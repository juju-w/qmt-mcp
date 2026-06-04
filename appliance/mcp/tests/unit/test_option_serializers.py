from __future__ import annotations

from qmt_mcp_xtdata.option_serializers import option_codes, option_detail_record, quote_midpoint


def test_option_detail_normalizes_common_fields():
    rec = option_detail_record(
        "10000001.SHO",
        {"opt_code": "10000001.SHO", "undl_code": "510300.SH", "opt_type": "C", "strike_price": 4.0},
    )
    assert rec["code"] == "10000001.SHO"
    assert rec["underlying_code"] == "510300.SH"
    assert rec["option_type"] == "CALL"
    assert rec["exercise_price"] == 4.0


def test_option_codes_from_list_and_dicts():
    assert option_codes(["10000001.SHO"]) == ["10000001.SHO"]
    assert option_codes({"data": [{"code": "10000002.SHO"}]}) == ["10000002.SHO"]


def test_quote_midpoint():
    assert quote_midpoint({"bid_price": [1.0], "ask_price": [1.2]}) == 1.1
    assert quote_midpoint({"bid_price": [], "ask_price": []}) is None
