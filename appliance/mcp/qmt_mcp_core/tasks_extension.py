"""Stable MCP 2026-07-28 Tasks extension runtime."""

from __future__ import annotations

import asyncio
import contextvars
import hashlib
import json
from collections.abc import Sequence
from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import principal_components
from mcp.server.extension import Extension, MethodBinding
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.server import require_client_extension
from mcp.shared.exceptions import MCPError
from mcp_types import (
    CallToolRequestParams,
    CreateMessageResult,
    CreateMessageResultWithTools,
    ElicitRequest,
    ElicitRequestFormParams,
    ElicitResult,
    InputRequests,
    InputRequiredResult,
    ListRootsResult,
    RequestParams,
)
from pydantic import Field, TypeAdapter, ValidationError
from pydantic_core import to_jsonable_python

from .registry import ToolRegistry
from .task_notifications import TASKS_EXTENSION_ID, TaskStateEvent
from .task_store import TaskRecord, TaskStore

STABLE_PROTOCOL_VERSION = "2026-07-28"
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
MAX_INPUT_ITEMS = 16
MAX_INPUT_KEY = 128
MAX_INPUT_METHOD = 128
MAX_INPUT_BATCH_BYTES = 65_536

_INPUT_REQUESTS_ADAPTER = TypeAdapter(InputRequests)
_INPUT_RESPONSE_ADAPTERS = {
    "elicitation/create": TypeAdapter(ElicitResult),
    "sampling/createMessage": TypeAdapter(CreateMessageResult | CreateMessageResultWithTools),
    "roots/list": TypeAdapter(ListRootsResult),
}
_current_task_interaction: contextvars.ContextVar[TaskInteraction | None] = contextvars.ContextVar(
    "qmt_task_interaction",
    default=None,
)


async def _noop_publish(_task_id: str) -> None:
    return


class TaskRequestParams(RequestParams):
    task_id: str = Field(alias="taskId", min_length=1, max_length=128)


class TaskUpdateParams(TaskRequestParams):
    input_responses: dict[str, Any] = Field(alias="inputResponses", default_factory=dict)


def _invalid_params(message: str) -> MCPError:
    return MCPError(code=INVALID_PARAMS, message=message)


def _compact_json_size(value: Any) -> int:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise _invalid_params("Input data must be valid JSON") from exc
    return len(encoded)


def _validate_input_keys(value: dict[str, Any], *, label: str) -> None:
    if len(value) > MAX_INPUT_ITEMS:
        raise _invalid_params(f"{label} exceeds {MAX_INPUT_ITEMS} entries")
    for key in value:
        if not isinstance(key, str) or not key or len(key) > MAX_INPUT_KEY:
            raise _invalid_params(f"{label} contains an invalid key")


