from __future__ import annotations

import pandas as pd
import numpy as np


def compute_bollinger(series: pd.Series, period: int = 20, std_dev: int = 2):
    """Compute Bollinger Bands from a pandas Series. Returns (upper, lower, middle)."""
    if len(series) < period:
        val = float(series.iloc[-1]) if len(series) > 0 else 0.0
        return val, val, val
    middle = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    return float(upper.iloc[-1]), float(lower.iloc[-1]), float(middle.iloc[-1])


def calculate_bollinger(prices: list[float], period: int = 20, std_dev: int = 2) -> dict:
    """List-based Bollinger Bands (backward compat)."""
    if len(prices) < period:
        return {"middle_band": prices[-1] if prices else 0.0, "upper_band": 0.0, "lower_band": 0.0}
    s = pd.Series(prices)
    u, l, m = compute_bollinger(s, period, std_dev)
    return {"middle_band": m, "upper_band": u, "lower_band": l}
