"""Smoke checks for the MCP core that do not require QMT login."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from .config import CoreConfig
from .app import create_app


def make_smoke_config() -> CoreConfig:
    audit_path = str(Path(tempfile.gettempdir()) / f"qmt-mcp-audit-smoke-{os.getpid()}.jsonl")
    return CoreConfig(
        broker_id="smoke",
        broker_name="",
        xtquant_dir_win="",
        userdata_win="",
        mcp_mode="readonly",
        token="smoke-token",
        host="127.0.0.1",
        port=8765,
        audit_path=audit_path,
        worker_limit=2,
        allow_unauth_loopback=False,
        enable_xtdata=False,
        test_mode=True,
    )


def main() -> None:
    config = make_smoke_config()
    _, _, health, registry = create_app(config)
    registry.assert_no_write_tools()
    assert "qmt_health" in registry.tool_names()
    assert "qmt_capabilities" in registry.tool_names()
    payload = health.to_dict()
    assert payload["tool_families"]

    # Exercise wrapped tool call by reaching into the explicit registry.
    tool = registry._tools["qmt_health"]["callable"]  # noqa: SLF001 - smoke only
    result = tool()
    assert result["server"] == "live"
    time.sleep(0.05)
    lines = Path(config.audit_path).read_text(encoding="utf-8").splitlines()
    assert lines
    record = json.loads(lines[-1])
    assert record["tool"] == "qmt_health"
    assert "smoke-token" not in lines[-1]
    print("qmt_mcp_core smoke OK")


if __name__ == "__main__":
    main()
