from __future__ import annotations

import pytest

from qmt_mcp_core.errors import McpCoreError
from qmt_mcp_xtdata import tools


def test_sector_members_retries_legacy_one_argument_signature(monkeypatch):
    calls = []

    def fake_call(name, *args):
        calls.append((name, args))
        if len(args) == 2:
            raise McpCoreError(
                "dependency",
                "xtdata.get_stock_list_in_sector failed: TypeError: takes 1 positional argument but 2 were given",
            )
        return ["510500.SH"]

    monkeypatch.setattr(tools, "_call_xtdata", fake_call)

    assert tools._call_sector_members("沪深ETF", -1) == ["510500.SH"]
    assert calls == [
        ("get_stock_list_in_sector", ("沪深ETF", -1)),
        ("get_stock_list_in_sector", ("沪深ETF",)),
    ]


def test_sector_members_does_not_mask_runtime_failures(monkeypatch):
    def fake_call(_name, *_args):
        raise McpCoreError("not_ready", "无法连接行情服务")

    monkeypatch.setattr(tools, "_call_xtdata", fake_call)

    with pytest.raises(McpCoreError, match="无法连接行情服务"):
        tools._call_sector_members("沪深ETF", -1)
