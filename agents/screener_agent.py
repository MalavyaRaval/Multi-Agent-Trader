"""
agents/screener_agent.py

Discovers trading opportunities by scanning a universe of symbols
and ranking them by momentum, volume, and technical signals.
"""

from __future__ import annotations

from typing import Any, Dict, List

from agents.market_agent import MarketAgent
from agents.technical_agent import TechnicalAgent


DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "NFLX",
    "AMD", "INTC", "CRM", "UBER", "COIN", "PLTR", "SNOW", "ROKU",
    "SHOP", "SQ", "PYPL", "ZM", "DOCU", "DDOG", "NET", "CRWD",
    "MDB", "OKTA", "TWLO", "FSLY", "DDOG", "SE", "BABA", "JD",
    "PDD", "NIO", "LI", "XPEV", "ARKK", "QQQ", "SPY", "IWM",
]


class ScreenerAgent:
    name = "screener_agent"

    def __init__(self) -> None:
        self.market = MarketAgent()
        self.technical = TechnicalAgent()

    def screen(self, symbols: List[str] | None = None, top_n: int = 10) -> dict:
        """Screen symbols and return ranked candidates."""
        symbols = symbols or DEFAULT_UNIVERSE
        results: List[Dict[str, Any]] = []

        for symbol in symbols:
            try:
                score, data = self._score_symbol(symbol)
                if score > 0:
                    results.append({"symbol": symbol, "score": score, **data})
            except Exception:
                continue

        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)

        return {
            "status": "screening complete",
            "candidates": results[:top_n],
            "total_scanned": len(symbols),
            "matches": len(results),
        }

    def _score_symbol(self, symbol: str):
        """Score a single symbol. Returns (score, data_dict)."""
        snapshot = self.market.snapshot(symbol, timeframe="1d", days=60)
        tech = self.technical.analyze(symbol)

        signals = tech.get("signals", {})
        metrics = snapshot.metrics or {}

        score = 0.0
        reasons = []

        # Price momentum
        change = metrics.get("change_percent")
        if change is not None:
            if 2 < change < 8:
                score += 1.5
                reasons.append(f"Strong momentum (+{change:.1f}%)")
            elif 1 < change <= 2:
                score += 0.5
                reasons.append(f"Positive momentum (+{change:.1f}%)")
            elif change > 8:
                score -= 0.5  # Too extended
                reasons.append(f"Overextended (+{change:.1f}%)")

        # Volume
        vol_ratio = signals.get("volume_ratio")
        if vol_ratio is not None and vol_ratio > 1.5:
            score += 1.0
            reasons.append(f"High volume ({vol_ratio:.1f}x)")

        # RSI
        rsi = signals.get("rsi_14")
        if rsi is not None:
            if 40 < rsi < 60:
                score += 0.5
                reasons.append(f"RSI neutral ({rsi:.1f})")
            elif 30 <= rsi <= 40:
                score += 1.0
                reasons.append(f"RSI in buy zone ({rsi:.1f})")
            elif rsi > 75:
                score -= 1.0
                reasons.append(f"RSI overbought ({rsi:.1f})")

        # MACD
        macd = signals.get("macd")
        macd_signal = signals.get("macd_signal")
        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                score += 0.5
                reasons.append("MACD bullish")

        # Trend
        ema_20 = signals.get("ema_20")
        ema_50 = signals.get("ema_50")
        if ema_20 is not None and ema_50 is not None and ema_20 > ema_50:
            score += 0.5
            reasons.append("EMA uptrend")

        data = {
            "price": snapshot.trade.price if snapshot.trade else None,
            "change_percent": change,
            "volume_ratio": vol_ratio,
            "rsi": rsi,
            "reasons": reasons,
        }
        return score, data
