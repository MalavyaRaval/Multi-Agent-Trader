from __future__ import annotations

import pandas as pd
import pytest

from observability.data_quality import validate_market_data


def _valid_bars(n=100):
    now = pd.Timestamp.now(tz="UTC")
    ts = [now - pd.Timedelta(days=n - i) for i in range(n)]
    closes = [100.0 + i * 0.1 for i in range(n)]
    return pd.DataFrame(
        {
            "timestamp": ts,
            "symbol": ["AAPL"] * n,
            "open": [c - 0.5 for c in closes],
            "high": [c + 1 for c in closes],
            "low": [c - 1 for c in closes],
            "close": closes,
            "volume": [1000 + i for i in range(n)],
        }
    )


def test_valid_data_passes():
    report = validate_market_data(_valid_bars(), "AAPL", min_bars=60)
    assert report["status"] == "PASS"
    assert report["failed_checks"] == []
    assert report["bars"] == 100


def test_empty_dataframe_fails():
    report = validate_market_data(pd.DataFrame(), "AAPL")
    assert report["status"] == "FAIL"
    assert "data_exists" in report["failed_checks"]


def test_none_fails():
    report = validate_market_data(None, "AAPL")
    assert report["status"] == "FAIL"
    assert "data_exists" in report["failed_checks"]


def test_too_few_bars_fails():
    report = validate_market_data(_valid_bars(10), "AAPL", min_bars=60)
    assert "minimum_bars" in report["failed_checks"]


def test_duplicate_timestamps_detected():
    df = _valid_bars()
    df.loc[5, "timestamp"] = df.loc[4, "timestamp"]
    report = validate_market_data(df, "AAPL", min_bars=60)
    assert "no_duplicate_timestamps" in report["failed_checks"]
    assert report["duplicates"] == 1


def test_unordered_timestamps_detected():
    df = _valid_bars()
    df.loc[10, "timestamp"] = df.loc[0, "timestamp"] - pd.Timedelta(days=1)
    report = validate_market_data(df, "AAPL", min_bars=60)
    assert "timestamps_ordered" in report["failed_checks"]


def test_high_below_low_detected():
    df = _valid_bars()
    df.loc[3, "high"] = df.loc[3, "low"] - 5
    report = validate_market_data(df, "AAPL", min_bars=60)
    assert "high_gte_low" in report["failed_checks"]


def test_negative_volume_detected():
    df = _valid_bars()
    df.loc[2, "volume"] = -5
    report = validate_market_data(df, "AAPL", min_bars=60)
    assert "volume_non_negative" in report["failed_checks"]


def test_wrong_symbol_detected():
    report = validate_market_data(_valid_bars(), "MSFT", min_bars=60)
    assert "correct_symbol" in report["failed_checks"]


def test_stale_data_detected_when_threshold_set():
    report = validate_market_data(_valid_bars(), "AAPL", min_bars=60, max_freshness_seconds=60)
    assert "freshness" in report["failed_checks"]
    assert report["freshness_seconds"] is not None


def test_freshness_not_checked_without_threshold():
    report = validate_market_data(_valid_bars(), "AAPL", min_bars=60)
    assert "freshness" not in report["failed_checks"]
    assert report["freshness_seconds"] is not None


def test_missing_ohlcv_columns_fail_gracefully():
    df = _valid_bars().drop(columns=["volume"])
    report = validate_market_data(df, "AAPL", min_bars=60)
    assert "volume_non_negative" in report["failed_checks"]
    assert report["status"] == "FAIL"


def test_non_positive_close_detected():
    df = _valid_bars()
    df.loc[7, "close"] = 0.0
    report = validate_market_data(df, "AAPL", min_bars=60)
    assert "close_valid" in report["failed_checks"]


def test_gap_analysis_checked_for_daily_bars_with_no_large_gap():
    report = validate_market_data(_valid_bars(), "AAPL", min_bars=60)
    assert report["gap_analysis"]["checked"] is True
    assert report["gap_analysis"]["large_gap_detected"] is False
    assert report["gap_analysis"]["max_gap_days"] == pytest.approx(1.0, abs=0.01)
    # Informational only -- never flips overall PASS/FAIL status.
    assert report["status"] == "PASS"


def test_gap_analysis_flags_large_gap_in_daily_bars():
    df = _valid_bars()
    # Push everything after index 50 out by 10 days to simulate a data outage.
    df.loc[50:, "timestamp"] = df.loc[50:, "timestamp"] + pd.Timedelta(days=10)
    report = validate_market_data(df, "AAPL", min_bars=60)
    assert report["gap_analysis"]["checked"] is True
    assert report["gap_analysis"]["large_gap_detected"] is True
    assert report["gap_analysis"]["max_gap_days"] > 5.0
    # Still informational only -- a gap alone does not fail the report.
    assert "minimum_bars" not in report["failed_checks"]


def test_gap_analysis_skipped_for_intraday_bars():
    now = pd.Timestamp.now(tz="UTC")
    n = 100
    df = pd.DataFrame(
        {
            "timestamp": [now - pd.Timedelta(minutes=(n - i)) for i in range(n)],
            "symbol": ["AAPL"] * n,
            "open": [100.0] * n,
            "high": [101.0] * n,
            "low": [99.0] * n,
            "close": [100.0] * n,
            "volume": [1000] * n,
        }
    )
    report = validate_market_data(df, "AAPL", min_bars=60)
    assert report["gap_analysis"]["checked"] is False
    assert report["gap_analysis"]["max_gap_days"] is None


def test_gap_analysis_present_but_unchecked_when_no_timestamps():
    df = _valid_bars().drop(columns=["timestamp"])
    report = validate_market_data(df, "AAPL", min_bars=60)
    assert report["gap_analysis"] == {"checked": False, "max_gap_days": None, "large_gap_detected": False}
