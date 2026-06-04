"""Health and capability state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .audit import now_iso
from .config import CoreConfig


@dataclass
class ToolFamilyCapability:
    family: str
    state: str
    reason: str
    tools: list[str] = field(default_factory=list)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "state": self.state,
            "reason": self.reason,
            "tools": list(self.tools),
            "updated_at": self.updated_at,
        }


class HealthState:
    def __init__(self, config: CoreConfig):
        self.config = config
        self.server = "live"
        self.broker_config = "loaded" if config.broker_id != "unknown" else "missing"
        self.xtquant_import = "unknown"
        self.xtdata = "disabled"
        self.xttrade = "not_authorized"
        self.audit = "unknown"
        # Live readiness (feature 005). Updated by the background probe/connector.
        self.qmt_login = "unknown"  # unknown | awaiting | logged_in
        self.last_probe_at = ""
        self.last_error = ""
        # Optional DB persistence (feature 012). disabled | connected | degraded | error
        self.database = "disabled"
        self.db_domains: list[str] = []
        self.families: dict[str, ToolFamilyCapability] = {}
        self.set_family("core", "enabled", "core tools available", [])
        self.set_family("xttrade_query", "not_authorized", "broker/account permission not available", [])
        self.set_family("xttrade_write", "disabled", "write tools are out of scope", [])
        self.set_family("portfolio", "disabled", "portfolio analysis not registered", [])

    def set_family(self, family: str, state: str, reason: str, tools: list[str] | None = None) -> None:
        self.families[family] = ToolFamilyCapability(family, state, reason, tools or [])

    def update_family_tools(self, family: str, tools: list[str]) -> None:
        cap = self.families.get(family)
        if cap:
            cap.tools = list(tools)

    def readiness(self) -> dict[str, Any]:
        """Structured readiness snapshot (005). Reported, never flips `ok`."""
        return {
            "qmt_login": self.qmt_login,
            "xtdata_state": self.xtdata,
            "trader_state": self.xttrade,
            "last_probe_at": self.last_probe_at,
            "last_error": self.last_error,
        }

    def to_dict(self) -> dict[str, Any]:
        # `ok` reflects server/audit health only; readiness states (awaiting_login,
        # not_authorized, ...) are reported but do not flip `ok` to false — the MCP
        # serves before QMT login (constitution V).
        ok = self.server != "error" and self.audit != "error"
        return {
            "ok": ok,
            "server": self.server,
            "transport": self.config.transport,
            "broker_config": self.broker_config,
            "xtquant_import": self.xtquant_import,
            "xtdata": self.xtdata,
            "xttrade": self.xttrade,
            "audit": self.audit,
            "database": self.database,
            "db_domains": list(self.db_domains),
            "readiness": self.readiness(),
            "tool_families": [cap.to_dict() for cap in self.families.values()],
        }

    def livez(self) -> dict[str, Any]:
        """Unauthenticated liveness — no account/broker/secret detail (005)."""
        return {"ok": self.server != "error", "server": self.server}

    def capabilities(self) -> dict[str, Any]:
        return {
            "ok": True,
            "transport": self.config.transport,
            "tool_families": [cap.to_dict() for cap in self.families.values()],
        }
