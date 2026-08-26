from __future__ import annotations

import pandas as pd
import numpy as np


def compute_ema_series(series: pd.Series, period: int = 20) -> pd.Series:
    """Compute the full EMA series from a pandas Series (for charting)."""
    series = pd.to_numeric(series, errors="coerce")
    return series.ewm(span=period, adjust=False).mean()


def compute_ema(series: pd.Series, period: int = 20) -> float:
    """Compute the latest EMA value from a pandas Series."""
    if series is None or len(series) < period:
        return None
    series = pd.to_numeric(series, errors="coerce")
    if series.dropna().empty:
        return None
    value = compute_ema_series(series, period).iloc[-1]
    return float(value) if pd.notna(value) else None