def _normalize_input_requests(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or not value:
        raise _invalid_params("inputRequests must be a non-empty object")
    _validate_input_keys(value, label="inputRequests")
    try:
        parsed = _INPUT_REQUESTS_ADAPTER.validate_python(value)
        normalized = _INPUT_REQUESTS_ADAPTER.dump_python(
            parsed,
            by_alias=True,
            mode="json",
            exclude_none=True,
        )
    except ValidationError as exc:
        raise _invalid_params("inputRequests contains an invalid standard MCP request") from exc
    for request in normalized.values():
        method = request.get("method")
        if not isinstance(method, str) or not method or len(method) > MAX_INPUT_METHOD:
            raise _invalid_params("inputRequests contains an invalid method")
    if _compact_json_size(normalized) > MAX_INPUT_BATCH_BYTES:
        raise _invalid_params("inputRequests exceeds 65536 bytes")
    return normalized


def _validate_response_batch(value: dict[str, Any]) -> None:
    if not isinstance(value, dict):
        raise _invalid_params("inputResponses must be an object")
    _validate_input_keys(value, label="inputResponses")
    if _compact_json_size(value) > MAX_INPUT_BATCH_BYTES:
        raise _invalid_params("inputResponses exceeds 65536 bytes")


def _normalize_matching_response(request: dict[str, Any], response: Any) -> Any:
    method = request["method"]
    adapter = _INPUT_RESPONSE_ADAPTERS.get(method)
    if adapter is None:
        raise _invalid_params(f"Unsupported input request method {method!r}")
    try:
        parsed = adapter.validate_python(response)
        return adapter.dump_python(parsed, by_alias=True, mode="json", exclude_none=True)
    except ValidationError as exc:
        raise _invalid_params(f"Invalid response for {method}") from exc


def _normalize_complete_response_set(
    requests: dict[str, Any],
    responses: dict[str, Any],
) -> dict[str, Any]:
    _validate_response_batch(responses)
    if set(responses) != set(requests):
        raise _invalid_params("Synchronous fallback responses must match every input request")
    return {key: _normalize_matching_response(requests[key], response) for key, response in responses.items()}


def _principal_digest() -> str:
    token = get_access_token()
    components: tuple[str, str | None, str | None] | tuple[str]
    if token is None:
        components = ("qmt-static-principal-v1",)
    else:
        components = principal_components(token)
    encoded = json.dumps(components, ensure_ascii=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _declares_tasks(ctx) -> bool:
    capabilities = ctx.session.client_capabilities
    extensions = capabilities.extensions if capabilities else None
    return bool(extensions and TASKS_EXTENSION_ID in extensions)


def _error_payload(exc: MCPError) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": exc.code, "message": exc.message}
    if exc.data is not None:
        payload["data"] = to_jsonable_python(exc.data)
    return payload


class TaskInteraction:
    """Coordinate one live task's durable input snapshots and transient answers."""

    def __init__(self, store: TaskStore, task_id: str, publish=_noop_publish):
        self.store = store
        self.task_id = task_id
        self._publish = publish
        self._lock = asyncio.Lock()
        self._pending: dict[str, Any] = {}
        self._responses: dict[str, Any] = {}
        self._used_keys: set[str] = set()
        self._waiter: asyncio.Future[dict[str, Any]] | None = None
        self._closed = False
        self._status_message: str | None = None

    async def request_input(
        self,
        input_requests: dict[str, Any],
        *,
        status_message: str | None = None,
    ) -> dict[str, Any]:
        normalized = _normalize_input_requests(input_requests)
        async with self._lock:
            if self._closed:
                raise _invalid_params("Task no longer accepts input")
            if self._waiter is not None or self._pending:
                raise _invalid_params("Task already has pending input")
            if self._used_keys.intersection(normalized):
                raise _invalid_params("Task input request keys must be unique")
            waiter = asyncio.get_running_loop().create_future()
            if not self.store.request_input(
                self.task_id,
                normalized,
                status_message=status_message,
            ):
                raise _invalid_params("Task no longer accepts input")
            self._used_keys.update(normalized)
            self._pending = dict(normalized)
            self._responses = {}
            self._waiter = waiter
            self._status_message = status_message
        await self._publish(self.task_id)
        try:
            return await waiter
        finally:
            async with self._lock:
                if self._waiter is waiter:
                    self._waiter = None

    async def submit(self, input_responses: dict[str, Any]) -> None:
        _validate_response_batch(input_responses)
        changed = False
        async with self._lock:
            if self._closed or not self._pending:
                return
            matching = {
                key: _normalize_matching_response(self._pending[key], response)
                for key, response in input_responses.items()
                if key in self._pending
            }
            if not matching:
                return

            remaining = {key: request for key, request in self._pending.items() if key not in matching}
            if remaining:
                if not self.store.replace_input_requests(
                    self.task_id,
                    remaining,
                    status_message=self._status_message,
                ):
                    self._close_locked()
                    return
                self._responses.update(matching)
                self._pending = remaining
                changed = True
            else:
                if not self.store.resume(self.task_id):
                    self._close_locked()
                    return
                self._responses.update(matching)
                self._pending = {}
                waiter = self._waiter
                self._waiter = None
                responses = dict(self._responses)
                self._responses = {}
                if waiter is not None and not waiter.done():
                    waiter.set_result(responses)
                changed = True

        if changed:
            await self._publish(self.task_id)

    async def close(self) -> None:
        async with self._lock:
            self._close_locked()

    def _close_locked(self) -> None:
        self._closed = True
        self._pending = {}
        self._responses = {}
        waiter = self._waiter
        self._waiter = None
        if waiter is not None and not waiter.done():
            waiter.cancel()


async def request_task_input(
    input_requests: dict[str, Any],
    *,
    status_message: str | None = None,
    synchronous_fallback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pause a durable task, or return the caller's safe synchronous fallback."""

    interaction = _current_task_interaction.get()
    if interaction is None:
        if synchronous_fallback is None:
            raise _invalid_params("This tool requires task input support")
        normalized = _normalize_input_requests(input_requests)
        return _normalize_complete_response_set(normalized, synchronous_fallback)
    return await interaction.request_input(input_requests, status_message=status_message)


class TasksExtension(Extension):
    identifier = TASKS_EXTENSION_ID

    def __init__(
        self,
        store: TaskStore,
        *,
        task_tools: Sequence[str],
        mrtr_before_task_tools: Sequence[str] = (),
        conformance_fixtures: bool = False,
        subscriptions=None,
    ):
        self.store = store
        self.task_tools = frozenset(task_tools)
        self.mrtr_before_task_tools = frozenset(mrtr_before_task_tools)
        self.conformance_fixtures = conformance_fixtures
        self.subscriptions = subscriptions
        self.registry: ToolRegistry | None = None
        self._running: dict[str, asyncio.Task[None]] = {}
        self._interactions: dict[str, TaskInteraction] = {}
        self._expiry_watchers: dict[str, asyncio.Task[None]] = {}

    def bind_registry(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def require_capability(self, ctx) -> None:
        require_client_extension(ctx, self.identifier)

    def principal_digest(self) -> str:
        return _principal_digest()

    def subscription_records(self, task_ids: Sequence[str]) -> list[TaskRecord]:
        """Return only current records authorized for this request principal."""

        owner_digest = _principal_digest()
        token = get_access_token()
        scopes = set(token.scopes) if token is not None else None
        records: list[TaskRecord] = []
        for task_id in task_ids:
            record = self.store.get(task_id)
            if record is None or record.owner_digest != owner_digest:
                continue
            if scopes is not None and not set(record.required_scopes).issubset(scopes):
                continue
            records.append(record)
        return records

    async def _publish_current(self, task_id: str) -> None:
        if self.subscriptions is None:
            return
        record = self.store.get(task_id)
        if record is None:
            return
        await self.subscriptions.publish(
            TaskStateEvent(
                task_id=record.task_id,
                owner_digest=record.owner_digest,
                snapshot=record.to_notification(),
            )
        )

    def methods(self) -> Sequence[MethodBinding]:
        versions = frozenset({STABLE_PROTOCOL_VERSION})
        return (
            MethodBinding("tasks/get", TaskRequestParams, self._get, versions),
            MethodBinding("tasks/update", TaskUpdateParams, self._update, versions),
            MethodBinding("tasks/cancel", TaskRequestParams, self._cancel, versions),
        )

    async def intercept_tool_call(self, params: CallToolRequestParams, ctx, call_next):
        if params.name not in self.task_tools:
            return await call_next(ctx)
        if ctx.protocol_version != STABLE_PROTOCOL_VERSION:
            return await call_next(ctx)

        if params.name in self.mrtr_before_task_tools:
            result = await call_next(ctx)
            if not params.input_responses or isinstance(result, InputRequiredResult) or not _declares_tasks(ctx):
                return result
            return await self._taskify_completed_result(params.name, result)

        if not _declares_tasks(ctx):
            if self.conformance_fixtures and params.name == "failing_job":
                require_client_extension(ctx, self.identifier)
            return await call_next(ctx)

        required_scopes: tuple[str, ...] = ()
        if self.registry is not None:
            required_scopes = self.registry.required_scopes(params.name) or ()
        record = self.store.create(
            owner_digest=_principal_digest(),
            tool_name=params.name,
            required_scopes=required_scopes,
        )
        interaction = TaskInteraction(self.store, record.task_id, self._publish_current)
        self._interactions[record.task_id] = interaction
        runner = asyncio.create_task(
            self._execute(record.task_id, interaction, ctx, call_next),
            name=f"mcp-task-{record.task_id}",
        )
        self._running[record.task_id] = runner
        runner.add_done_callback(lambda _done, task_id=record.task_id: self._running.pop(task_id, None))
        if record.ttl_ms is not None:
            watcher = asyncio.create_task(
                self._expire_after(record.task_id, record.ttl_ms),
                name=f"mcp-task-expiry-{record.task_id}",
            )
            self._expiry_watchers[record.task_id] = watcher
            watcher.add_done_callback(lambda _done, task_id=record.task_id: self._expiry_watchers.pop(task_id, None))
        await self._publish_current(record.task_id)
        return record.to_wire(created=True)

    async def _taskify_completed_result(self, tool_name: str, result: Any) -> dict[str, Any]:
        required_scopes: tuple[str, ...] = ()
        if self.registry is not None:
            required_scopes = self.registry.required_scopes(tool_name) or ()
        record = self.store.create(
            owner_digest=_principal_digest(),
            tool_name=tool_name,
            required_scopes=required_scopes,
        )
        if not self.store.complete(
            record.task_id,
            to_jsonable_python(result, by_alias=True, exclude_none=True),
        ):
            raise MCPError(code=INTERNAL_ERROR, message="Task creation failed")
        completed = self.store.get(record.task_id)
        if completed is None:
            raise MCPError(code=INTERNAL_ERROR, message="Task creation failed")
        await self._publish_current(record.task_id)
        return completed.to_wire(created=True)

    async def _execute(self, task_id: str, interaction: TaskInteraction, ctx, call_next) -> None:
        token = _current_task_interaction.set(interaction)
        try:
            result = await call_next(ctx)
            if self.store.complete(task_id, to_jsonable_python(result, by_alias=True, exclude_none=True)):
                await self._publish_current(task_id)
        except asyncio.CancelledError:
            return
        except MCPError as exc:
            if self.store.fail(task_id, _error_payload(exc), status_message=exc.message):
                await self._publish_current(task_id)
        except Exception:
            changed = self.store.fail(
                task_id,
                {"code": INTERNAL_ERROR, "message": "Task execution failed"},
                status_message="Task execution failed",
            )
            if changed:
                await self._publish_current(task_id)
        finally:
            _current_task_interaction.reset(token)
            await interaction.close()
            self._interactions.pop(task_id, None)
            watcher = self._expiry_watchers.pop(task_id, None)
            if watcher is not None and watcher is not asyncio.current_task() and not watcher.done():
                watcher.cancel()

    async def _expire_after(self, task_id: str, ttl_ms: int) -> None:
        try:
            await asyncio.sleep(ttl_ms / 1000)
            while True:
                record = self.store.get(task_id)
                if record is None:
                    self._expiry_watchers.pop(task_id, None)
                    await self._stop_runtime(task_id, cancel_expiry=False)
                    return
                if record.terminal or record.expires_at_ms is None:
                    return
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            return

    async def _stop_runtime(self, task_id: str, *, cancel_expiry: bool = True) -> None:
        current = asyncio.current_task()
        if cancel_expiry:
            watcher = self._expiry_watchers.pop(task_id, None)
            if watcher is not None and watcher is not current and not watcher.done():
                watcher.cancel()
        if interaction := self._interactions.get(task_id):
            await interaction.close()
        runner = self._running.get(task_id)
        if runner is not None and runner is not current and not runner.done():
            runner.cancel()
            await asyncio.gather(runner, return_exceptions=True)
        self._running.pop(task_id, None)
        self._interactions.pop(task_id, None)

    async def _get(self, ctx, params: TaskRequestParams) -> dict[str, Any]:
        require_client_extension(ctx, self.identifier)
        return (await self._authorized_record(params.task_id)).to_wire()

    async def _update(self, ctx, params: TaskUpdateParams) -> dict[str, Any]:
        require_client_extension(ctx, self.identifier)
        await self._authorized_record(params.task_id)
        _validate_response_batch(params.input_responses)
        if interaction := self._interactions.get(params.task_id):
            await interaction.submit(params.input_responses)
        return {"resultType": "complete"}

    async def _cancel(self, ctx, params: TaskRequestParams) -> dict[str, Any]:
        require_client_extension(ctx, self.identifier)
        record = await self._authorized_record(params.task_id)
        if not record.terminal:
            if self.store.cancel(params.task_id):
                await self._publish_current(params.task_id)
            await self._stop_runtime(params.task_id)
        return {"resultType": "complete"}

    async def _authorized_record(self, task_id: str) -> TaskRecord:
        record = self.store.get(task_id)
        if record is None:
            await self._stop_runtime(task_id)
            raise MCPError(code=INVALID_PARAMS, message="Invalid task")
        if record.owner_digest != _principal_digest():
            raise MCPError(code=INVALID_PARAMS, message="Invalid task")
        token = get_access_token()
        if token is not None and not set(record.required_scopes).issubset(token.scopes):
            raise MCPError(code=INVALID_PARAMS, message="Invalid task")
        return record


def register_task_conformance_fixtures(mcp) -> None:
    """Register official harness fixtures only under the explicit CI gate."""

    @mcp.tool(name="greet")
    def greet(name: str) -> str:
        """Return a deterministic greeting for protocol conformance."""
        return f"Hello, {name}!"

    @mcp.tool(name="slow_compute")
    async def slow_compute(seconds: float = 1, label: str = "work") -> str:
        """Complete a bounded delayed operation for task lifecycle tests."""
        await asyncio.sleep(max(0, min(float(seconds), 120)))
        return f"Completed {label}"

    @mcp.tool(name="failing_job")
    async def failing_job() -> str:
        """Return an application-level tool error after a short delay."""
        await asyncio.sleep(1)
        raise ValueError("Fixture tool execution failed")

    @mcp.tool(name="protocol_error_job")
    async def protocol_error_job() -> str:
        """Raise a structured MCP error for failed-task conformance."""
        await asyncio.sleep(0)
        raise MCPError(code=INTERNAL_ERROR, message="Fixture protocol failure")

    @mcp.tool(name="confirm_delete")
    async def confirm_delete(filename: str) -> str:
        """Request confirmation input for a synthetic delete operation."""
        responses = await request_task_input(
            {
                "confirmation": ElicitRequest(
                    params=ElicitRequestFormParams(
                        message=f"Confirm deletion of {filename}",
                        requested_schema={
                            "type": "object",
                            "properties": {"confirm": {"type": "boolean"}},
                            "required": ["confirm"],
                        },
                    )
                )
            },
            status_message="Waiting for confirmation",
            synchronous_fallback={"confirmation": {"action": "cancel"}},
        )
        accepted = responses["confirmation"]
        if accepted.get("action") == "accept" and (accepted.get("content") or {}).get("confirm") is True:
            return f"Deleted {filename}"
        return f"Deletion of {filename} was not confirmed"

    @mcp.tool(name="multi_input")
    async def multi_input() -> str:
        """Request two independent confirmations for partial-update tests."""
        requests = {
            key: ElicitRequest(
                params=ElicitRequestFormParams(
                    message=f"Confirm {key}",
                    requested_schema={
                        "type": "object",
                        "properties": {"confirm": {"type": "boolean"}},
                        "required": ["confirm"],
                    },
                )
            )
            for key in ("first", "second")
        }
        responses = await request_task_input(
            requests,
            status_message="Waiting for two confirmations",
            synchronous_fallback={
                "first": {"action": "cancel"},
                "second": {"action": "cancel"},
            },
        )
        accepted = sum(
            response.get("action") == "accept" and (response.get("content") or {}).get("confirm") is True
            for response in responses.values()
        )
        return f"Received {accepted} confirmations"

    @mcp.tool(name="test_tool_with_task")
    async def test_tool_with_task(ctx: Context) -> str | InputRequiredResult:
        """Resolve synchronous input before starting a synthetic durable task."""
        if ctx.protocol_version != STABLE_PROTOCOL_VERSION:
            return "Task input is unavailable for this legacy client"
        input_request = ElicitRequest(
            params=ElicitRequestFormParams(
                message="What is your name?",
                requested_schema={
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            )
        )
        response = (ctx.input_responses or {}).get("user_name")
        if response is None:
            return InputRequiredResult(input_requests={"user_name": input_request})
        request = _normalize_input_requests({"user_name": input_request})["user_name"]
        value = _normalize_matching_response(
            request,
            to_jsonable_python(response, by_alias=True, exclude_none=True),
        )
        if value.get("action") == "accept" and not isinstance((value.get("content") or {}).get("name"), str):
            raise _invalid_params("Accepted user_name response requires a string name")
        name = (value.get("content") or {}).get("name", "unknown")
        return f"Completed task for {name}"
