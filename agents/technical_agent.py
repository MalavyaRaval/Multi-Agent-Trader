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
        errors = []
        try:
            snapshot = self.market.snapshot(symbol=symbol, timeframe=timeframe, days=days)
            bars = getattr(snapshot, "bars", None)
            if bars is None:
                return {
                    "status": "error",
                    "source": "Alpaca",
                    "symbol": symbol,
                    "data_quality": "unavailable",
                    "bars_used": 0,
                    "signals": {},
                    "errors": ["No market data"],
                }

            frame = self._coerce_to_frame(bars)
            if frame.empty:
                return {
                    "status": "error",
                    "source": "Alpaca",
                    "symbol": symbol,
                    "data_quality": "unavailable",
                    "bars_used": 0,
                    "signals": {},
                    "errors": ["No data"],
                }

            required = ["open", "high", "low", "close", "volume"]
            missing = [col for col in required if col not in frame.columns]
            if missing:
                return {
                    "status": "error",
                    "source": "Alpaca",
                    "symbol": symbol,
                    "data_quality": "unavailable",
                    "bars_used": len(frame),
                    "signals": {},
                    "errors": [f"Missing OHLCV columns: {missing}"],
                }

            if len(frame) < 60:
                return {
                    "status": "error",
                    "source": "Alpaca",
                    "symbol": symbol,
                    "data_quality": "partial",
                    "bars_used": len(frame),
                    "signals": {},
                    "errors": [f"Insufficient historical data: {len(frame)} bars < 60"],
                }

            frame = frame.copy()
            for col in required:
                frame[col] = pd.to_numeric(frame[col], errors="coerce")

            close = frame["close"]
            high = frame["high"]
            low = frame["low"]
            volume = frame["volume"]

            if close.notna().sum() == 0 or high.notna().sum() == 0 or low.notna().sum() == 0:
                return {
                    "status": "error",
                    "source": "Alpaca",
                    "symbol": symbol,
                    "data_quality": "unavailable",
                    "bars_used": len(frame),
                    "signals": {},
                    "errors": ["No valid OHLC data received"],
                }

            signals = {}
            signals["last_price"] = float(close.dropna().iloc[-1])
            signals["close"] = float(close.dropna().iloc[-1])
            signals["rsi_14"] = compute_rsi(close, 14)
            signals["macd"], signals["macd_signal"], signals["macd_hist"] = compute_macd(close)
            signals["ema_20"] = compute_ema(close, 20)
            signals["ema_50"] = compute_ema(close, 50)
            bb_upper, bb_lower, bb_mid = compute_bollinger(close)
            signals["bollinger_upper"] = bb_upper
            signals["bollinger_middle"] = bb_mid
            signals["bollinger_lower"] = bb_lower
            signals["atr_14"] = compute_atr(high, low, close, 14)
            vol_signals = compute_volume_signals(volume, close)
            signals.update(vol_signals)

            metrics = getattr(snapshot, "metrics", {}) or {}
            if metrics:
                signals["change_percent"] = metrics.get("change_percent")
                signals["relative_volume"] = metrics.get("relative_volume")

            return {
                "status": "ok",
                "source": "Alpaca",
                "symbol": symbol,
                "data_quality": "complete",
                "timeframe": getattr(snapshot, "timeframe", timeframe),
                "bars_used": len(frame),
                "number_of_bars": len(frame),
                "signals": signals,
                "errors": errors,
            }
        except Exception as e:
            errors.append(str(e))
            return {
                "status": "error",
                "source": "Alpaca",
                "symbol": symbol,
                "data_quality": "unavailable",
                "bars_used": 0,
                "signals": {},
                "errors": errors,
            }

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