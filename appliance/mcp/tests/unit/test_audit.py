"""Unit tests for the append-only JSONL audit sink."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qmt_mcp_core.audit import JsonlAuditSink, request_id, sanitize_args
from qmt_mcp_core.errors import McpCoreError


def test_request_id_prefix():
    assert request_id().startswith("req_")


def test_sanitize_args_redacts_secret_keys():
    clean = sanitize_args({"token": "abc", "password": "x", "code": "600000.SH"})
    assert clean["token"] == "<redacted>"
    assert clean["password"] == "<redacted>"
    assert clean["code"] == "600000.SH"


def test_sanitize_args_summarizes_collections():
    clean = sanitize_args({"codes": ["a", "b", "c", "d", "e", "f", "g"]})
    assert clean["codes"]["count"] == 7
    assert clean["codes"]["truncated"] is True
    assert len(clean["codes"]["sample"]) == 5


def test_initialize_creates_parent_and_file(tmp_audit_path):
    sink = JsonlAuditSink(tmp_audit_path, "acme")
    sink.initialize()
    assert Path(tmp_audit_path).exists()


def test_append_writes_jsonl_record(tmp_audit_path):
    sink = JsonlAuditSink(tmp_audit_path, "acme")
    sink.initialize()
    sink.append(
        request_id_value="req_1",
        tool="qmt_health",
        family="core",
        args_summary={"token": "leak"},
        outcome="ok",
        latency_ms=12,
    )
    lines = Path(tmp_audit_path).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["tool"] == "qmt_health"
    assert record["broker_id"] == "acme"
    assert record["args_summary"]["token"] == "<redacted>"
    assert record["latency_ms"] == 12


def test_append_is_ordered(tmp_audit_path):
    sink = JsonlAuditSink(tmp_audit_path, "acme")
    sink.initialize()
    for i in range(3):
        sink.append(
            request_id_value=f"req_{i}",
            tool="t",
            family="core",
            args_summary=None,
            outcome="ok",
            latency_ms=i,
        )
    lines = Path(tmp_audit_path).read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["request_id"] for line in lines] == ["req_0", "req_1", "req_2"]


def test_unwritable_path_raises_persistence(tmp_path):
    # A path whose parent is a file, not a directory -> mkdir fails.
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    sink = JsonlAuditSink(str(blocker / "audit.jsonl"), "acme")
    with pytest.raises(McpCoreError) as exc:
        sink.initialize()
    assert exc.value.error_type == "persistence"
