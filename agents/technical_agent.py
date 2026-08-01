from __future__ import annotations

import pandas as pd

from agents.market_agent import MarketAgent
from indicators.atr import compute_atr
from indicators.bollinger import compute_bollinger
from indicators.ema import compute_ema
from indicators.macd import compute_macd
from indicators.rsi import compute_rsi
from indicators.volume import compute_volume_signals


class TechnicalAgent:
    name = "technical_agent"

    def __init__(self, market_agent=None) -> None:
        self.market = market_agent or MarketAgent()

    def analyze(self, symbol: str, timeframe: str = "1d", days: int = 200) -> dict:
        symbol = symbol.upper()
        try:
            snapshot = self.market.snapshot(symbol=symbol, timeframe=timeframe, days=days)
            bars = getattr(snapshot, "bars", None)
            if bars is None:
                return {"status": "error", "symbol": symbol, "error": "No data"}

            frame = self._coerce_to_frame(bars)
            if frame.empty:
                return {"status": "error", "symbol": symbol, "error": "No data"}

            signals = {}
            close = pd.to_numeric(frame.get("close", pd.Series([None] * len(frame))), errors="coerce")
            high = pd.to_numeric(frame.get("high", pd.Series([None] * len(frame))), errors="coerce")
            low = pd.to_numeric(frame.get("low", pd.Series([None] * len(frame))), errors="coerce")
            volume = pd.to_numeric(frame.get("volume", pd.Series([0] * len(frame))), errors="coerce")

            signals["rsi_14"] = compute_rsi(close, 14)
            signals["macd"], signals["macd_signal"], signals["macd_hist"] = compute_macd(close)
            signals["ema_20"] = compute_ema(close, 20)
            signals["ema_50"] = compute_ema(close, 50)
            bb_upper, bb_lower, bb_mid = compute_bollinger(close)
            signals["bollinger_upper"] = bb_upper
            signals["bollinger_lower"] = bb_lower
            signals["atr_14"] = compute_atr(high, low, close, 14)
            vol_signals = compute_volume_signals(volume, close)
            signals.update(vol_signals)

            metrics = getattr(snapshot, "metrics", {}) or {}
            if metrics:
                signals["change_percent"] = metrics.get("change_percent")
                signals["relative_volume"] = metrics.get("relative_volume")

            return {
                "status": "technical analysis ready",
                "symbol": symbol,
                "timeframe": getattr(snapshot, "timeframe", timeframe),
                "signals": signals,
            }
        except Exception as e:
            return {"status": "error", "symbol": symbol, "error": str(e)}

    @staticmethod
    def _coerce_to_frame(bars):
        if isinstance(bars, pd.DataFrame):
            return bars
        if isinstance(bars, list):
            if not bars:
                return pd.DataFrame()
            if isinstance(bars[0], dict):
                return pd.DataFrame(bars)
            return pd.DataFrame({"close": bars})
        if isinstance(bars, dict):
            return pd.DataFrame(bars)
        return pd.DataFrame()