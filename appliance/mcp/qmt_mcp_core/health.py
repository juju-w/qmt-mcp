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
        self.families: dict[str, ToolFamilyCapability] = {}
        self.set_family("core", "enabled", "core tools available", [])
        self.set_family("xttrade_query", "not_authorized", "broker/account permission not available", [])
        self.set_family("xttrade_write", "disabled", "write tools are out of scope", [])

    def set_family(self, family: str, state: str, reason: str, tools: list[str] | None = None) -> None:
        self.families[family] = ToolFamilyCapability(family, state, reason, tools or [])

    def update_family_tools(self, family: str, tools: list[str]) -> None:
        cap = self.families.get(family)
        if cap:
            cap.tools = list(tools)

    def to_dict(self) -> dict[str, Any]:
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
            "tool_families": [cap.to_dict() for cap in self.families.values()],
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "ok": True,
            "transport": self.config.transport,
            "tool_families": [cap.to_dict() for cap in self.families.values()],
        }
