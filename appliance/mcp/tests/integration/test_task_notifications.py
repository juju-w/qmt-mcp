"""Stable MCP 2026-07-28 task subscriptions and status notifications."""

from __future__ import annotations

import asyncio
import http.client
import json
import socket
import threading
import time
from types import SimpleNamespace

import pytest

pytest.importorskip("mcp")

pytestmark = pytest.mark.integration

import uvicorn  # noqa: E402
from mcp.server.auth.middleware.auth_context import auth_context_var  # noqa: E402
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser  # noqa: E402
from mcp.server.auth.provider import AccessToken  # noqa: E402
from mcp.server.subscriptions import InMemorySubscriptionBus  # noqa: E402
from mcp.shared.exceptions import MCPError  # noqa: E402
from mcp.shared.subscriptions import ToolsListChanged  # noqa: E402
from mcp_types import ElicitRequest, ElicitRequestFormParams  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from qmt_mcp_core.app import create_app  # noqa: E402
from qmt_mcp_core.config import CoreConfig  # noqa: E402
from qmt_mcp_core.task_notifications import (  # noqa: E402
    MAX_TASK_IDS_PER_SUBSCRIPTION,
    TaskListenHandler,
    TaskStateEvent,
    TaskSubscriptionFilter,
    TaskSubscriptionsListenRequestParams,
)
from qmt_mcp_core.task_store import TaskStore  # noqa: E402
from qmt_mcp_core.tasks_extension import (  # noqa: E402
    STABLE_PROTOCOL_VERSION,
    TASKS_EXTENSION_ID,
    TaskInteraction,
    TaskRequestParams,
    TasksExtension,
)


class RecordingSession:
    def __init__(self, *, tasks: bool = True, block_task_frames: bool = False):
        extensions = {TASKS_EXTENSION_ID: {}} if tasks else {}
        self.client_capabilities = SimpleNamespace(extensions=extensions)
        self.frames: list[dict] = []
        self.changed = asyncio.Event()
        self.block_task_frames = block_task_frames
        self.task_frame_entered = asyncio.Event()
        self.release_task_frames = asyncio.Event()

    async def send_notification(self, notification, *, related_request_id):
        frame = notification.model_dump(mode="json", by_alias=True, exclude_none=True)
        frame["_relatedRequestId"] = related_request_id
        if frame["method"] == "notifications/tasks" and self.block_task_frames:
            self.task_frame_entered.set()
            await self.release_task_frames.wait()
        self.frames.append(frame)
        self.changed.set()


def _context(session: RecordingSession, request_id: str = "listen-1", *, version: str = STABLE_PROTOCOL_VERSION):
    return SimpleNamespace(
        protocol_version=version,
        request_id=request_id,
        session=session,
    )


def _params(*task_ids: str, tools: bool = False) -> TaskSubscriptionsListenRequestParams:
    return TaskSubscriptionsListenRequestParams(
        notifications=TaskSubscriptionFilter(
            taskIds=list(task_ids),
            toolsListChanged=tools or None,
        )
    )


async def _wait_frames(session: RecordingSession, count: int, timeout: float = 2) -> None:
    async with asyncio.timeout(timeout):
        while len(session.frames) < count:
            session.changed.clear()
            await session.changed.wait()


async def _stop_listener(runner: asyncio.Task, handler: TaskListenHandler) -> None:
    handler.close()
    await asyncio.wait_for(runner, timeout=2)
    assert handler.active_streams == 0


def _extension(tmp_path, *, max_buffered_events: int = 128):
    bus = InMemorySubscriptionBus()
    store = TaskStore(tmp_path / "tasks.sqlite3", poll_interval_ms=25)
    extension = TasksExtension(store, task_tools=(), subscriptions=bus)
    handler = TaskListenHandler(bus, extension, max_buffered_events=max_buffered_events)
    return store, extension, bus, handler


def _owned_record(store: TaskStore, extension: TasksExtension, *, scopes: tuple[str, ...] = ()):
    return store.create(
        owner_digest=extension.principal_digest(),
        tool_name="notification-test",
        required_scopes=scopes,
    )


def _access_token(name: str, scopes: list[str]) -> AccessToken:
    return AccessToken(
        token=f"token-{name}",
        client_id=f"client-{name}",
        subject=f"user-{name}",
        scopes=scopes,
        resource="https://qmt.example/mcp",
    )


