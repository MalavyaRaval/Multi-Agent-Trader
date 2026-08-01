"""
sizing/kelly.py

Kelly Criterion position sizing.

The Kelly fraction tells you what fraction of your bankroll to bet
given your edge and odds. For trading, we adapt it using historical
win rate and average win/loss ratio.
"""

from __future__ import annotations

from typing import Optional


def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """
    Calculate Kelly fraction.
    
    Args:
        win_rate: Probability of winning (0.0 to 1.0)
        avg_win: Average win amount per winning trade
        avg_loss: Average loss amount per losing trade (positive number)
    
    Returns:
        Kelly fraction (can be negative, zero, or > 1.0)
    """
    if avg_loss <= 0:
        return 0.0

    try:
        win_rate = float(win_rate)
        avg_win = float(avg_win)
        avg_loss = float(avg_loss)
    except Exception:
        return 0.0

    if win_rate <= 0 or win_rate >= 1:
        return 0.0
    
    # b = average win / average loss (the odds)
    b = avg_win / avg_loss
    
    # Kelly = (bp - q) / b  where p = win_rate, q = 1 - p
    kelly = (b * win_rate - (1 - win_rate)) / b
    
    # Clamp to reasonable trading range (half-Kelly is common)
    return max(0.0, min(kelly * 0.5, 0.25))


def kelly_position_size(
    equity: float,
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    price: float,
    max_position_pct: float = 0.2,
) -> Optional[float]:
    """
    Calculate number of shares to buy using Kelly criterion.
    
    Args:
        equity: Total account equity
        win_rate: Historical win rate (0.0 to 1.0)
        avg_win: Average win per winning trade
        avg_loss: Average loss per losing trade (positive)
        price: Current stock price
        max_position_pct: Maximum position size as fraction of equity
    
    Returns:
        Number of shares, or None if Kelly says don't trade
    """
    if price <= 0:
        return None
    
    fraction = kelly_fraction(win_rate, avg_win, avg_loss)
    if fraction <= 0:
        return None
    
    # Cap at max_position_pct
    fraction = min(fraction, max_position_pct)
    
    dollars_to_invest = equity * fraction
    shares = dollars_to_invest / price
    
    return round(shares, 4) if shares >= 0.0001 else None


def half_kelly(*args, **kwargs):
    """Half-Kelly (more conservative) wrapper."""
    result = kelly_position_size(*args, **kwargs)
    if result is not None:
        return round(result * 0.5, 4) if result * 0.5 >= 0.0001 else None
    return None
