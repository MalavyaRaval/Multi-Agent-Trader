"""
sizing/vol_target.py

Volatility Targeting position sizing.

Sizes positions so that each trade contributes a target level of
volatility (risk) to the portfolio, regardless of the asset's
inherent volatility.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import numpy as np


def target_volatility_size(
    equity: float,
    price: float,
    atr: float,
    target_volatility_pct: float = 0.02,  # 2% daily vol target
    max_position_pct: float = 0.25,
) -> Optional[float]:
    """
    Size position to target a specific volatility level.
    
    Higher ATR = smaller position (asset is more volatile)
    Lower ATR = larger position (asset is less volatile)
    
    Args:
        equity: Total account equity
        price: Current stock price
        atr: Average True Range (volatility measure)
        target_volatility_pct: Target daily volatility as fraction of equity (default 2%)
        max_position_pct: Max position as fraction of equity
    
    Returns:
        Number of shares, or None if volatility is too high
    """
    if price <= 0 or atr <= 0 or equity <= 0:
        return None

    try:
        equity = float(equity)
        price = float(price)
        atr = float(atr)
    except Exception:
        return None
    
    # Position volatility = position_value * (atr / price)
    # We want: position_volatility / equity = target_volatility_pct
    # So: position_value = target_volatility_pct * equity / (atr / price)
    
    vol_ratio = atr / price  # % of price that ATR represents
    target_position_value = target_volatility_pct * equity / vol_ratio
    
    # Cap at max position size
    max_position_value = equity * max_position_pct
    position_value = min(target_position_value, max_position_value)
    
    shares = position_value / price
    return round(shares, 4) if shares >= 0.0001 else None


def risk_parity_size(
    equity: float,
    price: float,
    atr: float,
    risk_budget: float = 0.01,  # 1% of equity risk per trade
    max_position_pct: float = 0.25,
) -> Optional[float]:
    """
    Size position based on a fixed risk budget.
    
    Risk = position_value * (atr / price)
    We want risk = risk_budget * equity
    
    Args:
        equity: Total account equity
        price: Current stock price
        atr: Average True Range
        risk_budget: Max risk as fraction of equity per trade
        max_position_pct: Max position as fraction of equity
    """
    if price <= 0 or atr <= 0 or equity <= 0:
        return None
    
    vol_ratio = atr / price
    target_position_value = risk_budget * equity / vol_ratio
    
    max_position_value = equity * max_position_pct
    position_value = min(target_position_value, max_position_value)
    
    shares = position_value / price
    return round(shares, 4) if shares >= 0.0001 else None
