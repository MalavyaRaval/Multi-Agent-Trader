from __future__ import annotations

import pandas as pd
import numpy as np


def compute_volume_signals(volume: pd.Series, close: pd.Series) -> dict:
    """Compute volume-based signals."""
    if len(volume) < 20 or len(close) < 20:
        return {"volume_ratio": 0.0, "volume_trend": "neutral"}
    avg_volume = float(volume.tail(20).mean())
    latest_volume = float(volume.iloc[-1])
    ratio = latest_volume / avg_volume if avg_volume > 0 else 0.0
    
    # Simple volume trend based on price and volume correlation
    vol_change = volume.pct_change().dropna().tail(5).mean()
    price_change = close.pct_change().dropna().tail(5).mean()
    
    trend = "neutral"
    if ratio > 1.5 and price_change > 0:
        trend = "strong_buy"
    elif ratio > 1.5 and price_change < 0:
        trend = "strong_sell"
    elif ratio > 1.2 and price_change > 0:
        trend = "buy"
    elif ratio > 1.2 and price_change < 0:
        trend = "sell"
    
    return {"volume_ratio": ratio, "volume_trend": trend}


def calculate_volume_ratio(volume: float, average_volume: float) -> float:
    """Simple volume ratio (backward compat)."""
    if average_volume == 0:
        return 0.0
    return volume / average_volume
