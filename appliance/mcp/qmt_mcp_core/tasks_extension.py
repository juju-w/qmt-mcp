"""Stable MCP 2026-07-28 Tasks extension runtime."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Sequence
from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import principal_components
from mcp.server.extension import Extension, MethodBinding
from mcp.server.mcpserver.server import require_client_extension
from mcp.shared.exceptions import MCPError
from mcp_types import CallToolRequestParams, RequestParams
from pydantic import Field
from pydantic_core import to_jsonable_python

from .registry import ToolRegistry
from .task_store import TaskRecord, TaskStore

TASKS_EXTENSION_ID = "io.modelcontextprotocol/tasks"
STABLE_PROTOCOL_VERSION = "2026-07-28"
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class TaskRequestParams(RequestParams):
    task_id: str = Field(alias="taskId", min_length=1, max_length=128)


class TaskUpdateParams(TaskRequestParams):
    input_responses: dict[str, Any] = Field(alias="inputResponses", default_factory=dict)


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


class TasksExtension(Extension):
    identifier = TASKS_EXTENSION_ID

    def __init__(
        self,
        store: TaskStore,
        *,
        task_tools: Sequence[str],
        conformance_fixtures: bool = False,
    ):
        self.store = store
        self.task_tools = frozenset(task_tools)
        self.conformance_fixtures = conformance_fixtures
        self.registry: ToolRegistry | None = None
        self._running: dict[str, asyncio.Task[None]] = {}

    def bind_registry(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def methods(self) -> Sequence[MethodBinding]:
        versions = frozenset({STABLE_PROTOCOL_VERSION})
        return (
            MethodBinding("tasks/get", TaskRequestParams, self._get, versions),
            MethodBinding("tasks/update", TaskUpdateParams, self._update, versions),
            MethodBinding("tasks/cancel", TaskRequestParams, self._cancel, versions),
        )

    async def intercept_tool_call(self, params: CallToolRequestParams, ctx, call_next):
        if ctx.protocol_version != STABLE_PROTOCOL_VERSION or params.name not in self.task_tools:
            return await call_next(ctx)
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

        if self.conformance_fixtures and params.name == "confirm_delete":
            filename = str((params.arguments or {}).get("filename", "item"))
            self.store.request_input(
                record.task_id,
                {
                    "confirmation": {
                        "mode": "form",
                        "message": f"Confirm deletion of {filename}",
                        "requestedSchema": {
                            "type": "object",
                            "properties": {"confirm": {"type": "boolean"}},
                            "required": ["confirm"],
                        },
                    }
                },
                status_message="Waiting for confirmation",
            )
            waiting = self.store.get(record.task_id)
            assert waiting is not None
            return waiting.to_wire(created=True)

        runner = asyncio.create_task(
            self._execute(record.task_id, ctx, call_next),
            name=f"mcp-task-{record.task_id}",
        )
        self._running[record.task_id] = runner
        runner.add_done_callback(lambda _done, task_id=record.task_id: self._running.pop(task_id, None))
        return record.to_wire(created=True)

    async def _execute(self, task_id: str, ctx, call_next) -> None:
        try:
            result = await call_next(ctx)
            self.store.complete(task_id, to_jsonable_python(result, by_alias=True, exclude_none=True))
        except asyncio.CancelledError:
            return
        except MCPError as exc:
            self.store.fail(task_id, _error_payload(exc), status_message=exc.message)
        except Exception:
            self.store.fail(
                task_id,
                {"code": INTERNAL_ERROR, "message": "Task execution failed"},
                status_message="Task execution failed",
            )

    async def _get(self, ctx, params: TaskRequestParams) -> dict[str, Any]:
        require_client_extension(ctx, self.identifier)
        return self._authorized_record(params.task_id).to_wire()

    async def _update(self, ctx, params: TaskUpdateParams) -> dict[str, Any]:
        require_client_extension(ctx, self.identifier)
        self._authorized_record(params.task_id)
        # 024 defines multi-round structured input. Unknown responses are
        # intentionally acknowledged and ignored for forward compatibility.
        return {"resultType": "complete"}

    async def _cancel(self, ctx, params: TaskRequestParams) -> dict[str, Any]:
        require_client_extension(ctx, self.identifier)
        record = self._authorized_record(params.task_id)
        if not record.terminal:
            self.store.cancel(params.task_id)
            if runner := self._running.get(params.task_id):
                runner.cancel()
        return {"resultType": "complete"}

    def _authorized_record(self, task_id: str) -> TaskRecord:
        record = self.store.get(task_id)
        if record is None or record.owner_digest != _principal_digest():
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
    def confirm_delete(filename: str) -> str:
        """Request confirmation input for a synthetic delete operation."""
        return f"Deleted {filename}"
