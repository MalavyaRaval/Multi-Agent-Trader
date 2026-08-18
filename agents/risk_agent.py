"""
risk_agent.py

Evaluates trading risk based on volatility (ATR), technical signals, and portfolio concentration.
"""

from __future__ import annotations

import logging

import pandas as pd

from agents.market_agent import MarketAgent
from agents.technical_agent import TechnicalAgent
from indicators.atr import compute_atr

logger = logging.getLogger(__name__)


class RiskAgent:
    name = "risk_agent"

    def __init__(self) -> None:
        self.market = MarketAgent()
        self.technical = TechnicalAgent()

    def analyze(self, symbol: str, context: dict | None = None) -> dict:
        if not symbol:
            return {
                "status": "error",
                "symbol": None,
                "risk_level": "unknown",
                "data_quality": "unavailable",
                "error": "Missing symbol",
            }

        symbol = str(symbol).strip().upper()
        if not symbol:
            return {
                "status": "error",
                "symbol": None,
                "risk_level": "unknown",
                "data_quality": "unavailable",
                "error": "Missing symbol",
            }

        result = {
            "symbol": symbol,
            "status": "risk analysis ready",
            "data_quality": "complete",
            "data_available": False,
            "risk_level": "unknown",
            "atr_14": None,
            "last_price": None,
            "atr_percent": None,
            "atr": None,
            "atr_pct": None,
            "rsi": None,
            "rsi_warning": None,
            "checks": {},
            "error": None,
        }

        tech = {}
        signals = {}
        if isinstance(context, dict):
            tech = context.get("technical", {}) if isinstance(context.get("technical", {}), dict) else {}
            signals = tech.get("signals", {}) if isinstance(tech, dict) else {}

        atr = signals.get("atr_14") if signals else None
        rsi = signals.get("rsi_14") if signals else None
        price = signals.get("last_price") if signals else None

        if price is None:
            market = context.get("market", {}) if isinstance(context, dict) else {}
            if isinstance(market, dict):
                quote = market.get("quote")
                if quote is not None:
                    price = getattr(quote, "last_price", None)
                    if price is None:
                        price = getattr(quote, "price", None)
                else:
                    trade = market.get("trade")
                    if trade is not None:
                        price = getattr(trade, "price", None)

        if atr is None:
            try:
                snapshot = self.market.snapshot(symbol, timeframe="1d", days=60)
                if snapshot and getattr(snapshot, "bars", None) is not None and not snapshot.bars.empty:
                    bars = snapshot.bars
                    close = pd.to_numeric(bars["close"], errors="coerce")
                    high = pd.to_numeric(bars["high"], errors="coerce")
                    low = pd.to_numeric(bars["low"], errors="coerce")
                    if close.empty or close.notna().sum() == 0 or high.notna().sum() == 0 or low.notna().sum() == 0:
                        result["status"] = "error"
                        result["data_quality"] = "unavailable"
                        result["error"] = "Missing ATR: invalid OHLC data"
                        result["checks"]["missing_atr"] = "Missing ATR: invalid OHLC data"
                        return result
                    atr = compute_atr(high, low, close, 14)
            except Exception as exc:
                result["status"] = "error"
                result["data_quality"] = "unavailable"
                result["error"] = f"Missing ATR: {exc}"
                result["checks"]["missing_atr"] = str(exc)
                return result

        if atr is not None and atr > 0:
            result["atr_14"] = float(atr)
            result["atr"] = float(atr)
            if price is not None and float(price) > 0:
                price = float(price)
                result["last_price"] = price
                atr_percent = (float(atr) / float(price)) * 100.0
                result["atr_percent"] = round(atr_percent, 2)
                result["atr_pct"] = round(atr_percent, 2)
                if atr_percent > 5:
                    result["risk_level"] = "high"
                    result["checks"]["volatility_warning"] = "ATR > 5% of price"
                elif atr_percent > 2.5:
                    result["risk_level"] = "medium"
                    result["checks"]["volatility_warning"] = "ATR > 2.5% of price"
                else:
                    result["risk_level"] = "low"
                result["data_available"] = True
            else:
                result["status"] = "error"
                result["data_quality"] = "unavailable"
                result["error"] = "Missing current price for ATR percent calculation"
                result["checks"]["missing_price"] = "Missing current price for ATR percent calculation"
                return result
        else:
            if not atr and context is None:
                result["status"] = "error"
                result["data_quality"] = "unavailable"
                result["error"] = "Missing ATR: technical ATR not available"
                result["checks"]["missing_atr"] = "Missing ATR: technical ATR not available"
                return result

        if rsi is None:
            if isinstance(context, dict):
                result["status"] = "risk analysis ready"
                result["data_quality"] = "partial"
            else:
                try:
                    tech = self.technical.analyze(symbol)
                    rsi = tech.get("signals", {}).get("rsi_14")
                except Exception:
                    rsi = None
        result["rsi"] = rsi
        if rsi is not None:
            if rsi > 75:
                result["checks"]["rsi_warning"] = "near_overbought"
                result["rsi_warning"] = "near_overbought"
                if result["risk_level"] in {"unknown", None}:
                    result["risk_level"] = "high"
            elif rsi < 25:
                result["checks"]["rsi_warning"] = "oversold"
                result["rsi_warning"] = "oversold"
                if result["risk_level"] in {"unknown", None}:
                    result["risk_level"] = "medium"
            else:
                result["checks"]["rsi_warning"] = "normal"
                result["rsi_warning"] = "normal"

        if atr is None or price is None:
            result["status"] = "error"
            result["data_quality"] = "unavailable"
            missing_fields = []
            if atr is None:
                missing_fields.append("atr_14")
            if price is None:
                missing_fields.append("last_price")
            result["error"] = f"Missing required risk fields: {missing_fields}"
            result["checks"]["missing_fields"] = missing_fields
            return result

        return result
