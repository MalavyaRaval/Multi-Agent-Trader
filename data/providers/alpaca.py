from __future__ import annotations

import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, Optional

import pandas as pd
from dotenv import load_dotenv

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import (
    StockBarsRequest,
    StockLatestQuoteRequest,
    StockLatestTradeRequest,
)
from alpaca.data.timeframe import TimeFrame

from data.providers.base import MarketDataProvider
from data.cache import Cache
from data.retry import retry
from data.models import MarketQuote, MarketTrade, MarketSnapshot


# ----------------------------------------------------------
# Configuration
# ----------------------------------------------------------

load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
    raise RuntimeError("Missing Alpaca API keys.")

logger = logging.getLogger(__name__)


class AlpacaMarketDataProvider(MarketDataProvider):
    def __init__(self, cache_ttl_seconds: int = 60) -> None:
        self.client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
        self.cache = Cache(cache_ttl_seconds)
        logger.info("Alpaca Market Data Provider initialized.")

    def _is_sip_error(self, error: Exception) -> bool:
        message = str(error).lower()
        return "subscription does not permit querying recent sip data" in message or "sip data" in message

    @retry(max_retries=3, delay_seconds=1.0)
    def latest_quote(self, symbol: str) -> MarketQuote:
        symbol = symbol.upper()
        request = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
        try:
            quote = self.client.get_stock_latest_quote(request)[symbol]
        except Exception as exc:
            if self._is_sip_error(exc):
                logger.warning("SIP quote data unavailable for %s; returning placeholder", symbol)
                return MarketQuote(
                    symbol=symbol,
                    bid_price=0.0,
                    ask_price=0.0,
                    bid_size=0,
                    ask_size=0,
                    timestamp=datetime.utcnow(),
                )
            raise
        return MarketQuote(
            symbol=symbol,
            bid_price=float(quote.bid_price),
            ask_price=float(quote.ask_price),
            bid_size=int(getattr(quote, "bid_size", 0) or 0),
            ask_size=int(getattr(quote, "ask_size", 0) or 0),
            timestamp=quote.timestamp,
        )

    @retry(max_retries=3, delay_seconds=1.0)
    def latest_trade(self, symbol: str) -> MarketTrade:
        symbol = symbol.upper()
        request = StockLatestTradeRequest(symbol_or_symbols=[symbol])
        try:
            trade = self.client.get_stock_latest_trade(request)[symbol]
        except Exception as exc:
            if self._is_sip_error(exc):
                logger.warning("SIP trade data unavailable for %s; returning placeholder", symbol)
                return MarketTrade(
                    symbol=symbol,
                    price=0.0,
                    size=0,
                    timestamp=datetime.utcnow(),
                )
            raise
        return MarketTrade(
            symbol=symbol,
            price=float(trade.price),
            size=int(trade.size),
            timestamp=trade.timestamp,
        )

    @retry(max_retries=3, delay_seconds=1.0)
    def historical_bars(self, symbol: str, timeframe: str | TimeFrame = "1d", days: int = 200) -> pd.DataFrame:
        symbol = symbol.upper()
        cache_key = (symbol, str(timeframe), days)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return pd.DataFrame(cached)

        resolved_timeframe = self._resolve_timeframe(timeframe)
        end = datetime.utcnow()
        start = end - timedelta(days=days)

        request = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=resolved_timeframe,
            start=start,
            end=end,
        )

        try:
            bars = self.client.get_stock_bars(request)
            df = bars.df
        except Exception as exc:
            if self._is_sip_error(exc):
                logger.warning("SIP historical data unavailable for %s; returning empty frame", symbol)
                empty_df = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "symbol"])
                self.cache.set(cache_key, empty_df.to_dict(orient="records"))
                return empty_df
            raise

        if df.empty:
            raise RuntimeError(f"No historical data available for {symbol}")

        df = df.reset_index()
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        self.cache.set(cache_key, df.to_dict(orient="records"))
        return df

    def _resolve_timeframe(self, timeframe: str | TimeFrame) -> TimeFrame:
        if isinstance(timeframe, TimeFrame):
            return timeframe

        mapping = {
            "1m": TimeFrame.Minute,
            "5m": TimeFrame(5, "Min"),
            "15m": TimeFrame(15, "Min"),
            "1h": TimeFrame.Hour,
            "1d": TimeFrame.Day,
            "1day": TimeFrame.Day,
            "1hour": TimeFrame.Hour,
            "1min": TimeFrame.Minute,
        }

        key = str(timeframe).strip().lower()
        if key not in mapping:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return mapping[key]

    def _compute_metrics(self, bars: pd.DataFrame, trade: Optional[MarketTrade], quote: Optional[MarketQuote]) -> Dict[str, Any]:
        if bars.empty:
            return {}

        latest = bars.iloc[-1]
        previous = bars.iloc[-2] if len(bars) > 1 else latest
        close_series = pd.to_numeric(bars["close"], errors="coerce")
        volume_series = pd.to_numeric(bars["volume"], errors="coerce")

        avg_volume = float(volume_series.dropna().tail(20).mean()) if not volume_series.dropna().empty else 0.0
        latest_volume = float(volume_series.dropna().iloc[-1]) if not volume_series.dropna().empty else 0.0
        prev_close = float(previous["close"]) if "close" in previous.index else None
        latest_close = float(latest["close"]) if "close" in latest.index else None

        metrics: Dict[str, Any] = {
            "average_volume": avg_volume,
            "current_volume": latest_volume,
            "relative_volume": (latest_volume / avg_volume) if avg_volume else 0.0,
            "previous_close": prev_close,
            "vwap": float((close_series * volume_series).sum() / volume_series.sum()) if volume_series.sum() else None,
        }

        if trade and prev_close:
            metrics["gap_percent"] = ((float(trade.price) - prev_close) / prev_close * 100.0) if prev_close else None

        if quote:
            metrics["spread"] = float(quote.ask_price - quote.bid_price)
            metrics["mid_price"] = float((quote.ask_price + quote.bid_price) / 2.0)

        if trade and latest_close is not None:
            metrics["change_vs_last_close"] = float(trade.price - latest_close)
            metrics["change_percent"] = float((trade.price - latest_close) / latest_close * 100.0) if latest_close else None

        return metrics

    def snapshot(self, symbol: str, timeframe: str | TimeFrame = "1d", days: int = 200) -> MarketSnapshot:
        symbol = symbol.upper()
        logger.info("Building market snapshot for %s (%s)", symbol, timeframe)

        bars = self.historical_bars(symbol, timeframe=timeframe, days=days)
        quote = self.latest_quote(symbol)
        trade = self.latest_trade(symbol)
        metrics = self._compute_metrics(bars, trade, quote)
        if not metrics:
            metrics = {"change_percent": None, "relative_volume": None, "spread": None}

        return MarketSnapshot(
            symbol=symbol,
            timeframe=str(timeframe),
            quote=quote,
            trade=trade,
            bars=bars,
            metrics=metrics,
            generated_at=datetime.utcnow(),
        )

    def snapshot_multi_timeframe(self, symbol: str, intervals: Optional[list[str]] = None, days: int = 200) -> Dict[str, MarketSnapshot]:
        if intervals is None:
            intervals = ["1m", "5m", "15m", "1h", "1d"]

        snapshots: Dict[str, MarketSnapshot] = {}
        for interval in intervals:
            snapshots[interval] = self.snapshot(symbol=symbol, timeframe=interval, days=days)
        return snapshots
