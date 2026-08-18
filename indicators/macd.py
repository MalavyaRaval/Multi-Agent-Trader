from __future__ import annotations

import pandas as pd
import numpy as np


def compute_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Compute MACD, signal line, and histogram from a pandas Series."""
    if series is None or len(series) < slow:
        return None, None, None
    series = pd.to_numeric(series, errors="coerce")
    if series.dropna().empty:
        return None, None, None
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    macd_value = macd_line.iloc[-1]
    signal_value = signal_line.iloc[-1]
    hist_value = histogram.iloc[-1]
    return (
        float(macd_value) if pd.notna(macd_value) else None,
        float(signal_value) if pd.notna(signal_value) else None,
        float(hist_value) if pd.notna(hist_value) else None,
    )


def calculate_macd(prices: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """List-based MACD (backward compat)."""
    if len(prices) < slow:
        return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
    s = pd.Series(prices)
    m, sig, hist = compute_macd(s, fast, slow, signal)
    return {"macd": m, "signal": sig, "histogram": hist}
