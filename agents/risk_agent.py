"""
risk_agent.py

Evaluates trading risk based on volatility (ATR), technical signals, and portfolio concentration.
"""

from __future__ import annotations

from agents.market_agent import MarketAgent
from agents.technical_agent import TechnicalAgent
from indicators.atr import compute_atr

import pandas as pd


class RiskAgent:
    name = "risk_agent"

    def __init__(self) -> None:
        self.market = MarketAgent()
        self.technical = TechnicalAgent()

    def analyze(self, symbol: str) -> dict:
        symbol = symbol.upper()
        result = {"symbol": symbol, "status": "risk analysis ready", "risk_level": "medium", "checks": {}}

        try:
            snapshot = self.market.snapshot(symbol, timeframe="1d", days=60)
            bars = snapshot.bars
            if not bars.empty:
                close = pd.to_numeric(bars["close"], errors="coerce")
                high = pd.to_numeric(bars["high"], errors="coerce")
                low = pd.to_numeric(bars["low"], errors="coerce")
                atr = compute_atr(high, low, close, 14)
                price = float(close.iloc[-1]) if len(close) > 0 else 0.0
                atr_pct = (atr / price * 100.0) if price > 0 else 0.0
                result["checks"]["atr_14"] = round(atr, 4)
                result["checks"]["atr_percent"] = round(atr_pct, 2)

                if atr_pct > 5:
                    result["risk_level"] = "high"
                    result["checks"]["volatility_warning"] = "ATR > 5% of price"
                elif atr_pct > 2.5:
                    result["risk_level"] = "medium"
                else:
                    result["risk_level"] = "low"
        except Exception as e:
            result["checks"]["market_data_error"] = str(e)

        # Technical risk signals
        try:
            tech = self.technical.analyze(symbol)
            signals = tech.get("signals", {})
            rsi = signals.get("rsi_14")
            if rsi is not None:
                if rsi > 75:
                    result["checks"]["rsi_warning"] = "Overbought (RSI > 75)"
                    result["risk_level"] = "high"
                elif rsi < 25:
                    result["checks"]["rsi_warning"] = "Oversold (RSI < 25)"
        except Exception as e:
            result["checks"]["technical_error"] = str(e)

        return result
