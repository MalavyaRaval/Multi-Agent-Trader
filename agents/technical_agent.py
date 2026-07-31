# from __future__ import annotations

# from typing import Any, Optional

# from indicators.ema import calculate_ema
# from indicators.macd import calculate_macd
# from indicators.rsi import calculate_rsi


# class TechnicalAgent:
#     name = "technical_agent"

#     def __init__(self, market_agent: Optional[Any] = None) -> None:
#         self.market_agent = market_agent

#     def analyze(self, symbol: str, timeframe: str = "1d", days: int = 200) -> dict:
#         snapshot = None
#         if self.market_agent is not None:
#             snapshot = self.market_agent.snapshot(symbol=symbol, timeframe=timeframe, days=days)
#         else:
#             try:
#                 from agents.market_agent import MarketAgent

#                 self.market_agent = MarketAgent()
#                 snapshot = self.market_agent.snapshot(symbol=symbol, timeframe=timeframe, days=days)
#             except Exception as exc:  # pragma: no cover - defensive
#                 return {
#                     "symbol": symbol,
#                     "status": "technical analysis unavailable",
#                     "error": str(exc),
#                 }

#         bars = getattr(snapshot, "bars", None)
#         closes = []
#         if bars is not None:
#             try:
#                 closes = [float(row["close"]) for row in bars.to_dict(orient="records")]
#             except Exception:
#                 closes = []

#         metrics = getattr(snapshot, "metrics", {}) or {}
#         signals = {
#             "relative_volume": metrics.get("relative_volume"),
#             "change_percent": metrics.get("change_percent"),
#             "spread": metrics.get("spread"),
#             "ema_20": calculate_ema(closes, period=20) if closes else None,
#             "rsi_14": calculate_rsi(closes, period=14) if closes else None,
#         }

#         macd = calculate_macd(closes, fast=12, slow=26, signal=9) if closes else {"macd": None, "signal": None, "histogram": None}
#         signals.update(macd)

#         return {
#             "symbol": symbol,
#             "timeframe": getattr(snapshot, "timeframe", timeframe),
#             "signals": signals,
#             "status": "technical analysis ready",
#         }


import pandas as pd
from agents.market_agent import MarketAgent
from indicators.rsi import compute_rsi
from indicators.macd import compute_macd
from indicators.ema import compute_ema
from indicators.bollinger import compute_bollinger
from indicators.atr import compute_atr
from indicators.volume import compute_volume_signals

class TechnicalAgent:
    name = "technical_agent"
    
    def __init__(self):
        self.market = MarketAgent()
    
    def analyze(self, symbol: str):
        try:
            snapshot = self.market.snapshot(symbol, timeframe="1d", days=200)
            bars = snapshot.bars
            if bars.empty:
                return {"status": "error", "symbol": symbol, "error": "No data"}
            
            signals = {}
            close = pd.to_numeric(bars["close"], errors="coerce")
            high = pd.to_numeric(bars["high"], errors="coerce")
            low = pd.to_numeric(bars["low"], errors="coerce")
            volume = pd.to_numeric(bars["volume"], errors="coerce")
            
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
            
            # Add market snapshot metrics
            if snapshot.metrics:
                signals["change_percent"] = snapshot.metrics.get("change_percent")
                signals["relative_volume"] = snapshot.metrics.get("relative_volume")
            
            return {"status": "technical analysis ready", "symbol": symbol, "signals": signals}
        except Exception as e:
            return {"status": "error", "symbol": symbol, "error": str(e)}