from __future__ import annotations

from qmt_mcp_xtdata.reference_serializers import financial_groups, rows_from_any


def test_rows_from_any_dict_and_list():
    rows, truncated = rows_from_any({"a": 1})
    assert rows == [{"a": 1}]
    assert truncated is False

    rows, truncated = rows_from_any([{"a": 1}, {"a": 2}], limit=1)
    assert rows == [{"a": 1}]
    assert truncated is True


def test_financial_groups_nested():
    groups, truncated = financial_groups({"600000.SH": {"Income": [{"revenue": 1}]}})
    assert truncated is False
    assert groups == [{"code": "600000.SH", "table": "Income", "rows": [{"revenue": 1}]}]
