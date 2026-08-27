"""
observability/data_quality.py

Phase 5 of PHASES_PLAN.md — Data Quality System.

An API returning HTTP 200 does not mean the data is usable. This module runs
a fixed checklist against a bars DataFrame (existence, symbol match, bar
count, timestamp validity/ordering/duplicates, OHLC sanity, non-negative
volume, freshness) and returns a structured report. It never raises -- a
FAIL is a valid, expected outcome the caller decides what to do with.

This is deliberately separate from the lighter-weight per-agent
"data_quality" status strings already used across agents/*.py (e.g.
TechnicalAgent's "complete"/"partial"/"unavailable") -- those describe
whether an agent *has enough to compute with*, while this module describes
whether the underlying market data *itself* is statistically trustworthy.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

CHECK_NAMES = [
    "data_exists",
    "correct_symbol",
    "minimum_bars",
    "timestamps_valid",
    "timestamps_ordered",
    "no_duplicate_timestamps",
    "open_valid",
    "high_gte_low",
    "close_valid",
    "volume_non_negative",
    "freshness",
]

# PHASES_PLAN.md Phase 14 -- missing-bar detection. Reported informationally
# only (see `gap_analysis` below); it never affects `status`/`checks`. A hard
# FAIL here would need a real market-holiday calendar to avoid flagging
# ordinary long weekends as data problems, which this module does not have.
_GAP_THRESHOLD_DAYS = 5.0


def validate_market_data(
    df: Optional[pd.DataFrame],
    symbol: str,
    *,
    min_bars: int = 60,
    max_freshness_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """Validate a bars DataFrame against the Phase 5 checklist. Never raises."""
    checks: Dict[str, bool] = {}
    errors: List[str] = []
    symbol = (symbol or "").upper()

    def fail(name: str, message: str) -> None:
        checks[name] = False
        errors.append(message)

    def ok(name: str) -> None:
        checks[name] = True

    if df is None or df.empty:
        fail("data_exists", "No bars were returned.")
        for name in CHECK_NAMES[1:]:
            checks[name] = False
        return _finalize(checks, errors, bars=0, missing_values=0, duplicates=0, freshness_seconds=None, gap_analysis=None)
    ok("data_exists")

    bars = len(df)

    if "symbol" in df.columns:
        symbols_seen = {str(s).upper() for s in df["symbol"].dropna().unique()}
        if symbols_seen and symbols_seen != {symbol}:
            fail("correct_symbol", f"Bars contain unexpected symbol(s): {sorted(symbols_seen)}")
        else:
            ok("correct_symbol")
    else:
        ok("correct_symbol")  # single-symbol frame, nothing to cross-check

    if bars < min_bars:
        fail("minimum_bars", f"Received {bars} bars; at least {min_bars} required.")
    else:
        ok("minimum_bars")

    missing_values = int(df.isna().sum().sum())

    timestamps = None
    if "timestamp" in df.columns:
        timestamps = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    elif isinstance(df.index, pd.DatetimeIndex):
        timestamps = pd.Series(df.index)

    duplicates = 0
    freshness_seconds: Optional[float] = None
    gap_analysis: Dict[str, Any] = {"checked": False, "max_gap_days": None, "large_gap_detected": False}

    if timestamps is None:
        fail("timestamps_valid", "No timestamp column or DatetimeIndex found.")
        fail("timestamps_ordered", "Cannot check ordering without timestamps.")
        fail("no_duplicate_timestamps", "Cannot check duplicates without timestamps.")
        checks["freshness"] = max_freshness_seconds is None
    else:
        ts = pd.Series(timestamps).reset_index(drop=True)
        if ts.isna().any():
            fail("timestamps_valid", "One or more timestamps could not be parsed.")
        else:
            ok("timestamps_valid")

        valid_ts = ts.dropna()
        if len(valid_ts) and not valid_ts.is_monotonic_increasing:
            fail("timestamps_ordered", "Timestamps are not in ascending order.")
        else:
            ok("timestamps_ordered")

        duplicates = int(valid_ts.duplicated().sum())
        if duplicates:
            fail("no_duplicate_timestamps", f"{duplicates} duplicate timestamp(s) found.")
        else:
            ok("no_duplicate_timestamps")

        sorted_ts = valid_ts.sort_values()
        deltas = sorted_ts.diff().dropna()
        if len(deltas) and deltas.median() >= pd.Timedelta(hours=20):
            # Coarse enough (daily-or-slower) that a multi-day gap is
            # meaningful rather than an ordinary overnight/weekend break.
            max_gap_days = float(deltas.max().total_seconds() / 86400.0)
            gap_analysis = {
                "checked": True,
                "max_gap_days": round(max_gap_days, 2),
                "large_gap_detected": max_gap_days > _GAP_THRESHOLD_DAYS,
            }

        if len(valid_ts):
            latest = valid_ts.max()
            if latest.tzinfo is None:
                latest = latest.tz_localize("UTC")
            freshness_seconds = (pd.Timestamp.now(tz="UTC") - latest).total_seconds()

        if max_freshness_seconds is None:
            checks["freshness"] = True
        elif freshness_seconds is None:
            fail("freshness", "No valid timestamp to measure freshness against.")
        elif freshness_seconds > max_freshness_seconds:
            fail("freshness", f"Latest bar is {freshness_seconds:.0f}s old; limit is {max_freshness_seconds:.0f}s.")
        else:
            ok("freshness")

    for col, check_name in (("open", "open_valid"), ("close", "close_valid")):
        if col not in df.columns:
            fail(check_name, f"Missing '{col}' column.")
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        if series.isna().any():
            fail(check_name, f"'{col}' contains non-numeric or missing values.")
        elif not (series > 0).all():
            fail(check_name, f"'{col}' contains non-positive values.")
        else:
            ok(check_name)

    if "high" in df.columns and "low" in df.columns:
        high = pd.to_numeric(df["high"], errors="coerce")
        low = pd.to_numeric(df["low"], errors="coerce")
        if high.isna().any() or low.isna().any():
            fail("high_gte_low", "High/low contain non-numeric or missing values.")
        elif not (high >= low).all():
            fail("high_gte_low", "Found bar(s) where high < low.")
        else:
            ok("high_gte_low")
    else:
        fail("high_gte_low", "Missing 'high' or 'low' column.")

    if "volume" in df.columns:
        volume = pd.to_numeric(df["volume"], errors="coerce")
        if volume.isna().any():
            fail("volume_non_negative", "Volume contains non-numeric or missing values.")
        elif (volume < 0).any():
            fail("volume_non_negative", "Found negative volume value(s).")
        else:
            ok("volume_non_negative")
    else:
        fail("volume_non_negative", "Missing 'volume' column.")

    return _finalize(
        checks,
        errors,
        bars=bars,
        missing_values=missing_values,
        duplicates=duplicates,
        freshness_seconds=freshness_seconds,
        gap_analysis=gap_analysis,
    )


def _finalize(
    checks: Dict[str, bool],
    errors: List[str],
    *,
    bars: int,
    missing_values: int,
    duplicates: int,
    freshness_seconds: Optional[float],
    gap_analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    failed = [name for name in CHECK_NAMES if not checks.get(name, False)]
    return {
        "status": "FAIL" if failed else "PASS",
        "bars": bars,
        "missing_values": missing_values,
        "duplicates": duplicates,
        "freshness_seconds": round(freshness_seconds, 1) if freshness_seconds is not None else None,
        "checks": checks,
        "failed_checks": failed,
        "errors": errors,
        "gap_analysis": gap_analysis or {"checked": False, "max_gap_days": None, "large_gap_detected": False},
    }
