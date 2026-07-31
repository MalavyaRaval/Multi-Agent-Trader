from __future__ import annotations

import pandas as pd
import numpy as np


def compute_rsi(series: pd.Series, period: int = 14) -> float:
    """Compute RSI for a pandas Series of closing prices."""
    if len(series) < period + 1:
        return 0.0
    delta = series.diff().dropna()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean().iloc[-1]
    avg_loss = loss.rolling(window=period, min_periods=period).mean().iloc[-1]
    if avg_loss == 0 or pd.isna(avg_loss):
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def calculate_rsi(prices: list[float], period: int = 14) -> float:
    """List-based RSI (backward compat)."""
    if len(prices) < period + 1:
        return 0.0
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
