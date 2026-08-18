from __future__ import annotations

import pandas as pd
import numpy as np


def compute_ema(series: pd.Series, period: int = 20) -> float:
    """Compute the latest EMA value from a pandas Series."""
    if series is None or len(series) < period:
        return None
    series = pd.to_numeric(series, errors="coerce")
    if series.dropna().empty:
        return None
    ema = series.ewm(span=period, adjust=False).mean()
    value = ema.iloc[-1]
    return float(value) if pd.notna(value) else None


def calculate_ema(prices: list[float], period: int = 20) -> float:
    """List-based EMA (backward compat)."""
    if not prices:
        return 0.0
    s = pd.Series(prices)
    return compute_ema(s, period)