def _owner_for(extension: TasksExtension, token: AccessToken) -> str:
    marker = auth_context_var.set(AuthenticatedUser(token))
    try:
        return extension.principal_digest()
    finally:
        auth_context_var.reset(marker)


def test_filter_validation_capability_and_protocol_gating(tmp_path):
    store, extension, _bus, handler = _extension(tmp_path)
    record = _owned_record(store, extension)

    with pytest.raises(ValidationError):
        _params(*[record.task_id] * (MAX_TASK_IDS_PER_SUBSCRIPTION + 1))

    async def scenario():
        with pytest.raises(MCPError) as malformed:
            await handler(_context(RecordingSession()), _params("not-a-task-id"))
        assert malformed.value.code == -32602

        with pytest.raises(MCPError) as capability:
            await handler(_context(RecordingSession(tasks=False)), _params(record.task_id))
        assert capability.value.code == -32021

        with pytest.raises(MCPError) as legacy:
            await handler(
                _context(RecordingSession(), version="2025-11-25"),
                _params(record.task_id),
            )
        assert legacy.value.code == -32601

        session = RecordingSession()
        runner = asyncio.create_task(
            handler(
                _context(session),
                _params(record.task_id, record.task_id),
            )
        )
        await _wait_frames(session, 2)
        acknowledged = session.frames[0]["params"]["notifications"]["taskIds"]
        assert acknowledged == [record.task_id]
        await _stop_listener(runner, handler)

    asyncio.run(scenario())


def test_acknowledgement_current_and_terminal_snapshot_order(tmp_path):
    store, extension, _bus, handler = _extension(tmp_path)
    record = _owned_record(store, extension)

    async def scenario():
        session = RecordingSession()
        runner = asyncio.create_task(handler(_context(session), _params(record.task_id)))
        await _wait_frames(session, 2)

        assert store.complete(record.task_id, {"content": [{"type": "text", "text": "done"}]})
        await extension._publish_current(record.task_id)
        await _wait_frames(session, 3)

        assert [frame["method"] for frame in session.frames] == [
            "notifications/subscriptions/acknowledged",
            "notifications/tasks",
            "notifications/tasks",
        ]
        snapshots = [frame["params"] for frame in session.frames[1:]]
        assert [snapshot["status"] for snapshot in snapshots] == ["working", "completed"]
        assert snapshots[-1]["result"]["content"][0]["text"] == "done"
        for frame in session.frames:
            assert frame["_relatedRequestId"] == "listen-1"
            assert frame["params"]["_meta"]["io.modelcontextprotocol/subscriptionId"] == "listen-1"
        for snapshot in snapshots:
            assert "resultType" not in snapshot
            assert "owner_digest" not in snapshot
            assert "required_scopes" not in snapshot
        assert not any(frame["method"] == "notifications/tasks/status" for frame in session.frames)
        await _stop_listener(runner, handler)

    asyncio.run(scenario())


def test_failure_tool_error_and_cancellation_terminal_shapes(tmp_path):
    store, extension, _bus, handler = _extension(tmp_path)
    failed = _owned_record(store, extension)
    tool_error = _owned_record(store, extension)
    cancelled = _owned_record(store, extension)

    async def scenario():
        session = RecordingSession()
        context = _context(session, "listen-terminals")
        runner = asyncio.create_task(
            handler(
                context,
                _params(failed.task_id, tool_error.task_id, cancelled.task_id),
            )
        )
        await _wait_frames(session, 4)

        async def raise_protocol_error(_ctx):
            raise MCPError(code=-32603, message="protocol failure")

        await extension._execute(
            failed.task_id,
            TaskInteraction(store, failed.task_id, extension._publish_current),
            context,
            raise_protocol_error,
        )

        async def return_tool_error(_ctx):
            return {
                "content": [{"type": "text", "text": "tool failed"}],
                "isError": True,
            }

        await extension._execute(
            tool_error.task_id,
            TaskInteraction(store, tool_error.task_id, extension._publish_current),
            context,
            return_tool_error,
        )
        await extension._cancel(context, TaskRequestParams(taskId=cancelled.task_id))
        await _wait_frames(session, 7)

        terminal = {frame["params"]["taskId"]: frame["params"] for frame in session.frames[4:]}
        assert terminal[failed.task_id]["status"] == "failed"
        assert terminal[failed.task_id]["error"]["code"] == -32603
        assert terminal[tool_error.task_id]["status"] == "completed"
        assert terminal[tool_error.task_id]["result"]["isError"] is True
        assert terminal[cancelled.task_id]["status"] == "cancelled"
        assert terminal[cancelled.task_id]["statusMessage"] == "Cancelled by client"
        await _stop_listener(runner, handler)

    asyncio.run(scenario())


