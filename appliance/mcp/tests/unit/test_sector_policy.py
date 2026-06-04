from __future__ import annotations

import pytest

from qmt_mcp_core.errors import McpCoreError
from qmt_mcp_xtdata.sector_policy import parse_prefixes, require_confirm, require_managed_sector


def test_sector_policy_prefixes():
    prefixes = parse_prefixes("MCP/,AI/")
    assert require_managed_sector("MCP/Test", prefixes) == "MCP/Test"
    with pytest.raises(McpCoreError):
        require_managed_sector("沪深A股", prefixes)
    with pytest.raises(McpCoreError):
        require_managed_sector("User/Test", prefixes)


def test_confirm_required():
    with pytest.raises(McpCoreError):
        require_confirm(False)
    require_confirm(True)
