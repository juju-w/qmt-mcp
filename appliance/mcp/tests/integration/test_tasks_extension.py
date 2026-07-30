"""Stable MCP Tasks extension lifecycle through the real ASGI transport."""

from __future__ import annotations

import json
import time

import pytest

pytest.importorskip("mcp")

pytestmark = pytest.mark.integration

from starlette.testclient import TestClient  # noqa: E402

from qmt_mcp_core.app import create_app  # noqa: E402
from qmt_mcp_core.config import CoreConfig  # noqa: E402

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
