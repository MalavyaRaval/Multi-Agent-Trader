from __future__ import annotations

import pandas as pd
import numpy as np


def compute_ema(series: pd.Series, period: int = 20) -> float:
    """Compute the latest EMA value from a pandas Series."""
    if len(series) < period:
        return float(series.iloc[-1]) if len(series) > 0 else 0.0
    ema = series.ewm(span=period, adjust=False).mean()
    return float(ema.iloc[-1])


def calculate_ema(prices: list[float], period: int = 20) -> float:
    """List-based EMA (backward compat)."""
    if not prices:
        return 0.0
    s = pd.Series(prices)
    return compute_ema(s, period)
