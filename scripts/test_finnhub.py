"""
scripts/test_finnhub.py

Phase 0 - Finnhub baseline health check.

Tests:
- API key presence
- API authentication
- company profile
- quote
- financial data
- company news
- response freshness
- empty response handling
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE = "https://finnhub.io/api/v1"
SYMBOL = os.getenv("DEFAULT_SYMBOL", "AAPL").upper()
TIMEOUT = float(os.getenv("FINNHUB_TIMEOUT_SECONDS", "10"))


def _check(
    name: str,
    status: str,
    message: str = "",
    **extra: Any,
) -> Dict[str, Any]:
    result = {
        "name": name,
        "status": status,
        "message": message,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    result.update(extra)
    return result


def _request(
    endpoint: str,
    params: Dict[str, Any],
) -> tuple[Any, float, requests.Response | None, Exception | None]:

    started = time.perf_counter()

    try:
        response = requests.get(
            f"{API_BASE}/{endpoint}",
            params=params,
            timeout=TIMEOUT,
        )

        latency_ms = (time.perf_counter() - started) * 1000

        try:
            payload = response.json()
        except ValueError:
            payload = response.text

        if not response.ok:
            error = RuntimeError(
                f"HTTP {response.status_code}: {payload}"
            )
            return payload, latency_ms, response, error

        return payload, latency_ms, response, None

    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return None, latency_ms, None, exc


def run() -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "service": "finnhub",
        "symbol": SYMBOL,
        "checks": [],
    }

    api_key = os.getenv("FINNHUB_API_KEY")

    if not api_key:
        report["checks"].append(
            _check(
                "credentials",
                "FAIL",
                "FINNHUB_API_KEY is missing.",
            )
        )
        report["status"] = "FAIL"
        return report

    report["checks"].append(
        _check(
            "credentials",
            "PASS",
            "FINNHUB_API_KEY is present.",
        )
    )

    # ---------------------------------------------------------
    # Company profile
    # ---------------------------------------------------------

    profile, latency, response, error = _request(
        "stock/profile2",
        {
            "symbol": SYMBOL,
            "token": api_key,
        },
    )

    if error:
        report["checks"].append(
            _check(
                "company_profile",
                "FAIL",
                str(error),
                latency_ms=latency,
                http_status=response.status_code if response else None,
            )
        )
    elif not profile:
        report["checks"].append(
            _check(
                "company_profile",
                "WARNING",
                "Finnhub returned an empty company profile.",
                latency_ms=latency,
            )
        )
    else:
        report["checks"].append(
            _check(
                "company_profile",
                "PASS",
                "Company profile returned.",
                latency_ms=latency,
                company_name=profile.get("name"),
                exchange=profile.get("exchange"),
            )
        )

    # ---------------------------------------------------------
    # Quote
    # ---------------------------------------------------------

    quote, latency, response, error = _request(
        "quote",
        {
            "symbol": SYMBOL,
            "token": api_key,
        },
    )

    if error:
        report["checks"].append(
            _check(
                "quote",
                "FAIL",
                str(error),
                latency_ms=latency,
                http_status=response.status_code if response else None,
            )
        )
    elif not quote:
        report["checks"].append(
            _check(
                "quote",
                "WARNING",
                "Finnhub returned an empty quote.",
                latency_ms=latency,
            )
        )
    else:
        quote_timestamp = quote.get("t")

        freshness_seconds = None

        if quote_timestamp:
            freshness_seconds = (
                datetime.now(timezone.utc).timestamp()
                - float(quote_timestamp)
            )

        report["checks"].append(
            _check(
                "quote",
                "PASS",
                "Quote returned.",
                latency_ms=latency,
                current_price=quote.get("c"),
                previous_close=quote.get("pc"),
                quote_timestamp=quote_timestamp,
                freshness_seconds=freshness_seconds,
            )
        )

    # ---------------------------------------------------------
    # Financial data
    # ---------------------------------------------------------

    financials, latency, response, error = _request(
        "stock/metric",
        {
            "symbol": SYMBOL,
            "metric": "all",
            "token": api_key,
        },
    )

    if error:
        status = (
            "WARNING"
            if response is not None and response.status_code in (403, 429)
            else "FAIL"
        )

        report["checks"].append(
            _check(
                "financial_data",
                status,
                str(error),
                latency_ms=latency,
                http_status=response.status_code if response else None,
            )
        )
    elif not financials:
        report["checks"].append(
            _check(
                "financial_data",
                "WARNING",
                "Finnhub returned an empty financial-data response.",
                latency_ms=latency,
            )
        )
    else:
        metric = financials.get("metric", {})

        report["checks"].append(
            _check(
                "financial_data",
                "PASS",
                "Financial metrics returned.",
                latency_ms=latency,
                metric_count=len(metric),
                pe_ratio=metric.get("peBasicExclExtraTTM"),
                eps=metric.get("epsBasicExclExtraItemsTTM"),
            )
        )

    # ---------------------------------------------------------
    # News
    # ---------------------------------------------------------

    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=7)

    news, latency, response, error = _request(
        "company-news",
        {
            "symbol": SYMBOL,
            "from": start_date.isoformat(),
            "to": today.isoformat(),
            "token": api_key,
        },
    )

    if error:
        status = (
            "WARNING"
            if response is not None and response.status_code in (403, 429)
            else "FAIL"
        )

        report["checks"].append(
            _check(
                "news",
                status,
                str(error),
                latency_ms=latency,
                http_status=response.status_code if response else None,
            )
        )
    elif news is None:
        report["checks"].append(
            _check(
                "news",
                "WARNING",
                "News endpoint returned no response.",
                latency_ms=latency,
            )
        )
    elif not isinstance(news, list):
        report["checks"].append(
            _check(
                "news",
                "WARNING",
                "News endpoint returned an unexpected response type.",
                latency_ms=latency,
                response_type=type(news).__name__,
            )
        )
    elif len(news) == 0:
        report["checks"].append(
            _check(
                "news",
                "WARNING",
                "News endpoint returned an empty article list.",
                latency_ms=latency,
                articles_returned=0,
            )
        )
    else:
        newest_timestamp = news[0].get("datetime")

        freshness_seconds = None

        if newest_timestamp:
            freshness_seconds = (
                datetime.now(timezone.utc).timestamp()
                - float(newest_timestamp)
            )

        report["checks"].append(
            _check(
                "news",
                "PASS",
                "News returned successfully.",
                latency_ms=latency,
                articles_returned=len(news),
                newest_article_timestamp=newest_timestamp,
                freshness_seconds=freshness_seconds,
            )
        )

    # ---------------------------------------------------------
    # Overall
    # ---------------------------------------------------------

    failures = [
        item for item in report["checks"]
        if item["status"] == "FAIL"
    ]

    warnings = [
        item for item in report["checks"]
        if item["status"] == "WARNING"
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