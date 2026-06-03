#!/usr/bin/env python
"""QMT MCP launcher.

The executable entrypoint stays at this path for Wine/autostart compatibility.
The implementation lives in qmt_mcp_core and registers explicit, capability-
gated tool families. No vendored tool package is mounted wholesale.
"""

from __future__ import annotations

from qmt_mcp_core.app import main


def filter_trade_tools() -> list[str]:
    """Build-time compatibility smoke: 002 core exposes no trade/write tools."""
    return []


if __name__ == "__main__":
    main()
