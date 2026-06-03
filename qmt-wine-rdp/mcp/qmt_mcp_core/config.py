"""Runtime config loading for the MCP core."""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from pathlib import Path

from .errors import McpCoreError

DEFAULT_MCP_ENV = Path("/opt/qmt-mcp/mcp.env")


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        try:
            parsed = shlex.split(value, posix=True)
            result[key] = parsed[0] if parsed else ""
        except ValueError:
            result[key] = value.strip().strip("'\"")
    return result


def _merged_env(mcp_env_path: Path = DEFAULT_MCP_ENV) -> dict[str, str]:
    merged = _read_env_file(mcp_env_path)
    merged.update({k: v for k, v in os.environ.items()})
    return merged


def _is_loopback(host: str) -> bool:
    return host in {"127.0.0.1", "localhost", "::1"}


@dataclass(frozen=True)
class CoreConfig:
    broker_id: str
    broker_name: str
    xtquant_dir_win: str
    userdata_win: str
    mcp_mode: str
    token: str
    host: str
    port: int
    transport: str
    audit_path: str
    worker_limit: int
    allow_unauth_loopback: bool
    enable_xtdata: bool
    test_mode: bool

    @property
    def auth_required(self) -> bool:
        return bool(self.token)

    def validate_security(self) -> None:
        if self.transport not in {"streamable-http", "http", "sse"}:
            raise McpCoreError(
                "config",
                "invalid QMT_MCP_TRANSPORT",
                {"transport": self.transport, "allowed": ["streamable-http", "http", "sse"]},
            )
        if not self.token and not (_is_loopback(self.host) and self.allow_unauth_loopback):
            raise McpCoreError(
                "auth",
                "QMT_MCP_TOKEN is required when MCP is bound to a non-loopback host",
                {"host": self.host},
            )


def load_config(mcp_env_path: Path = DEFAULT_MCP_ENV) -> CoreConfig:
    env = _merged_env(mcp_env_path)
    host = env.get("MCP_HOST", "0.0.0.0")
    cfg = CoreConfig(
        broker_id=env.get("QMT_BROKER_ID", "unknown"),
        broker_name=env.get("QMT_BROKER_NAME", ""),
        xtquant_dir_win=env.get("QMT_XTQUANT_DIR_WIN", ""),
        userdata_win=env.get("QMT_USERDATA_WIN", ""),
        mcp_mode=env.get("QMT_MCP_MODE", "readonly") or "readonly",
        token=env.get("QMT_MCP_TOKEN", "").strip(),
        host=host,
        port=int(env.get("MCP_PORT", "8765")),
        transport=env.get("QMT_MCP_TRANSPORT", "streamable-http") or "streamable-http",
        audit_path=env.get("QMT_MCP_AUDIT_PATH", "/broker/logs/mcp-audit.jsonl"),
        worker_limit=max(1, int(env.get("QMT_MCP_WORKERS", "4"))),
        allow_unauth_loopback=env.get("QMT_MCP_ALLOW_UNAUTH_LOOPBACK", "0") == "1",
        enable_xtdata=env.get("QMT_MCP_ENABLE_XTDATA", "1") != "0",
        test_mode=env.get("QMT_MCP_TEST_MODE", "0") == "1",
    )
    cfg.validate_security()
    return cfg
