"""Unit tests for xttrade serializers with fake SDK objects (feature 004)."""

from __future__ import annotations

from types import SimpleNamespace

from qmt_mcp_xttrade.serializers import (
    asset_record,
    order_record,
    position_record,
    raw_m_fields,
    records,
    trade_record,
)


def test_raw_m_fields_collects_m_prefixed():
    obj = SimpleNamespace(m_dCash=100.0, m_strAccountID="111", other=1)
    raw = raw_m_fields(obj)
    assert raw == {"m_dCash": 100.0, "m_strAccountID": "111"}
    assert "other" not in raw


def test_asset_record_maps_known_fields():
    obj = SimpleNamespace(
        m_strAccountID="111111",
        m_dCash=1000.0,
        m_dFrozenCash=50.0,
        m_dMarketValue=8000.0,
        m_dTotalAsset=9000.0,
    )
    rec = asset_record(obj)
    assert rec["account_id"] == "111111"
    assert rec["cash"] == 1000.0
    assert rec["total_asset"] == 9000.0
    assert rec["raw"]["m_dMarketValue"] == 8000.0


def test_position_record_falls_back_on_code_attr():
    # uses m_strStockCode (not m_strInstrumentID) — mapper should still find it
    obj = SimpleNamespace(m_strStockCode="600000.SH", m_nVolume=100, m_nCanUseVolume=100)
    rec = position_record(obj)
    assert rec["code"] == "600000.SH"
    assert rec["volume"] == 100


def test_order_and_trade_records():
    order = SimpleNamespace(m_nOrderID=7, m_strStockCode="000001.SZ", m_nOrderStatus=50, m_nOrderVolume=200)
    o = order_record(order)
    assert o["order_id"] == 7
    assert o["order_status"] == 50

    trade = SimpleNamespace(m_strTradeID="t1", m_dPrice=10.5, m_nVolume=100, m_strStockCode="000001.SZ")
    t = trade_record(trade)
    assert t["trade_id"] == "t1"
    assert t["traded_price"] == 10.5
    assert t["traded_volume"] == 100


def test_records_handles_list_single_none():
    assert records(None, asset_record) == []
    one = SimpleNamespace(m_dCash=1.0)
    assert len(records(one, asset_record)) == 1
    assert len(records([one, one], asset_record)) == 2
