from __future__ import annotations

import pandas as pd
import numpy as np


def compute_bollinger_series(series: pd.Series, period: int = 20, std_dev: int = 2):
    """Compute the full Bollinger Band series (for charting). Returns (upper, lower, middle)."""
    series = pd.to_numeric(series, errors="coerce")
    middle = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    return upper, lower, middle


def compute_bollinger(series: pd.Series, period: int = 20, std_dev: int = 2):
    """Compute Bollinger Bands from a pandas Series. Returns (upper, lower, middle)."""
    if series is None or len(series) < period:
        return None, None, None
    series = pd.to_numeric(series, errors="coerce")
    if series.dropna().empty:
        return None, None, None
    upper, lower, middle = compute_bollinger_series(series, period, std_dev)
    upper_value = upper.iloc[-1]
    lower_value = lower.iloc[-1]
    middle_value = middle.iloc[-1]
    return (
        float(upper_value) if pd.notna(upper_value) else None,
        float(lower_value) if pd.notna(lower_value) else None,
        float(middle_value) if pd.notna(middle_value) else None,
    )
