from __future__ import annotations

import pandas as pd
import numpy as np


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
    """Compute Average True Range from high, low, close pandas Series."""
    if high is None or low is None or close is None or len(close) < 2:
        return None
    high = pd.to_numeric(high, errors="coerce")
    low = pd.to_numeric(low, errors="coerce")
    close = pd.to_numeric(close, errors="coerce")
    if high.dropna().empty or low.dropna().empty or close.dropna().empty:
        return None
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=period, min_periods=period).mean()
    value = atr.iloc[-1]
    return float(value) if pd.notna(value) else None