def test_snapshot_race_mixed_filters_and_multiple_listeners(tmp_path):
    store, extension, bus, handler = _extension(tmp_path)
    record = _owned_record(store, extension)

    async def scenario():
        first = RecordingSession()
        second = RecordingSession()
        first_runner = asyncio.create_task(handler(_context(first, "listen-a"), _params(record.task_id, tools=True)))
        second_runner = asyncio.create_task(handler(_context(second, "listen-b"), _params(record.task_id)))
        await asyncio.gather(_wait_frames(first, 2), _wait_frames(second, 2))

        await bus.publish(ToolsListChanged())
        await _wait_frames(first, 3)
        assert first.frames[2]["method"] == "notifications/tools/list_changed"
        assert len(second.frames) == 2

        assert store.complete(record.task_id, {"ok": True})
        await extension._publish_current(record.task_id)
        await asyncio.gather(_wait_frames(first, 4), _wait_frames(second, 3))
        assert first.frames[-1]["params"]["status"] == "completed"
        assert second.frames[-1]["params"]["status"] == "completed"

        for runner in (first_runner, second_runner):
            runner.cancel()
        await asyncio.gather(first_runner, second_runner, return_exceptions=True)
        assert handler.active_streams == 0

        # Hold the acknowledgement write open while the task advances. The
        # current working snapshot must still precede the queued completion.
        race_handler = TaskListenHandler(bus, extension)
        race_record = _owned_record(store, extension)
        race_session = RecordingSession()
        original_send = race_session.send_notification
        acknowledge_entered = asyncio.Event()
        release_acknowledgement = asyncio.Event()

        async def blocked_ack(notification, *, related_request_id):
            if notification.method == "notifications/subscriptions/acknowledged":
                acknowledge_entered.set()
                await release_acknowledgement.wait()
            await original_send(notification, related_request_id=related_request_id)

        race_session.send_notification = blocked_ack
        race_runner = asyncio.create_task(
            race_handler(
                _context(race_session, "listen-race"),
                _params(race_record.task_id),
            )
        )
        await acknowledge_entered.wait()
        assert store.complete(race_record.task_id, {"race": "settled"})
        await extension._publish_current(race_record.task_id)
        release_acknowledgement.set()
        await _wait_frames(race_session, 3)
        assert [frame["params"]["status"] for frame in race_session.frames[1:]] == [
            "working",
            "completed",
        ]
        await _stop_listener(race_runner, race_handler)

    asyncio.run(scenario())


def test_slow_consumer_closes_without_blocking_publishers(tmp_path):
    store, extension, bus, handler = _extension(tmp_path, max_buffered_events=2)
    record = _owned_record(store, extension)

    async def scenario():
        session = RecordingSession(block_task_frames=True)
        runner = asyncio.create_task(handler(_context(session), _params(record.task_id)))
        await session.task_frame_entered.wait()

        snapshot = record.to_notification()
        for _ in range(3):
            await bus.publish(
                TaskStateEvent(
                    task_id=record.task_id,
                    owner_digest=record.owner_digest,
                    snapshot=snapshot,
                )
            )
        assert handler.active_streams == 0

        session.release_task_frames.set()
        await asyncio.wait_for(runner, timeout=2)
        assert handler.active_streams == 0

    asyncio.run(scenario())


