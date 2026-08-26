from __future__ import annotations

import pandas as pd
import numpy as np


def compute_macd_series(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Compute the full MACD line, signal line, and histogram series (for charting)."""
    series = pd.to_numeric(series, errors="coerce")
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Compute MACD, signal line, and histogram from a pandas Series."""
    if series is None or len(series) < slow:
        return None, None, None
    series = pd.to_numeric(series, errors="coerce")
    if series.dropna().empty:
        return None, None, None
    macd_line, signal_line, histogram = compute_macd_series(series, fast, slow, signal)
    macd_value = macd_line.iloc[-1]
    signal_value = signal_line.iloc[-1]
    hist_value = histogram.iloc[-1]
    return (
        float(macd_value) if pd.notna(macd_value) else None,
        float(signal_value) if pd.notna(signal_value) else None,
        float(hist_value) if pd.notna(hist_value) else None,
    )
