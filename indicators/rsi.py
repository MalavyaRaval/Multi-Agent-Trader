from __future__ import annotations

import pandas as pd
import numpy as np


def compute_rsi_series(series: pd.Series, period: int = 14) -> pd.Series:
    """Compute the full RSI series (for charting), using the same rolling-mean
    method as compute_rsi (a simple mean of gains/losses, NOT Wilder smoothing)."""
    series = pd.to_numeric(series, errors="coerce")
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))

    rsi = rsi.where(avg_loss != 0, 100.0)
    rsi = rsi.where(~(avg_gain.isna() | avg_loss.isna()))
    return rsi


def compute_rsi(series: pd.Series, period: int = 14) -> float:
    """Compute RSI for a pandas Series of closing prices."""
    if series is None or len(series) < period + 1:
        return None
    if pd.isna(series).all():
        return None
    delta = pd.to_numeric(series, errors="coerce").diff().dropna()
    if len(delta) < period:
        return None
    value = compute_rsi_series(series, period).iloc[-1]
    return float(value) if pd.notna(value) else None