def test_reconnect_restart_expiry_and_oauth_isolation(tmp_path):
    store, extension, _bus, handler = _extension(tmp_path)
    static_record = _owned_record(store, extension)
    assert store.complete(static_record.task_id, {"persisted": True})

    token_a = _access_token("a", ["qmt:read", "qmt:trade"])
    token_b = _access_token("b", ["qmt:read"])
    oauth_record = store.create(
        owner_digest=_owner_for(extension, token_a),
        tool_name="scoped",
        required_scopes=("qmt:trade",),
    )

    async def scenario():
        # A restarted extension reads the same persisted terminal snapshot.
        restarted = TasksExtension(
            TaskStore(store.path),
            task_tools=(),
            subscriptions=InMemorySubscriptionBus(),
        )
        restarted_handler = TaskListenHandler(restarted.subscriptions, restarted)
        session = RecordingSession()
        runner = asyncio.create_task(
            restarted_handler(
                _context(session, "listen-restart"),
                _params(static_record.task_id),
            )
        )
        await _wait_frames(session, 2)
        assert session.frames[1]["params"]["status"] == "completed"
        await _stop_listener(runner, restarted_handler)

        # Different principals and insufficient scopes are indistinguishable
        # from unknown IDs: none are acknowledged or disclosed.
        marker = auth_context_var.set(AuthenticatedUser(token_b))
        try:
            denied = RecordingSession()
            await handler(
                _context(denied, "listen-denied"),
                _params(oauth_record.task_id, "tsk_" + "x" * 40),
            )
        finally:
            auth_context_var.reset(marker)
        assert denied.frames == [
            {
                "method": "notifications/subscriptions/acknowledged",
                "params": {
                    "notifications": {},
                    "_meta": {"io.modelcontextprotocol/subscriptionId": "listen-denied"},
                },
                "_relatedRequestId": "listen-denied",
            }
        ]

        # The owning principal sees the record when its original scope remains.
        marker = auth_context_var.set(AuthenticatedUser(token_a))
        try:
            allowed = RecordingSession()
            allowed_runner = asyncio.create_task(
                handler(
                    _context(allowed, "listen-allowed"),
                    _params(oauth_record.task_id),
                )
            )
            await _wait_frames(allowed, 2)
            assert allowed.frames[0]["params"]["notifications"]["taskIds"] == [oauth_record.task_id]
            allowed_runner.cancel()
            await asyncio.gather(allowed_runner, return_exceptions=True)
        finally:
            auth_context_var.reset(marker)

        expiring_store = TaskStore(tmp_path / "expiring.sqlite3", ttl_ms=1, clock_ms=lambda: 100)
        expiring_extension = TasksExtension(
            expiring_store,
            task_tools=(),
            subscriptions=InMemorySubscriptionBus(),
        )
        expired = _owned_record(expiring_store, expiring_extension)
        expiring_store._clock_ms = lambda: 102
        expiring_handler = TaskListenHandler(expiring_extension.subscriptions, expiring_extension)
        expired_session = RecordingSession()
        await expiring_handler(
            _context(expired_session, "listen-expired"),
            _params(expired.task_id),
        )
        assert expired_session.frames[0]["params"]["notifications"] == {}

    asyncio.run(scenario())


def test_input_transition_publication_and_noop_suppression(tmp_path):
    store, extension, bus, handler = _extension(tmp_path)
    record = _owned_record(store, extension)
    events: list[TaskStateEvent] = []
    unsubscribe = bus.subscribe(lambda event: events.append(event) if isinstance(event, TaskStateEvent) else None)
    interaction = TaskInteraction(store, record.task_id, extension._publish_current)

    def request(message: str) -> ElicitRequest:
        return ElicitRequest(
            params=ElicitRequestFormParams(
                message=message,
                requested_schema={
                    "type": "object",
                    "properties": {"confirm": {"type": "boolean"}},
                    "required": ["confirm"],
                },
            )
        )

    async def scenario():
        session = RecordingSession()
        runner = asyncio.create_task(
            handler(
                _context(session, "listen-input"),
                _params(record.task_id),
            )
        )
        await _wait_frames(session, 2)

        waiter = asyncio.create_task(
            interaction.request_input(
                {"first": request("First"), "second": request("Second")},
                status_message="Waiting",
            )
        )
        await _wait_frames(session, 3)
        assert [event.snapshot["status"] for event in events] == ["input_required"]

        answer = {"action": "accept", "content": {"confirm": True}}
        await interaction.submit({"unknown": answer})
        assert len(events) == 1
        await interaction.submit({"first": answer})
        await _wait_frames(session, 4)
        assert set(events[-1].snapshot["inputRequests"]) == {"second"}
        await interaction.submit({"first": answer})
        assert len(events) == 2
        await interaction.submit({"second": answer})
        await _wait_frames(session, 5)
        assert (await waiter)["second"] == answer
        assert [event.snapshot["status"] for event in events] == [
            "input_required",
            "input_required",
            "working",
        ]
        assert not any("inputResponses" in event.snapshot for event in events)
        await interaction.close()

        assert store.complete(record.task_id, {"content": [{"type": "text", "text": "done"}]})
        await extension._publish_current(record.task_id)
        await _wait_frames(session, 6)
        assert [frame["params"]["status"] for frame in session.frames[1:]] == [
            "working",
            "input_required",
            "input_required",
            "working",
            "completed",
        ]

        context = _context(RecordingSession())
        count = len(events)
        await extension._cancel(context, TaskRequestParams(taskId=record.task_id))
        assert len(events) == count
        await _stop_listener(runner, handler)

    try:
        asyncio.run(scenario())
    finally:
        unsubscribe()


