"""
indicators/multiframe.py

Analyzes a symbol across multiple timeframes simultaneously
and aggregates signals into a unified view.
"""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from agents.market_agent import MarketAgent
from indicators.atr import compute_atr
from indicators.bollinger import compute_bollinger
from indicators.ema import compute_ema
from indicators.macd import compute_macd
from indicators.rsi import compute_rsi
from indicators.volume import compute_volume_signals


TIMEFRAMES = ["1d", "1h", "15m", "5m"]


def analyze_multiframe(symbol: str, timeframes=None) -> dict:
    """Run technical analysis across multiple timeframes and aggregate."""
    timeframes = timeframes or TIMEFRAMES
    symbol = symbol.upper()
    market = MarketAgent()

    frame_results: Dict[str, Any] = {}
    for tf in timeframes:
        try:
            # Adjust days per timeframe to get enough bars
            days_map = {"1d": 200, "1h": 60, "15m": 30, "5m": 15, "1m": 7}
            days = days_map.get(tf, 200)

            snapshot = market.snapshot(symbol, timeframe=tf, days=days)
            bars = snapshot.bars
            if bars.empty or len(bars) < 20:
                frame_results[tf] = {"status": "insufficient_data"}
                continue

            close = pd.to_numeric(bars["close"], errors="coerce")
            high = pd.to_numeric(bars.get("high", close), errors="coerce")
            low = pd.to_numeric(bars.get("low", close), errors="coerce")
            volume = pd.to_numeric(bars.get("volume", pd.Series([0] * len(bars))), errors="coerce")

            signals = {}
            if len(close) >= 15:
                signals["rsi_14"] = compute_rsi(close, 14)
            if len(close) >= 26:
                signals["macd"], signals["macd_signal"], signals["macd_hist"] = compute_macd(close)
            if len(close) >= 20:
                signals["ema_20"] = compute_ema(close, 20)
            if len(close) >= 50:
                signals["ema_50"] = compute_ema(close, 50)
            if len(close) >= 15:
                signals["atr_14"] = compute_atr(high, low, close, 14)
            if len(close) >= 20:
                bb_upper, bb_lower, bb_mid = compute_bollinger(close, 20)
                signals["bollinger_upper"] = bb_upper
                signals["bollinger_middle"] = bb_mid
                signals["bollinger_lower"] = bb_lower
            if len(volume) >= 20:
                vol_sigs = compute_volume_signals(volume, close)
                signals.update(vol_sigs)
            if snapshot.metrics:
                signals["change_percent"] = snapshot.metrics.get("change_percent")
                signals["relative_volume"] = snapshot.metrics.get("relative_volume")

            # Determine trend direction for this timeframe
            trend = "neutral"
            ema_20 = signals.get("ema_20")
            ema_50 = signals.get("ema_50")
            if ema_20 is not None and ema_50 is not None:
                if ema_20 > ema_50 * 1.005:
                    trend = "uptrend"
                elif ema_20 < ema_50 * 0.995:
                    trend = "downtrend"

            # Determine momentum
            momentum = "neutral"
            macd = signals.get("macd")
            macd_signal = signals.get("macd_signal")
            rsi = signals.get("rsi_14")
            if macd is not None and macd_signal is not None:
                if macd > macd_signal and (rsi is None or rsi < 70):
                    momentum = "bullish"
                elif macd < macd_signal and (rsi is None or rsi > 30):
                    momentum = "bearish"

            frame_results[tf] = {
                "status": "ready",
                "trend": trend,
                "momentum": momentum,
                "signals": signals,
                "last_price": float(close.iloc[-1]) if len(close) > 0 else None,
            }
        except Exception as e:
            frame_results[tf] = {"status": "error", "error": str(e)}

    # ---- Aggregate across timeframes ----
    # Alignment scoring: higher when more timeframes agree
    trends = [r.get("trend") for r in frame_results.values() if r.get("status") == "ready"]
    momentums = [r.get("momentum") for r in frame_results.values() if r.get("status") == "ready"]

    uptrend_count = trends.count("uptrend")
    downtrend_count = trends.count("downtrend")
    bullish_count = momentums.count("bullish")
    bearish_count = momentums.count("bearish")
    total = len(trends)

    alignment_score = 0.0
    if total > 0:
        if uptrend_count > downtrend_count and bullish_count > bearish_count:
            alignment_score = (uptrend_count / total + bullish_count / total) / 2
        elif downtrend_count > uptrend_count and bearish_count > bullish_count:
            alignment_score = -((downtrend_count / total + bearish_count / total) / 2)

    # Determine overall multiframe signal
    overall = "neutral"
    if alignment_score >= 0.6:
        overall = "strong_buy"
    elif alignment_score >= 0.3:
        overall = "buy"
    elif alignment_score <= -0.6:
        overall = "strong_sell"
    elif alignment_score <= -0.3:
        overall = "sell"

    return {
        "symbol": symbol,
        "timeframes_analyzed": list(frame_results.keys()),
        "frame_results": frame_results,
        "alignment_score": round(alignment_score, 2),
        "overall_signal": overall,
        "trend_summary": {
            "uptrend": uptrend_count,
            "downtrend": downtrend_count,
            "neutral": total - uptrend_count - downtrend_count,
        },
        "momentum_summary": {
            "bullish": bullish_count,
            "bearish": bearish_count,
            "neutral": total - bullish_count - bearish_count,
        },
    }
