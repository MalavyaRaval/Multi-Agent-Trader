"""
market_agent.py

Market Data Agent

Responsibilities
----------------
• Connect to Alpaca Market Data API
• Download historical OHLCV bars
• Retrieve latest quote
• Retrieve latest trade
• Produce a MarketSnapshot object used by every other agent

No AI decisions are made here.
This agent ONLY gathers data.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pandas as pd

from alpaca.data.requests import (
    StockBarsRequest,
    StockLatestQuoteRequest,
    StockLatestTradeRequest,
)
from alpaca.data.timeframe import TimeFrame

from data.alpaca_client import get_market_data_client
from data.cache import Cache
from data.retry import retry


# ----------------------------------------------------------
# Configuration
# ----------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("market_agent")


# ----------------------------------------------------------
# Data Models
# ----------------------------------------------------------

@dataclass
class MarketQuote:

    symbol: str

    bid_price: float
    ask_price: float

    bid_size: int
    ask_size: int

    timestamp: datetime
    source: str = "alpaca"
    status: str = "ok"


@dataclass
class MarketTrade:

    symbol: str

    price: float

    size: int

    timestamp: datetime
    source: str = "alpaca"
    status: str = "ok"


@dataclass
class MarketSnapshot:
    symbol: str
    timeframe: str
    quote: Optional[MarketQuote]
    trade: Optional[MarketTrade]
    bars: pd.DataFrame
    metrics: Optional[Dict[str, Any]] = None
    generated_at: Optional[datetime] = None
    source: str = "alpaca"
    status: str = "ok"
    data_quality: Optional[Dict[str, str]] = None

    def __post_init__(self) -> None:
        if self.generated_at is None:
            self.generated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["bars"] = self.bars.to_dict(orient="records")
        data["generated_at"] = self.generated_at.isoformat() if self.generated_at else None
        return data


# ----------------------------------------------------------
# Market Agent
# ----------------------------------------------------------

class MarketAgent:
    """Collects market data and prepares structured snapshots for downstream agents."""

    def __init__(self, cache_ttl_seconds: int = 60) -> None:
        self.client = get_market_data_client()
        self._cache = Cache(cache_ttl_seconds)
        logger.info("Market Agent initialized.")

    # ------------------------------------------------------

    def _is_sip_error(self, error: Exception) -> bool:
        message = str(error).lower()
        return "subscription does not permit querying recent sip data" in message or "sip data" in message

    @retry(max_retries=3, delay_seconds=1.0)
    def latest_quote(self, symbol: str) -> MarketQuote:
        symbol = symbol.upper()
        if self.client is None:
            raise RuntimeError(f"{symbol}: Alpaca client not initialized. Check ALPACA_API_KEY and ALPACA_SECRET_KEY.")
        request = StockLatestQuoteRequest(symbol_or_symbols=[symbol], feed="iex")
        try:
            quote = self.client.get_stock_latest_quote(request)[symbol]
        except Exception as exc:
            raise RuntimeError(
                f"{symbol}: Alpaca quote unavailable. The configured market-data feed/subscription may not permit this request."
            ) from exc

        bid_price = float(getattr(quote, "bid_price", 0) or 0)
        ask_price = float(getattr(quote, "ask_price", 0) or 0)
        bid_size = int(getattr(quote, "bid_size", 0) or 0)
        ask_size = int(getattr(quote, "ask_size", 0) or 0)
        timestamp = getattr(quote, "timestamp", None)

        logger.info(
            "Alpaca quote %s: bid=%s ask=%s bid_size=%s ask_size=%s timestamp=%s",
            symbol,
            bid_price,
            ask_price,
            bid_size,
            ask_size,
            timestamp,
        )

        if bid_price <= 0 or ask_price <= 0:
            logger.error(
                "%s: invalid Alpaca quote values: bid=%s ask=%s bid_size=%s ask_size=%s timestamp=%s; treating quote as unavailable",
                symbol,
                bid_price,
                ask_price,
                bid_size,
                ask_size,
                timestamp,
            )
            return MarketQuote(
                symbol=symbol,
                bid_price=0.0,
                ask_price=0.0,
                bid_size=bid_size,
                ask_size=ask_size,
                timestamp=timestamp,
                source="alpaca",
                status="invalid",
            )

        if ask_price < bid_price:
            logger.error(
                "%s: invalid Alpaca quote: bid=%s ask=%s bid_size=%s ask_size=%s timestamp=%s; ask < bid, quote rejected",
                symbol,
                bid_price,
                ask_price,
                bid_size,
                ask_size,
                timestamp,
            )
            return MarketQuote(
                symbol=symbol,
                bid_price=0.0,
                ask_price=0.0,
                bid_size=bid_size,
                ask_size=ask_size,
                timestamp=timestamp,
                source="alpaca",
                status="invalid",
            )

        mid_price = (bid_price + ask_price) / 2.0
        spread = ask_price - bid_price
        spread_percent = ((ask_price - bid_price) / mid_price * 100.0) if mid_price and mid_price > 0 else None
        status = "ok"
        quote_quality = "valid"
        if mid_price is not None and spread_percent is not None and spread_percent > 2.0:
            status = "invalid"
            quote_quality = "suspicious"
        logger.info(
            "Quote for %s: bid_price=%s ask_price=%s spread=%s spread_percent=%s bid_size=%s ask_size=%s status=%s quote_quality=%s source=%s",
            symbol,
            bid_price,
            ask_price,
            spread,
            spread_percent,
            bid_size,
            ask_size,
            status,
            quote_quality,
            "alpaca",
        )

        return MarketQuote(
            symbol=symbol,
            bid_price=bid_price,
            ask_price=ask_price,
            bid_size=bid_size,
            ask_size=ask_size,
            timestamp=timestamp,
            source="alpaca",
            status=status,
        )

    # ------------------------------------------------------

    @retry(max_retries=3, delay_seconds=1.0)
    def latest_trade(self, symbol: str) -> MarketTrade:
        symbol = symbol.upper()
        if self.client is None:
            raise RuntimeError(f"{symbol}: Alpaca client not initialized. Check ALPACA_API_KEY and ALPACA_SECRET_KEY.")
        request = StockLatestTradeRequest(symbol_or_symbols=[symbol], feed="iex")
        try:
            trade = self.client.get_stock_latest_trade(request)[symbol]
        except Exception as exc:
            raise RuntimeError(
                f"{symbol}: Alpaca trade unavailable. The configured market-data feed/subscription may not permit this request."
            ) from exc

        price = float(getattr(trade, "price", 0) or 0)
        size = int(getattr(trade, "size", 0) or 0)
        timestamp = getattr(trade, "timestamp", None)
        status = "ok" if price > 0 else "invalid"
        logger.info(
            "Trade for %s: price=%s size=%s timestamp=%s status=%s source=%s",
            symbol,
            price,
            size,
            timestamp,
            status,
            "alpaca",
        )
        return MarketTrade(
            symbol=symbol,
            price=price,
            size=size,
            timestamp=timestamp,
            source="alpaca",
            status=status,
        )

    # ------------------------------------------------------

    def _validate_bars(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        if df is None or df.empty:
            raise RuntimeError(f"{symbol}: no historical OHLCV data received.")

        required = ["open", "high", "low", "close", "volume"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise RuntimeError(f"{symbol}: missing required OHLCV columns: {missing}")

        if "timestamp" in df.columns:
            df = df.sort_values("timestamp").reset_index(drop=True)

        if len(df) < 60:
            raise RuntimeError(
                f"{symbol}: insufficient historical data. Received {len(df)} bars; at least 60 are required."
            )

        for col in required:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        if df["close"].notna().sum() == 0:
            raise RuntimeError(f"{symbol}: close prices are entirely missing or invalid.")
        if df["high"].notna().sum() == 0 or df["low"].notna().sum() == 0:
            raise RuntimeError(f"{symbol}: high/low values are entirely missing or invalid.")

        if df[required].isna().all().all():
            raise RuntimeError(f"{symbol}: all OHLCV values are invalid or missing.")

        return df

    @retry(max_retries=3, delay_seconds=1.0)
    def historical_bars(self, symbol: str, timeframe: str | TimeFrame = "1d", days: int = 200) -> pd.DataFrame:
        symbol = symbol.upper()
        cache_key = (symbol, str(timeframe), days)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return pd.DataFrame(cached)

        if self.client is None:
            raise RuntimeError(f"{symbol}: Alpaca client not initialized. Check ALPACA_API_KEY and ALPACA_SECRET_KEY.")

        resolved_timeframe = self._resolve_timeframe(timeframe)
        end = datetime.utcnow()
        start = end - timedelta(days=days)

        request = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=resolved_timeframe,
            start=start,
            end=end,
            feed="iex",
        )

        try:
            bars = self.client.get_stock_bars(request)
            df = bars.df
        except Exception as exc:
            raise RuntimeError(
                f"{symbol}: Alpaca historical bars unavailable from IEX market data."
            ) from exc

        df = df.reset_index() if not df.empty else df
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        df = self._validate_bars(df, symbol)
        self._cache.set(cache_key, df.to_dict(orient="records"))
        return df

    # ------------------------------------------------------

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
        if bars is None or bars.empty:
            return {
                "average_volume": None,
                "current_volume": None,
                "relative_volume": None,
                "previous_close": None,
                "vwap": None,
                "gap_percent": None,
                "spread": None,
                "mid_price": None,
                "change_vs_last_close": None,
                "change_percent": None,
            }

        latest = bars.iloc[-1]
        previous = bars.iloc[-2] if len(bars) > 1 else latest
        close_series = pd.to_numeric(bars["close"], errors="coerce")
        volume_series = pd.to_numeric(bars["volume"], errors="coerce")

        clean_volume = volume_series.dropna()
        avg_volume = float(clean_volume.tail(20).mean()) if not clean_volume.empty else None
        latest_volume = float(clean_volume.iloc[-1]) if not clean_volume.empty else None
        prev_close = float(previous["close"]) if "close" in previous.index and pd.notna(previous["close"]) else None
        latest_close = float(latest["close"]) if "close" in latest.index and pd.notna(latest["close"]) else None
        vwap = float((close_series * volume_series).sum() / volume_series.sum()) if volume_series.sum() and pd.notna(volume_series.sum()) else None

        metrics: Dict[str, Any] = {
            "average_volume": avg_volume,
            "current_volume": latest_volume,
            "relative_volume": (latest_volume / avg_volume) if avg_volume and avg_volume > 0 and latest_volume is not None else None,
            "previous_close": prev_close,
            "vwap": vwap,
        }

        if trade and prev_close:
            metrics["gap_percent"] = ((float(trade.price) - prev_close) / prev_close * 100.0) if prev_close else None

        if quote:
            bid_price = float(getattr(quote, "bid_price", 0) or 0)
            ask_price = float(getattr(quote, "ask_price", 0) or 0)
            if bid_price > 0 and ask_price > 0 and ask_price >= bid_price:
                metrics["spread"] = float(ask_price - bid_price)
                metrics["mid_price"] = float((ask_price + bid_price) / 2.0)
                if metrics["spread"] is not None and metrics["mid_price"]:
                    spread_threshold = max(2.0, 0.10 * metrics["mid_price"])
                    if metrics["spread"] > spread_threshold:
                        logger.warning(
                            "%s suspicious spread detected: bid=%s ask=%s spread=%s threshold=%s status=%s",
                            quote.symbol,
                            quote.bid_price,
                            quote.ask_price,
                            metrics["spread"],
                            spread_threshold,
                            quote.status,
                        )
            else:
                metrics["spread"] = None
                metrics["mid_price"] = None

        if trade and latest_close is not None:
            metrics["change_vs_last_close"] = float(trade.price - latest_close)
            metrics["change_percent"] = float((trade.price - latest_close) / latest_close * 100.0) if latest_close else None
        else:
            metrics["change_vs_last_close"] = None
            metrics["change_percent"] = None

        logger.info(
            "Market metrics for %s: relative_volume=%s previous_close=%s change_percent=%s vwap=%s spread=%s trade_price=%s trade_timestamp=%s",
            bars.iloc[0].get("symbol") if not bars.empty and "symbol" in bars.columns else "UNKNOWN",
            metrics.get("relative_volume"),
            metrics.get("previous_close"),
            metrics.get("change_percent"),
            metrics.get("vwap"),
            metrics.get("spread"),
            getattr(trade, "price", None),
            getattr(trade, "timestamp", None),
        )

        return metrics

    def snapshot(self, symbol: str, timeframe: str | TimeFrame = "1d", days: int = 200) -> MarketSnapshot:
        symbol = symbol.upper()
        logger.info("Building market snapshot for %s (%s)", symbol, timeframe)

        empty_bars = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "symbol"])

        if self.client is None:
            logger.warning("%s: Alpaca client not initialized; returning unavailable market snapshot.", symbol)
            return MarketSnapshot(
                symbol=symbol,
                timeframe=str(timeframe),
                quote=None,
                trade=None,
                bars=empty_bars,
                metrics={"change_percent": None, "relative_volume": None, "spread": None},
                generated_at=datetime.utcnow(),
            )

        try:
            bars = self.historical_bars(symbol, timeframe=timeframe, days=days)
        except Exception as exc:
            logger.warning("%s: historical_bars failed: %s", symbol, exc)
            bars = empty_bars

        try:
            quote = self.latest_quote(symbol)
        except Exception as exc:
            logger.warning("%s: latest_quote failed: %s", symbol, exc)
            quote = None

        try:
            trade = self.latest_trade(symbol)
        except Exception as exc:
            logger.warning("%s: latest_trade failed: %s", symbol, exc)
            trade = None

        metrics = self._compute_metrics(bars, trade, quote)
        if not metrics:
            metrics = {"change_percent": None, "relative_volume": None, "spread": None}
        if "spread_percent" not in metrics and quote is not None:
            bid = getattr(quote, "bid_price", 0) or 0
            ask = getattr(quote, "ask_price", 0) or 0
            mid = (bid + ask) / 2.0 if bid > 0 and ask > 0 else None
            if mid and mid > 0:
                metrics["spread_percent"] = ((ask - bid) / mid) * 100.0

        status = "ok"
        if quote is not None and getattr(quote, "status", "ok") == "invalid":
            status = "partial"
        if trade is not None and getattr(trade, "status", "ok") == "invalid":
            status = "partial"
        if bars is None or bars.empty:
            status = "error"

        data_quality = {
            "quote": "available" if quote and getattr(quote, "bid_price", 0) and getattr(quote, "ask_price", 0) else "unavailable",
            "trade": "available" if trade and getattr(trade, "price", 0) else "unavailable",
            "bars": "available" if bars is not None and not bars.empty else "unavailable",
        }
        if quote is not None and getattr(quote, "status", "ok") == "invalid":
            data_quality["quote"] = "unavailable"

        return MarketSnapshot(
            symbol=symbol,
            timeframe=str(timeframe),
            quote=quote,
            trade=trade,
            bars=bars,
            metrics=metrics,
            generated_at=datetime.utcnow(),
            source="alpaca",
            status=status,
            data_quality=data_quality,
        )

    def diagnostics(self, symbol: str = "META") -> dict:
        symbol = symbol.upper()
        errors: list[str] = []
        result = {
            "symbol": symbol,
            "alpaca_client": self.client is not None,
            "quote": {"available": False},
            "trade": {"available": False},
            "bars": {"available": False},
            "errors": errors,
        }

        try:
            quote = self.latest_quote(symbol)
            result["quote"] = {
                "available": True,
                "bid": float(quote.bid_price),
                "ask": float(quote.ask_price),
                "bid_size": int(quote.bid_size),
                "ask_size": int(quote.ask_size),
            }
        except Exception as exc:
            result["quote"] = {"available": False, "error": str(exc)}
            errors.append(str(exc))

        try:
            trade = self.latest_trade(symbol)
            result["trade"] = {
                "available": True,
                "price": float(trade.price),
                "size": int(trade.size),
            }
        except Exception as exc:
            result["trade"] = {"available": False, "error": str(exc)}
            errors.append(str(exc))

        try:
            bars = self.historical_bars(symbol, timeframe="1d", days=200)
            result["bars"] = {
                "available": True,
                "rows": int(len(bars)),
                "columns": list(bars.columns),
                "last_close": float(bars["close"].dropna().iloc[-1]) if "close" in bars.columns and bars["close"].dropna().shape[0] else None,
                "last_volume": float(bars["volume"].dropna().iloc[-1]) if "volume" in bars.columns and bars["volume"].dropna().shape[0] else None,
            }
        except Exception as exc:
            result["bars"] = {"available": False, "error": str(exc)}
            errors.append(str(exc))

        return result

    def snapshot_multi_timeframe(self, symbol: str, intervals: Optional[list[str]] = None, days: int = 200) -> Dict[str, MarketSnapshot]:
        if intervals is None:
            intervals = ["1m", "5m", "15m", "1h", "1d"]

        snapshots: Dict[str, MarketSnapshot] = {}
        for interval in intervals:
            snapshots[interval] = self.snapshot(symbol=symbol, timeframe=interval, days=days)
        return snapshots


# ----------------------------------------------------------
# Example
# ----------------------------------------------------------

if __name__ == "__main__":
    agent = MarketAgent()
    snapshot = agent.snapshot("AAPL", timeframe="1d", days=250)
    print(snapshot.quote)
    print(snapshot.trade)
    print(snapshot.metrics)
    print(snapshot.bars.tail())