def _config(tmp_path, port: int) -> CoreConfig:
    return CoreConfig(
        broker_id="acme",
        broker_name="ACME",
        xtquant_dir_win="",
        userdata_win="",
        mcp_mode="readonly",
        token="",
        host="127.0.0.1",
        port=port,
        transport="streamable-http",
        audit_path=str(tmp_path / "audit.jsonl"),
        worker_limit=2,
        allow_unauth_loopback=True,
        enable_xtdata=False,
        test_mode=True,
        task_store=str(tmp_path / "http-tasks.sqlite3"),
        task_poll_interval_ms=100,
        task_conformance_fixtures=True,
    )


def _request(method: str, request_id: str, params: dict) -> tuple[dict, dict]:
    params = dict(params)
    params["_meta"] = {
        "io.modelcontextprotocol/protocolVersion": STABLE_PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientInfo": {"name": "notification-http-test", "version": "1"},
        "io.modelcontextprotocol/clientCapabilities": {
            "extensions": {TASKS_EXTENSION_ID: {}},
        },
    }
    headers = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
        "mcp-protocol-version": STABLE_PROTOCOL_VERSION,
        "mcp-method": method,
    }
    if method == "tools/call":
        headers["mcp-name"] = params["name"]
    return (
        {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
        headers,
    )


def _first_rpc_document(content_type: str, body: bytes) -> dict:
    if "text/event-stream" not in content_type:
        return json.loads(body)
    for line in body.decode().splitlines():
        if line.startswith("data:"):
            return json.loads(line.removeprefix("data:").strip())
    raise AssertionError("SSE response did not contain JSON-RPC data")


def test_real_streamable_http_completes_without_task_poll(fake_xtquant, tmp_path):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    port = sock.getsockname()[1]
    app, _cfg, _health, _registry = create_app(_config(tmp_path, port))
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            log_level="error",
            timeout_graceful_shutdown=1,
        )
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 3
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started

    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        call, call_headers = _request(
            "tools/call",
            "call-1",
            {"name": "slow_compute", "arguments": {"seconds": 0.5, "label": "push"}},
        )
        connection.request("POST", "/mcp", body=json.dumps(call), headers=call_headers)
        created_response = connection.getresponse()
        created_body = created_response.read()
        created = _first_rpc_document(
            created_response.getheader("content-type", ""),
            created_body,
        )["result"]
        assert created["status"] == "working"

        listen, listen_headers = _request(
            "subscriptions/listen",
            "listen-http",
            {"notifications": {"taskIds": [created["taskId"]]}},
        )
        connection.request("POST", "/mcp", body=json.dumps(listen), headers=listen_headers)
        response = connection.getresponse()
        assert response.status == 200
        assert "text/event-stream" in response.getheader("content-type", "")
        frames = []
        while line := response.readline():
            text = line.decode().strip()
            if not text.startswith("data:"):
                continue
            frame = json.loads(text.removeprefix("data:").strip())
            frames.append(frame)
            if frame.get("method") == "notifications/tasks" and frame.get("params", {}).get("status") == "completed":
                break

        assert frames[0]["method"] == "notifications/subscriptions/acknowledged"
        assert frames[0]["params"]["notifications"]["taskIds"] == [created["taskId"]]
        task_frames = [frame for frame in frames if frame.get("method") == "notifications/tasks"]
        assert task_frames[0]["params"]["status"] == "working"
        assert task_frames[-1]["params"]["status"] == "completed"
        assert task_frames[-1]["params"]["result"]["content"][0]["text"] == "Completed push"
    finally:
        connection.close()
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
    assert not thread.is_alive()
