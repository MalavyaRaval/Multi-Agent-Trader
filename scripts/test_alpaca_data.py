"""
scripts/test_alpaca_data.py

Phase 0 - Alpaca baseline health check.

Tests:
- API credentials present
- Paper account authentication
- Account endpoint
- Market data authentication
- Latest quote
- Latest trade
- Latest bar
- Historical bars
- Selected feed
- Number of returned bars
- Newest/oldest bar timestamps
- API latency
- HTTP/status errors
- Rate-limit information when available

This script NEVER places an order.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

load_dotenv()

SYMBOL = os.getenv("DEFAULT_SYMBOL", "AAPL").upper()
FEED_NAME = os.getenv("ALPACA_DATA_FEED", "iex").lower()
HISTORICAL_DAYS = int(os.getenv("HEALTH_CHECK_HISTORICAL_DAYS", "400"))
EXPECTED_BARS = int(os.getenv("HEALTH_CHECK_EXPECTED_BARS", "250"))


def _result(
    name: str,
    status: str,
    *,
    message: str = "",
    latency_ms: float | None = None,
    **extra: Any,
) -> Dict[str, Any]:
    data = {
        "name": name,
        "status": status,
        "message": message,
        "latency_ms": latency_ms,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    data.update(extra)
    return data


def _exception_details(exc: Exception) -> Dict[str, Any]:
    details: Dict[str, Any] = {
        "error_type": type(exc).__name__,
        "error": str(exc),
    }

    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
        if value is not None:
            details[attr] = value

    response = getattr(exc, "response", None)
    if response is not None:
        details["http_status"] = getattr(response, "status_code", None)

        headers = getattr(response, "headers", None)
        if headers:
            details["rate_limit"] = {
                key: headers.get(key)
                for key in (
                    "X-RateLimit-Limit",
                    "X-RateLimit-Remaining",
                    "X-RateLimit-Reset",
                )
                if headers.get(key) is not None
            }

    return details


def _timed_call(func):
    started = time.perf_counter()

    try:
        value = func()
        latency_ms = (time.perf_counter() - started) * 1000
        return value, latency_ms, None
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return None, latency_ms, exc


def run() -> Dict[str, Any]:
    started_at = datetime.now(timezone.utc)

    report: Dict[str, Any] = {
        "service": "alpaca",
        "symbol": SYMBOL,
        "selected_feed": FEED_NAME,
        "started_at": started_at.isoformat(),
        "checks": [],
    }

    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")

    if not api_key or not secret_key:
        report["checks"].append(
            _result(
                "credentials",
                "FAIL",
                message="ALPACA_API_KEY or ALPACA_SECRET_KEY is missing.",
            )
        )
        report["status"] = "FAIL"
        return report

    report["checks"].append(
        _result(
            "credentials",
            "PASS",
            message="Alpaca credentials are present.",
        )
    )

    # ---------------------------------------------------------
    # Trading / paper account
    # ---------------------------------------------------------

    try:
        from alpaca.trading.client import TradingClient

        trading_client = TradingClient(
            api_key,
            secret_key,
            paper=True,
        )

        account, latency_ms, error = _timed_call(
            trading_client.get_account
        )

        if error:
            report["checks"].append(
                _result(
                    "paper_account_authentication",
                    "FAIL",
                    message="Paper account authentication failed.",
                    latency_ms=latency_ms,
                    **_exception_details(error),
                )
            )
        else:
            report["checks"].append(
                _result(
                    "paper_account_authentication",
                    "PASS",
                    message="Paper trading account authenticated.",
                    latency_ms=latency_ms,
                    account_status=str(getattr(account, "status", "")),
                )
            )

            report["checks"].append(
                _result(
                    "account_endpoint",
                    "PASS",
                    message="Paper account endpoint responded successfully.",
                    latency_ms=latency_ms,
                    account_status=str(getattr(account, "status", "")),
                    buying_power=str(getattr(account, "buying_power", "")),
                )
            )

    except Exception as exc:
        report["checks"].append(
            _result(
                "paper_account_authentication",
                "FAIL",
                message="Could not initialize Alpaca TradingClient.",
                **_exception_details(exc),
            )
        )

    # ---------------------------------------------------------
    # Market data
    # ---------------------------------------------------------

    try:
        from alpaca.data.enums import DataFeed
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import (
            StockBarsRequest,
            StockLatestQuoteRequest,
            StockLatestTradeRequest,
        )
        from alpaca.data.timeframe import TimeFrame

        data_client = StockHistoricalDataClient(
            api_key,
            secret_key,
        )

        try:
            feed = DataFeed(FEED_NAME)
        except Exception:
            feed = DataFeed.IEX
            FEED_NAME = "iex"

        report["selected_feed"] = FEED_NAME

        # -----------------------------------------------------
        # Latest quote
        # -----------------------------------------------------

        quote_request = StockLatestQuoteRequest(
            symbol_or_symbols=[SYMBOL],
            feed=feed,
        )

        quote, latency_ms, error = _timed_call(
            lambda: data_client.get_stock_latest_quote(quote_request)
        )

        if error:
            report["checks"].append(
                _result(
                    "latest_quote",
                    "FAIL",
                    message="Latest quote request failed.",
                    latency_ms=latency_ms,
                    **_exception_details(error),
                )
            )
        else:
            quote_obj = quote.get(SYMBOL)

            if quote_obj is None:
                report["checks"].append(
                    _result(
                        "latest_quote",
                        "FAIL",
                        message=f"No quote returned for {SYMBOL}.",
                        latency_ms=latency_ms,
                    )
                )
            else:
                report["checks"].append(
                    _result(
                        "latest_quote",
                        "PASS",
                        message=f"Latest quote returned for {SYMBOL}.",
                        latency_ms=latency_ms,
                        bid=float(getattr(quote_obj, "bid_price", 0) or 0),
                        ask=float(getattr(quote_obj, "ask_price", 0) or 0),
                        timestamp=str(getattr(quote_obj, "timestamp", "")),
                    )
                )

        # -----------------------------------------------------
        # Latest trade
        # -----------------------------------------------------

        trade_request = StockLatestTradeRequest(
            symbol_or_symbols=[SYMBOL],
            feed=feed,
        )

        trade, latency_ms, error = _timed_call(
            lambda: data_client.get_stock_latest_trade(trade_request)
        )

        if error:
            report["checks"].append(
                _result(
                    "latest_trade",
                    "FAIL",
                    message="Latest trade request failed.",
                    latency_ms=latency_ms,
                    **_exception_details(error),
                )
            )
        else:
            trade_obj = trade.get(SYMBOL)

            if trade_obj is None:
                report["checks"].append(
                    _result(
                        "latest_trade",
                        "FAIL",
                        message=f"No trade returned for {SYMBOL}.",
                        latency_ms=latency_ms,
                    )
                )
            else:
                report["checks"].append(
                    _result(
                        "latest_trade",
                        "PASS",
                        message=f"Latest trade returned for {SYMBOL}.",
                        latency_ms=latency_ms,
                        price=float(getattr(trade_obj, "price", 0) or 0),
                        size=int(getattr(trade_obj, "size", 0) or 0),
                        timestamp=str(getattr(trade_obj, "timestamp", "")),
                    )
                )

        # -----------------------------------------------------
        # Latest bar
        # -----------------------------------------------------

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=10)

        latest_bar_request = StockBarsRequest(
            symbol_or_symbols=[SYMBOL],
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            limit=1,
            feed=feed,
        )

        latest_bars, latency_ms, error = _timed_call(
            lambda: data_client.get_stock_bars(latest_bar_request)
        )

        if error:
            report["checks"].append(
                _result(
                    "latest_bar",
                    "FAIL",
                    message="Latest bar request failed.",
                    latency_ms=latency_ms,
                    **_exception_details(error),
                )
            )
        else:
            df = latest_bars.df.reset_index()

            if df.empty:
                report["checks"].append(
                    _result(
                        "latest_bar",
                        "FAIL",
                        message=f"No latest bar returned for {SYMBOL}.",
                        latency_ms=latency_ms,
                    )
                )
            else:
                newest = df.iloc[-1]

                report["checks"].append(
                    _result(
                        "latest_bar",
                        "PASS",
                        message=f"Latest daily bar returned for {SYMBOL}.",
                        latency_ms=latency_ms,
                        timestamp=str(newest.get("timestamp")),
                        close=float(newest.get("close", 0)),
                        volume=float(newest.get("volume", 0)),
                    )
                )

        # -----------------------------------------------------
        # Historical bars
        # -----------------------------------------------------

        start = end - timedelta(days=HISTORICAL_DAYS)

        historical_request = StockBarsRequest(
            symbol_or_symbols=[SYMBOL],
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            feed=feed,
        )

        historical, latency_ms, error = _timed_call(
            lambda: data_client.get_stock_bars(historical_request)
        )

        if error:
            report["checks"].append(
                _result(
                    "historical_bars",
                    "FAIL",
                    message="Historical bars request failed.",
                    latency_ms=latency_ms,
                    **_exception_details(error),
                )
            )
        else:
            df = historical.df.reset_index()

            if df.empty:
                report["checks"].append(
                    _result(
                        "historical_bars",
                        "FAIL",
                        message=f"No historical bars returned for {SYMBOL}.",
                        latency_ms=latency_ms,
                        bars_received=0,
                    )
                )
            else:
                newest = df.iloc[-1]["timestamp"]
                oldest = df.iloc[0]["timestamp"]
                bars_received = len(df)

                status = "PASS" if bars_received >= EXPECTED_BARS else "WARNING"

                report["checks"].append(
                    _result(
                        "historical_bars",
                        status,
                        message=(
                            f"Received {bars_received} historical bars."
                        ),
                        latency_ms=latency_ms,
                        bars_received=bars_received,
                        expected_minimum=EXPECTED_BARS,
                        newest_bar=str(newest),
                        oldest_bar=str(oldest),
                    )
                )

    except Exception as exc:
        report["checks"].append(
            _result(
                "market_data_client",
                "FAIL",
                message="Could not initialize/use Alpaca market-data client.",
                **_exception_details(exc),
            )
        )

    # ---------------------------------------------------------
    # Rate limit observation
    # ---------------------------------------------------------

    rate_limit_seen = False

    for check in report["checks"]:
        if check.get("http_status") == 429:
            rate_limit_seen = True

    report["checks"].append(
        _result(
            "rate_limit_response",
            "WARNING",
            message=(
                "No 429 response was intentionally generated. "
                "Any observed 429 response is recorded above."
            ),
            rate_limit_observed=rate_limit_seen,
        )
    )

    failures = [
        c for c in report["checks"]
        if c["status"] == "FAIL"
    ]

    warnings = [
        c for c in report["checks"]
        if c["status"] == "WARNING"
    ]

    report["status"] = (
        "FAIL"
        if failures
        else "WARNING"
        if warnings
        else "PASS"
    )

    report["finished_at"] = datetime.now(timezone.utc).isoformat()

    return report


def main() -> None:
    report = run()

    print(json.dumps(report, indent=2, default=str))

    if report["status"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()