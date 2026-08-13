"""Stable MCP Tasks extension lifecycle through the real ASGI transport."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from types import SimpleNamespace

import pytest

pytest.importorskip("mcp")

pytestmark = pytest.mark.integration

from mcp.shared.exceptions import MCPError  # noqa: E402
from mcp_types import CallToolRequestParams, ElicitRequest, ElicitRequestFormParams  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from qmt_mcp_core.app import create_app  # noqa: E402
from qmt_mcp_core.config import CoreConfig  # noqa: E402
from qmt_mcp_core.task_store import TaskStore  # noqa: E402
from qmt_mcp_core.tasks_extension import (  # noqa: E402
    TaskInteraction,
    TasksExtension,
    request_task_input,
)

VERSION = "2026-07-28"
TASKS_ID = "io.modelcontextprotocol/tasks"


def _config(tmp_path, **overrides) -> CoreConfig:
    values = dict(
        broker_id="acme",
        broker_name="ACME",
        xtquant_dir_win="",
        userdata_win="",
        mcp_mode="readonly",
        token="",
        host="127.0.0.1",
        port=8765,
        transport="streamable-http",
        audit_path=str(tmp_path / "audit.jsonl"),
        worker_limit=2,
        allow_unauth_loopback=True,
        enable_xtdata=False,
        test_mode=True,
        task_store=str(tmp_path / "tasks.sqlite3"),
        task_poll_interval_ms=100,
        task_conformance_fixtures=True,
    )
    values.update(overrides)
    return CoreConfig(**values)


def _request(
    method: str,
    request_id: int,
    params: dict | None = None,
    *,
    tasks: bool = True,
    name_header: str | None = None,
) -> tuple[dict, dict]:
    capabilities = {"extensions": {TASKS_ID: {}}} if tasks else {}
    body_params = dict(params or {})
    body_params["_meta"] = {
        "io.modelcontextprotocol/protocolVersion": VERSION,
        "io.modelcontextprotocol/clientInfo": {"name": "tasks-test", "version": "1.0.0"},
        "io.modelcontextprotocol/clientCapabilities": capabilities,
    }
    headers = {
        "accept": "application/json, text/event-stream",
        "mcp-protocol-version": VERSION,
        "mcp-method": method,
    }
    if name_header is not None:
        headers["mcp-name"] = name_header
    elif method == "tools/call":
        headers["mcp-name"] = body_params["name"]
    elif method in {"tasks/get", "tasks/update", "tasks/cancel"}:
        headers["mcp-name"] = body_params["taskId"]
    return (
        {"jsonrpc": "2.0", "id": request_id, "method": method, "params": body_params},
        headers,
    )


def _response_json(response) -> dict:
    if "text/event-stream" not in response.headers.get("content-type", ""):
        return response.json()
    for line in response.text.splitlines():
        if line.startswith("data:"):
            return json.loads(line.removeprefix("data:").strip())
    raise AssertionError("missing SSE data event")


def _rpc(client: TestClient, method: str, request_id: int, params: dict, **kwargs) -> dict:
    payload, headers = _request(method, request_id, params, **kwargs)
    response = client.post("/mcp", json=payload, headers=headers)
    assert response.status_code in {200, 400}, response.text
    return _response_json(response)


def _wait_terminal(client: TestClient, task_id: str, *, request_id: int = 100) -> dict:
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        document = _rpc(client, "tasks/get", request_id, {"taskId": task_id})
        task = document["result"]
        if task["status"] in {"completed", "failed", "cancelled"}:
            return task
        time.sleep(max(task.get("pollIntervalMs", 100) / 1000, 0.01))
        request_id += 1
    raise AssertionError(f"task {task_id} did not settle")


def _wait_status(
    client: TestClient,
    task_id: str,
    expected: str,
    *,
    request_id: int = 500,
) -> dict:
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        document = _rpc(client, "tasks/get", request_id, {"taskId": task_id})
        task = document["result"]
        if task["status"] == expected:
            return task
        if task["status"] in {"completed", "failed", "cancelled"}:
            raise AssertionError(f"task {task_id} reached {task['status']} before {expected}")
        time.sleep(0.01)
        request_id += 1
    raise AssertionError(f"task {task_id} did not reach {expected}")


def test_task_lifecycle_tool_error_protocol_error_and_cancel(fake_xtquant, tmp_path):
    app, _cfg, _health, _registry = create_app(_config(tmp_path))
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        discover = _rpc(client, "server/discover", 1, {})
        assert discover["result"]["capabilities"]["extensions"][TASKS_ID] == {}

        greet = _rpc(
            client,
            "tools/call",
            2,
            {"name": "greet", "arguments": {"name": "World"}},
        )["result"]
        assert greet["resultType"] == "complete"
        assert greet["content"][0]["text"] == "Hello, World!"
        assert "taskId" not in greet

        created = _rpc(
            client,
            "tools/call",
            3,
            {"name": "slow_compute", "arguments": {"seconds": 0.05, "label": "integration"}},
        )["result"]
        assert created["resultType"] == "task"
        assert created["status"] == "working"
        assert created["taskId"].startswith("tsk_")
        assert isinstance(created["ttlMs"], int)
        assert isinstance(created["pollIntervalMs"], int)

        immediate = _rpc(client, "tasks/get", 4, {"taskId": created["taskId"]})["result"]
        assert immediate["resultType"] == "complete"
        assert immediate["taskId"] == created["taskId"]
        terminal = _wait_terminal(client, created["taskId"])
        assert terminal["status"] == "completed"
        assert terminal["result"]["content"]
        assert terminal["result"]["isError"] is False

        tool_error = _rpc(
            client,
            "tools/call",
            5,
            {"name": "failing_job", "arguments": {}},
        )["result"]
        failed_tool = _wait_terminal(client, tool_error["taskId"], request_id=200)
        assert failed_tool["status"] == "completed"
        assert failed_tool["result"]["isError"] is True

        protocol_error = _rpc(
            client,
            "tools/call",
            6,
            {"name": "protocol_error_job", "arguments": {}},
        )["result"]
        failed_protocol = _wait_terminal(client, protocol_error["taskId"], request_id=300)
        assert failed_protocol["status"] == "failed"
        assert failed_protocol["error"]["code"] == -32603
        assert "result" not in failed_protocol

        long_task = _rpc(
            client,
            "tools/call",
            7,
            {"name": "slow_compute", "arguments": {"seconds": 60, "label": "cancel"}},
        )["result"]
        cancel = _rpc(client, "tasks/cancel", 8, {"taskId": long_task["taskId"]})["result"]
        assert cancel["resultType"] == "complete"
        assert set(cancel) <= {"resultType", "_meta"}
        cancelled = _rpc(client, "tasks/get", 9, {"taskId": long_task["taskId"]})["result"]
        assert cancelled["status"] == "cancelled"
        # Cancelling a terminal task remains idempotent.
        assert _rpc(client, "tasks/cancel", 10, {"taskId": long_task["taskId"]})["result"]["resultType"] == "complete"


def test_task_capability_gating_sync_fallback_and_update_ack(fake_xtquant, tmp_path):
    app, _cfg, _health, _registry = create_app(_config(tmp_path))
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        synchronous = _rpc(
            client,
            "tools/call",
            1,
            {"name": "slow_compute", "arguments": {"seconds": 0, "label": "sync"}},
            tasks=False,
        )["result"]
        assert synchronous["resultType"] == "complete"
        assert "taskId" not in synchronous

        safe_confirmation = _rpc(
            client,
            "tools/call",
            11,
            {"name": "confirm_delete", "arguments": {"filename": "safe.txt"}},
            tasks=False,
        )["result"]
        assert safe_confirmation["resultType"] == "complete"
        assert safe_confirmation["content"][0]["text"] == "Deletion of safe.txt was not confirmed"

        safe_multi = _rpc(
            client,
            "tools/call",
            12,
            {"name": "multi_input", "arguments": {}},
            tasks=False,
        )["result"]
        assert safe_multi["resultType"] == "complete"
        assert safe_multi["content"][0]["text"] == "Received 0 confirmations"

        missing = _rpc(
            client,
            "tasks/get",
            2,
            {"taskId": "tsk_" + "x" * 40},
            tasks=False,
        )
        assert missing["error"]["code"] == -32021
        required = _rpc(
            client,
            "tools/call",
            3,
            {"name": "failing_job", "arguments": {}},
            tasks=False,
        )
        assert required["error"]["code"] == -32021
        assert TASKS_ID in required["error"]["data"]["requiredCapabilities"]["extensions"]

        waiting = _rpc(
            client,
            "tools/call",
            4,
            {"name": "confirm_delete", "arguments": {"filename": "safe.txt"}},
        )["result"]
        assert waiting["resultType"] == "task"
        detailed = _rpc(client, "tasks/get", 5, {"taskId": waiting["taskId"]})["result"]
        assert detailed["resultType"] == "complete"
        assert detailed["status"] == "input_required"
        assert "inputRequests" in detailed
        ack = _rpc(
            client,
            "tasks/update",
            6,
            {
                "taskId": waiting["taskId"],
                "inputResponses": {"unknown-key": {"ignored": True}},
            },
        )["result"]
        assert ack["resultType"] == "complete"
        _rpc(client, "tasks/cancel", 7, {"taskId": waiting["taskId"]})


def test_task_unknown_and_header_mismatch_fail_closed(fake_xtquant, tmp_path):
    app, _cfg, _health, _registry = create_app(_config(tmp_path))
    unknown_id = "tsk_" + "z" * 40
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        unknown = _rpc(client, "tasks/get", 1, {"taskId": unknown_id})
        assert unknown["error"]["code"] == -32602

        payload, headers = _request(
            "tasks/get",
            2,
            {"taskId": unknown_id},
            name_header="tsk_" + "y" * 40,
        )
        response = client.post("/mcp", json=payload, headers=headers)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == -32020

        headers.pop("mcp-name")
        missing = client.post("/mcp", json=payload, headers=headers)
        assert missing.status_code == 400
        assert missing.json()["error"]["code"] == -32020


def test_task_input_resumes_and_late_responses_are_idempotent(fake_xtquant, tmp_path):
    app, _cfg, _health, _registry = create_app(_config(tmp_path))
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        created = _rpc(
            client,
            "tools/call",
            1,
            {"name": "confirm_delete", "arguments": {"filename": "safe.txt"}},
        )["result"]
        waiting = _wait_status(client, created["taskId"], "input_required")
        request = waiting["inputRequests"]["confirmation"]
        assert request["method"] == "elicitation/create"
        assert request["params"]["requestedSchema"]["required"] == ["confirm"]

        unknown = _rpc(
            client,
            "tasks/update",
            2,
            {
                "taskId": created["taskId"],
                "inputResponses": {"unknown": {"ignored": True}},
            },
        )["result"]
        assert unknown["resultType"] == "complete"
        still_waiting = _rpc(client, "tasks/get", 3, {"taskId": created["taskId"]})["result"]
        assert set(still_waiting["inputRequests"]) == {"confirmation"}

        invalid = _rpc(
            client,
            "tasks/update",
            31,
            {
                "taskId": created["taskId"],
                "inputResponses": {"confirmation": {"action": "maybe"}},
            },
        )
        assert invalid["error"]["code"] == -32602
        after_invalid = _rpc(client, "tasks/get", 32, {"taskId": created["taskId"]})["result"]
        assert set(after_invalid["inputRequests"]) == {"confirmation"}

        accepted = {
            "confirmation": {
                "action": "accept",
                "content": {"confirm": True},
            }
        }
        ack = _rpc(
            client,
            "tasks/update",
            4,
            {"taskId": created["taskId"], "inputResponses": accepted},
        )["result"]
        assert ack["resultType"] == "complete"
        terminal = _wait_terminal(client, created["taskId"], request_id=600)
        assert terminal["status"] == "completed"
        assert terminal["result"]["content"][0]["text"] == "Deleted safe.txt"

        late = _rpc(
            client,
            "tasks/update",
            5,
            {"taskId": created["taskId"], "inputResponses": accepted},
        )["result"]
        assert late["resultType"] == "complete"
        unchanged = _rpc(client, "tasks/get", 6, {"taskId": created["taskId"]})["result"]
        assert unchanged["status"] == "completed"
        assert unchanged["result"] == terminal["result"]


@pytest.mark.parametrize("action", ["decline", "cancel"])
def test_task_input_decline_and_cancel_are_not_accepted(fake_xtquant, tmp_path, action):
    app, _cfg, _health, _registry = create_app(_config(tmp_path))
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        created = _rpc(
            client,
            "tools/call",
            1,
            {"name": "confirm_delete", "arguments": {"filename": "safe.txt"}},
        )["result"]
        _wait_status(client, created["taskId"], "input_required")
        _rpc(
            client,
            "tasks/update",
            2,
            {
                "taskId": created["taskId"],
                "inputResponses": {"confirmation": {"action": action}},
            },
        )
        terminal = _wait_terminal(client, created["taskId"], request_id=650)
        assert terminal["status"] == "completed"
        assert terminal["result"]["content"][0]["text"] == "Deletion of safe.txt was not confirmed"


def test_task_input_partial_fulfillment_keeps_only_pending_key(fake_xtquant, tmp_path):
    app, _cfg, _health, _registry = create_app(_config(tmp_path))
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        created = _rpc(
            client,
            "tools/call",
            1,
            {"name": "multi_input", "arguments": {}},
        )["result"]
        waiting = _wait_status(client, created["taskId"], "input_required", request_id=700)
        assert set(waiting["inputRequests"]) == {"first", "second"}

        first = {"action": "accept", "content": {"confirm": True}}
        _rpc(
            client,
            "tasks/update",
            2,
            {"taskId": created["taskId"], "inputResponses": {"first": first}},
        )
        partial = _rpc(client, "tasks/get", 3, {"taskId": created["taskId"]})["result"]
        assert partial["status"] == "input_required"
        assert set(partial["inputRequests"]) == {"second"}

        # A retry of the already-consumed key is acknowledged without mutation.
        _rpc(
            client,
            "tasks/update",
            4,
            {"taskId": created["taskId"], "inputResponses": {"first": first}},
        )
        retried = _rpc(client, "tasks/get", 5, {"taskId": created["taskId"]})["result"]
        assert set(retried["inputRequests"]) == {"second"}

        _rpc(
            client,
            "tasks/update",
            6,
            {"taskId": created["taskId"], "inputResponses": {"second": first}},
        )
        terminal = _wait_terminal(client, created["taskId"], request_id=800)
        assert terminal["status"] == "completed"
        assert terminal["result"]["content"][0]["text"] == "Received 2 confirmations"


def test_mrtr_resolves_before_task_creation_then_uses_response(fake_xtquant, tmp_path):
    config = _config(tmp_path)
    app, _cfg, _health, _registry = create_app(config)
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        initial = _rpc(
            client,
            "tools/call",
            1,
            {"name": "test_tool_with_task", "arguments": {}},
        )["result"]
        assert initial["resultType"] == "input_required"
        assert "taskId" not in initial
        assert initial["inputRequests"]["user_name"]["method"] == "elicitation/create"

        with sqlite3.connect(config.effective_task_store) as connection:
            assert connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0

        unresolved = _rpc(
            client,
            "tools/call",
            11,
            {
                "name": "test_tool_with_task",
                "arguments": {},
                "inputResponses": {"unknown": {"action": "cancel"}},
            },
        )["result"]
        assert unresolved["resultType"] == "input_required"
        assert set(unresolved["inputRequests"]) == {"user_name"}
        assert "taskId" not in unresolved

        with sqlite3.connect(config.effective_task_store) as connection:
            assert connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0

        created = _rpc(
            client,
            "tools/call",
            2,
            {
                "name": "test_tool_with_task",
                "arguments": {},
                "inputResponses": {
                    "user_name": {
                        "action": "accept",
                        "content": {"name": "Alice"},
                    }
                },
            },
        )["result"]
        assert created["resultType"] == "task"
        assert "inputRequests" not in created
        assert "requestState" not in created

        terminal = _wait_terminal(client, created["taskId"], request_id=900)
        assert terminal["status"] == "completed"
        assert terminal["result"]["content"][0]["text"] == "Completed task for Alice"


def test_legacy_interactive_request_is_rejected_before_task_dispatch(fake_xtquant, tmp_path):
    app, config, _health, _registry = create_app(_config(tmp_path))
    accept = {"accept": "application/json, text/event-stream"}
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "legacy-task-test", "version": "1.0.0"},
        },
    }
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        response = client.post("/mcp", json=initialize, headers=accept)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32022
    assert "mcp-session-id" not in response.headers
    with sqlite3.connect(config.effective_task_store) as connection:
        assert connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0


def test_expired_input_task_cleans_live_runtime(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3", ttl_ms=100)
    extension = TasksExtension(store, task_tools=("interactive",))
    context = SimpleNamespace(
        protocol_version=VERSION,
        session=SimpleNamespace(
            client_capabilities=SimpleNamespace(extensions={TASKS_ID: {}}),
        ),
    )
    request = ElicitRequest(
        params=ElicitRequestFormParams(
            message="Wait for expiry",
            requested_schema={
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
        )
    )

    async def scenario():
        async def call_next(_ctx):
            await request_task_input({"expiring": request})
            return "unreachable"

        created = await extension.intercept_tool_call(
            CallToolRequestParams(name="interactive", arguments={}),
            context,
            call_next,
        )
        task_id = created["taskId"]
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            record = store.get(task_id)
            if record is not None and record.status == "input_required":
                break
            await asyncio.sleep(0.005)
        else:
            raise AssertionError("task did not request input before expiry")

        await asyncio.sleep(0.2)
        assert store.get(task_id) is None
        assert task_id not in extension._running
        assert task_id not in extension._interactions
        assert task_id not in extension._expiry_watchers

    asyncio.run(scenario())


def test_task_interaction_concurrent_delivery_unique_round_keys_and_transient_answers(tmp_path):
    path = tmp_path / "tasks.sqlite3"
    store = TaskStore(path)
    record = store.create(
        owner_digest="a" * 64,
        tool_name="interactive-test",
        required_scopes=(),
    )
    interaction = TaskInteraction(store, record.task_id)

    def request(message: str) -> ElicitRequest:
        return ElicitRequest(
            params=ElicitRequestFormParams(
                message=message,
                requested_schema={
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                },
            )
        )

    async def scenario():
        first_waiter = asyncio.create_task(interaction.request_input({"round-one": request("First value")}))
        await asyncio.sleep(0)
        assert store.get(record.task_id).status == "input_required"
        answer = {
            "round-one": {
                "action": "accept",
                "content": {"value": "sensitive-answer-024"},
            }
        }
        await asyncio.gather(interaction.submit(answer), interaction.submit(answer))
        assert await first_waiter == answer
        assert store.get(record.task_id).status == "working"

        second_waiter = asyncio.create_task(interaction.request_input({"round-two": request("Second value")}))
        await asyncio.sleep(0)
        await interaction.submit(
            {
                "round-two": {
                    "action": "accept",
                    "content": {"value": "second-answer"},
                }
            }
        )
        assert (await second_waiter)["round-two"]["content"]["value"] == "second-answer"

        with pytest.raises(MCPError) as exc_info:
            await interaction.request_input({"round-one": request("Reused")})
        assert exc_info.value.code == -32602

        for invalid_requests in (
            {},
            {f"key-{index}": request("Too many") for index in range(17)},
            {"oversized": request("x" * 70_000)},
        ):
            with pytest.raises(MCPError) as invalid_info:
                await interaction.request_input(invalid_requests)
            assert invalid_info.value.code == -32602
        await interaction.close()

    asyncio.run(scenario())
    assert b"sensitive-answer-024" not in path.read_bytes()
