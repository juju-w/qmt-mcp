"""Unit coverage for dependency-light durable MCP task state."""

from __future__ import annotations

import os
import sqlite3

from qmt_mcp_core.task_store import TaskStore

OWNER = "a" * 64


def test_create_complete_and_reload_without_sensitive_inputs(tmp_path):
    path = tmp_path / "cache" / "tasks.sqlite3"
    store = TaskStore(path, ttl_ms=60_000, poll_interval_ms=250, max_retained=10)
    record = store.create(
        owner_digest=OWNER,
        tool_name="qmt_xtdata_download_history",
        required_scopes=("qmt:read", "qmt:market"),
    )

    assert record.status == "working"
    assert record.task_id.startswith("tsk_")
    assert record.to_wire()["pollIntervalMs"] == 250
    assert record.to_wire()["resultType"] == "complete"
    assert record.to_wire(created=True)["resultType"] == "task"
    assert store.complete(record.task_id, {"content": [], "isError": False})

    reloaded = TaskStore(path, ttl_ms=60_000, poll_interval_ms=250, max_retained=10)
    completed = reloaded.get(record.task_id)
    assert completed is not None
    assert completed.status == "completed"
    assert completed.result == {"content": [], "isError": False}
    assert completed.required_scopes == ("qmt:market", "qmt:read")

    with sqlite3.connect(path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(tasks)")}
    assert (
        not {
            "arguments",
            "token",
            "access_token",
            "authorization",
            "client_id",
            "issuer",
            "subject",
        }
        & columns
    )
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600


def test_terminal_state_is_immutable_under_late_updates(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    task = store.create(owner_digest=OWNER, tool_name="qmt_long", required_scopes=("qmt:read",))
    assert store.cancel(task.task_id)
    assert not store.complete(task.task_id, {"content": [{"type": "text", "text": "late"}]})
    assert not store.fail(task.task_id, {"code": -32603, "message": "late"})
    assert store.get(task.task_id).status == "cancelled"


def test_restart_recovery_fails_only_active_tasks(tmp_path):
    path = tmp_path / "tasks.sqlite3"
    store = TaskStore(path)
    working = store.create(owner_digest=OWNER, tool_name="qmt_working", required_scopes=())
    waiting = store.create(owner_digest=OWNER, tool_name="qmt_waiting", required_scopes=())
    done = store.create(owner_digest=OWNER, tool_name="qmt_done", required_scopes=())
    assert store.request_input(waiting.task_id, {"confirm": {"type": "boolean"}})
    assert store.complete(done.task_id, {"content": []})

    restarted = TaskStore(path)
    assert restarted.recover_interrupted() == 2
    for task_id in (working.task_id, waiting.task_id):
        record = restarted.get(task_id)
        assert record.status == "failed"
        assert record.error["code"] == -32603
    assert restarted.get(done.task_id).status == "completed"


def test_expiry_and_terminal_retention_do_not_prune_active(tmp_path):
    now = [1_000_000]
    store = TaskStore(
        tmp_path / "tasks.sqlite3",
        ttl_ms=1000,
        max_retained=1,
        clock_ms=lambda: now[0],
    )
    first = store.create(owner_digest=OWNER, tool_name="qmt_first", required_scopes=())
    now[0] += 1
    active = store.create(owner_digest=OWNER, tool_name="qmt_active", required_scopes=())
    now[0] += 1
    second = store.create(owner_digest=OWNER, tool_name="qmt_second", required_scopes=())
    assert store.complete(first.task_id, {"value": 1})
    now[0] += 1
    assert store.complete(second.task_id, {"value": 2})

    assert store.get(first.task_id) is None
    assert store.get(second.task_id) is not None
    assert store.get(active.task_id).status == "working"

    now[0] += 1000
    assert store.get(active.task_id) is None
    assert store.prune() >= 1


def test_malformed_ids_and_input_resume_are_bounded(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    assert store.get("") is None
    assert store.get("tsk_" + "x" * 1000) is None
    task = store.create(owner_digest=OWNER, tool_name="qmt_waiting", required_scopes=())
    assert store.request_input(task.task_id, {"confirmation": {"type": "boolean"}})
    waiting = store.get(task.task_id)
    assert waiting.status == "input_required"
    assert "inputRequests" in waiting.to_wire()
    assert "inputRequests" not in waiting.to_wire(created=True)
    assert store.resume(task.task_id)
    assert store.get(task.task_id).status == "working"
