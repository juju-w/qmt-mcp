from __future__ import annotations

from qmt_mcp_screening.sources import ScreeningSource


class FakeXtData:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []

    def __call__(self, name: str, *args):
        self.calls.append((name, args))
        if name == "get_market_data_ex":
            fields, codes, _period, _start, _end, _count, dividend_type, *_rest = args
            return {
                code: {
                    field: {
                        "20240102": 10.0 if field == "close" else 100.0,
                        "20240103": 11.0 if field == "close" else 110.0,
                        "20240104": 12.0 if field == "close" else 120.0,
                    }
                    for field in fields
                }
                for code in codes
            } | {"_dividend_type": dividend_type}
        if name == "get_full_tick":
            return {
                code: {
                    "time": 1_000_000,
                    "lastPrice": 10.0,
                    "bidPrice": [9.99],
                    "askPrice": [10.01],
                }
                for code in args[0]
            }
        if name == "get_financial_data":
            codes, tables, *_rest = args
            return {
                code: {
                    table: [{"report_date": "20231231", "announce_time": "20240320", "revenue": 100}]
                    for table in tables
                }
                for code in codes
            }
        raise AssertionError(name)


def test_daily_bars_are_batched_by_50_and_keep_adjustment_separate():
    fake = FakeXtData()
    source = ScreeningSource(fake)
    codes = [f"{index:06d}.SH" for index in range(101)]

    adjusted = source.daily_bars(codes, count=260, dividend_type="front_ratio", completed_through="20240103")
    unadjusted = source.daily_bars(codes[:1], count=1, dividend_type="none")

    market_calls = [call for call in fake.calls if call[0] == "get_market_data_ex"]
    assert [len(call[1][1]) for call in market_calls] == [50, 50, 1, 1]
    assert [call[1][6] for call in market_calls] == ["front_ratio", "front_ratio", "front_ratio", "none"]
    assert len(adjusted[codes[0]]) == 2
    assert adjusted[codes[0]][-1]["time"] == "20240103"
    assert unadjusted[codes[0]][0]["close"] == 10.0


def test_snapshots_are_batched_and_fresh_two_sided_quotes_are_normalized():
    fake = FakeXtData()
    source = ScreeningSource(fake)
    codes = [f"{index:06d}.SH" for index in range(51)]

    snapshots = source.snapshots(codes, captured_epoch_ms=1_003_000, max_age_seconds=5)

    assert [len(call[1][0]) for call in fake.calls] == [50, 1]
    assert snapshots[codes[0]]["bid1"] == 9.99
    assert snapshots[codes[0]]["ask1"] == 10.01
    assert snapshots[codes[0]]["quote_age_seconds"] == 3
    assert snapshots[codes[0]]["missing_reason"] is None


def test_financial_reads_are_announce_time_batched_by_200():
    fake = FakeXtData()
    source = ScreeningSource(fake)
    codes = [f"{index:06d}.SH" for index in range(401)]

    result = source.financial_tables(codes, ["Income", "Balance"], end_time="20241231")

    financial_calls = [call for call in fake.calls if call[0] == "get_financial_data"]
    assert [len(call[1][0]) for call in financial_calls] == [200, 200, 1]
    assert all(call[1][-1] == "announce_time" for call in financial_calls)
    assert result[codes[0]]["Income"][0]["revenue"] == 100


def test_malformed_broker_shapes_degrade_to_empty_normalized_records():
    source = ScreeningSource(lambda _name, *_args: "unexpected")
    assert source.daily_bars(["600001.SH"], count=20)["600001.SH"] == ()
    assert source.snapshots(["600001.SH"])["600001.SH"]["missing_reason"] == "missing_source_field"
    assert source.financial_tables(["600001.SH"], ["Income"])["600001.SH"] == {}


def test_stale_locked_crossed_and_one_sided_quotes_are_never_zero_spread():
    payloads = {
        "STALE.SH": {"time": 900_000, "bidPrice": [9.99], "askPrice": [10.01]},
        "LOCKED.SH": {"time": 1_000_000, "bidPrice": [10.0], "askPrice": [10.0]},
        "CROSSED.SH": {"time": 1_000_000, "bidPrice": [10.01], "askPrice": [10.0]},
        "ONE.SH": {"time": 1_000_000, "bidPrice": [10.0], "askPrice": []},
    }
    source = ScreeningSource(lambda name, _codes: payloads if name == "get_full_tick" else {})
    rows = source.snapshots(list(payloads), captured_epoch_ms=1_003_000, max_age_seconds=5)

    assert rows["STALE.SH"]["missing_reason"] == "stale_snapshot"
    assert rows["LOCKED.SH"]["missing_reason"] == "invalid_source_value"
    assert rows["CROSSED.SH"]["missing_reason"] == "invalid_source_value"
    assert rows["ONE.SH"]["missing_reason"] == "one_sided_quote"


def test_batch_source_errors_are_bounded_and_typed_instead_of_crashing_the_adapter():
    def failing(name, *_args):
        raise RuntimeError(f"fixture {name} failure")

    source = ScreeningSource(failing)
    bars = source.daily_bars(["600001.SH"], count=20)
    snapshots = source.snapshots(["600001.SH"])
    financial = source.financial_tables(["600001.SH"], ["Income"])

    assert bars["600001.SH"][0]["_source_error"] == "RuntimeError"
    assert snapshots["600001.SH"]["missing_reason"] == "source_error"
    assert financial["600001.SH"]["_source_error"][0]["error_type"] == "RuntimeError"
    assert [error["source"] for error in source.errors] == ["daily_bars", "snapshot", "financial"]


def test_quote_from_a_different_market_session_is_marked_stale():
    source = ScreeningSource(
        lambda name, _codes: {"513500.SH": {"time": "20260815150000", "bidPrice": [10.0], "askPrice": [10.01]}}
        if name == "get_full_tick"
        else {}
    )
    snapshot = source.snapshots(
        ["513500.SH"],
        captured_epoch_ms=1_000_000,
        max_age_seconds=10**12,
        expected_session="20260816",
    )["513500.SH"]
    assert snapshot["session_mismatch"] is True
    assert snapshot["missing_reason"] == "stale_snapshot"


def test_epoch_quote_time_is_not_mistaken_for_a_calendar_session():
    epoch_ms = 1_786_900_000_000
    source = ScreeningSource(
        lambda name, _codes: {"510500.SH": {"time": epoch_ms, "bidPrice": [10.0], "askPrice": [10.01]}}
        if name == "get_full_tick"
        else {}
    )
    snapshot = source.snapshots(
        ["510500.SH"],
        captured_epoch_ms=epoch_ms + 1_000,
        expected_session="20260817",
    )["510500.SH"]
    assert snapshot["quote_age_seconds"] == 1
    assert snapshot["session_mismatch"] is False
    assert snapshot["missing_reason"] is None
