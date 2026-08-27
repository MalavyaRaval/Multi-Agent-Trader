from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd
import pytest

import agents.market_agent as market_agent_module
import config
from agents.market_agent import (
    MARKET_DATA_FEED,
    MarketAgent,
    get_rate_limit_status,
    is_market_hours_now,
)


@pytest.fixture(autouse=True)
def _isolated_rate_limit_log(monkeypatch):
    """The rate-limit tracker is module-level shared state; give each test a
    fresh deque so tests don't leak request counts into each other."""
    monkeypatch.setattr(market_agent_module, "_request_log", deque())
    yield


def _bars_response(n=100):
    now = pd.Timestamp.now(tz="UTC")
    closes = [100.0 + i * 0.1 for i in range(n)]
    df = pd.DataFrame(
        {
            "timestamp": [now - pd.Timedelta(days=n - i) for i in range(n)],
            "symbol": ["AAPL"] * n,
            "open": [c - 0.5 for c in closes],
            "high": [c + 1 for c in closes],
            "low": [c - 1 for c in closes],
            "close": closes,
            "volume": [1000 + i for i in range(n)],
        }
    )
    return SimpleNamespace(df=df)


class FakeClient:
    def get_stock_bars(self, request):
        return _bars_response()

    def get_stock_latest_quote(self, request):
        return {
            "AAPL": SimpleNamespace(
                bid_price=100.0, ask_price=101.0, bid_size=10, ask_size=12,
                timestamp=pd.Timestamp("2026-01-01"),
            )
        }

    def get_stock_latest_trade(self, request):
        return {
            "AAPL": SimpleNamespace(price=101.5, size=5, timestamp=pd.Timestamp("2026-01-01"))
        }


# ---------------------------------------------------------------
# Feed reporting
# ---------------------------------------------------------------

def test_market_data_feed_matches_config():
    assert MARKET_DATA_FEED.value == config.ALPACA_DATA_FEED


def test_snapshot_reports_configured_feed():
    agent = MarketAgent()
    agent.client = FakeClient()

    snapshot = agent.snapshot("AAPL")

    assert snapshot.feed == MARKET_DATA_FEED.value


def test_snapshot_without_client_still_reports_market_hours():
    agent = MarketAgent()
    agent.client = None

    snapshot = agent.snapshot("AAPL")

    assert snapshot.feed == ""
    assert isinstance(snapshot.market_hours_open, bool)


# ---------------------------------------------------------------
# Request timing
# ---------------------------------------------------------------

def test_snapshot_records_request_timings_for_all_three_calls():
    agent = MarketAgent()
    agent.client = FakeClient()

    snapshot = agent.snapshot("AAPL")

    assert set(snapshot.request_timings_ms.keys()) == {"bars", "quote", "trade"}
    for value in snapshot.request_timings_ms.values():
        assert isinstance(value, float)
        assert value >= 0.0


# ---------------------------------------------------------------
# Rate-limit tracking
# ---------------------------------------------------------------

def test_rate_limit_status_starts_empty():
    status = get_rate_limit_status()
    assert status["requests_last_60s"] == 0
    assert status["limit_per_minute"] == config.ALPACA_DATA_RATE_LIMIT_PER_MIN
    assert status["remaining_estimate"] == config.ALPACA_DATA_RATE_LIMIT_PER_MIN


def test_real_calls_increment_rate_limit_counter():
    agent = MarketAgent()
    agent.client = FakeClient()

    agent.latest_quote("AAPL")
    agent.latest_trade("AAPL")

    status = get_rate_limit_status()
    assert status["requests_last_60s"] == 2
    assert status["remaining_estimate"] == config.ALPACA_DATA_RATE_LIMIT_PER_MIN - 2


def test_cache_hits_do_not_increment_rate_limit_counter():
    agent = MarketAgent()
    agent.client = FakeClient()

    agent.historical_bars("AAPL")  # real request
    agent.historical_bars("AAPL")  # served from cache

    status = get_rate_limit_status()
    assert status["requests_last_60s"] == 1


def test_rate_limit_window_prunes_old_entries():
    now = market_agent_module.time.monotonic()
    market_agent_module._request_log.extend([now - 120, now - 90, now - 30])

    status = get_rate_limit_status()

    assert status["requests_last_60s"] == 1


# ---------------------------------------------------------------
# Market-hours awareness
# ---------------------------------------------------------------

class _FixedDatetime(datetime):
    _fixed = datetime(2026, 1, 5, 15, 0, tzinfo=timezone.utc)  # Monday

    @classmethod
    def now(cls, tz=None):
        value = cls._fixed
        return value.astimezone(tz) if tz else value


def test_market_hours_open_on_weekday_during_session(monkeypatch):
    fixed = _FixedDatetime
    fixed._fixed = datetime(2026, 1, 5, 15, 0, tzinfo=timezone.utc)  # 10:00 ET, Monday
    monkeypatch.setattr(market_agent_module, "datetime", fixed)

    assert is_market_hours_now() is True


def test_market_hours_closed_outside_session(monkeypatch):
    fixed = _FixedDatetime
    fixed._fixed = datetime(2026, 1, 5, 3, 0, tzinfo=timezone.utc)  # ~22:00 ET, still Monday
    monkeypatch.setattr(market_agent_module, "datetime", fixed)

    assert is_market_hours_now() is False


def test_market_hours_closed_on_weekend(monkeypatch):
    fixed = _FixedDatetime
    fixed._fixed = datetime(2026, 1, 3, 15, 0, tzinfo=timezone.utc)  # Saturday
    monkeypatch.setattr(market_agent_module, "datetime", fixed)

    assert is_market_hours_now() is False
