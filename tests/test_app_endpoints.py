from __future__ import annotations

import json
from unittest.mock import Mock, patch
import pandas as pd
import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index_and_favicon(client):
    res_index = client.get("/")
    assert res_index.status_code == 200

    res_fav = client.get("/favicon.ico")
    assert res_fav.status_code in {200, 404}


def test_diagnostics_endpoint(client):
    res = client.get("/api/diagnostics")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert "alpaca" in data["services"]
    assert "finnhub" in data["services"]
    assert "gemini" in data["services"]


def test_diagnostics_is_a_data_source_registry(client):
    """PHASES_PLAN.md Phase 13 -- every service reports purpose + status,
    Alpaca additionally reports its feed, so a missing service is immediately
    visible instead of discovered mid-analysis."""
    res = client.get("/api/diagnostics")
    services = res.get_json()["services"]

    for key in ("alpaca", "finnhub", "gemini"):
        svc = services[key]
        assert svc.get("purpose"), f"{key} missing a purpose"
        assert svc.get("status") in {"connected", "missing_key", "missing_keys"}

    assert services["alpaca"]["feed"] == "IEX"
    assert isinstance(services["alpaca"]["market_hours_open"], bool)
    assert services["alpaca"]["rate_limit"]["limit_per_minute"] > 0


def test_chat_endpoint_technical_agent(client, monkeypatch):
    monkeypatch.setattr(
        "app.technical_agent.analyze",
        lambda symbol: {
            "status": "technical analysis ready",
            "symbol": symbol.upper(),
            "signals": {"rsi_14": 55.0, "ema_20": 100.0, "macd": 0.5, "change_percent": 1.2, "relative_volume": 1.5},
        },
    )
    res = client.post("/chat", json={"message": "Analyze AAPL", "agent_id": "technical_agent"})
    assert res.status_code == 200
    data = res.get_json()
    assert "Technical snapshot for AAPL" in data["response"]
    assert data["symbol"] == "AAPL"


def test_chat_endpoint_unknown_agent(client):
    res = client.post("/chat", json={"message": "Hello", "agent_id": "unknown"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["response"] == "Unknown agent."


def test_messages_and_sessions_endpoints(client):
    res_sessions = client.get("/api/sessions")
    assert res_sessions.status_code == 200
    assert "sessions" in res_sessions.get_json()

    res_messages = client.get("/api/messages?since=0")
    assert res_messages.status_code == 200
    assert "messages" in res_messages.get_json()


def test_account_and_positions_endpoints(client, monkeypatch):
    monkeypatch.setattr(
        "app.portfolio_agent.get_account_summary",
        lambda: {"cash": "10000.0", "equity": "12000.0", "buying_power": "20000.0", "portfolio_value": "12000.0"},
    )
    res_acct = client.get("/api/account")
    assert res_acct.status_code == 200
    data = res_acct.get_json()
    assert data["cash"] == "10000.0"

    monkeypatch.setattr(
        "app.portfolio_agent.analyze",
        lambda symbol: {"status": "portfolio check ready", "all_positions": [], "account": {}},
    )
    res_pos = client.get("/api/positions")
    assert res_pos.status_code == 200
    assert "all_positions" in res_pos.get_json()


def test_history_endpoints(client):
    res_hist = client.get("/api/history?limit=10")
    assert res_hist.status_code == 200
    assert isinstance(res_hist.get_json(), list)

    res_stats = client.get("/api/history/stats")
    assert res_stats.status_code == 200
    assert "total_orders" in res_stats.get_json()


def test_screener_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        "app.screener.screen",
        lambda symbols=None, top_n=10: {
            "status": "screening complete",
            "candidates": [{"symbol": "AAPL", "score": 3.5}],
            "total_scanned": 1,
            "matches": 1,
        },
    )
    res = client.post("/api/screen", json={"symbols": ["AAPL"], "top_n": 5})
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "screening complete"
    assert len(data["candidates"]) == 1


def test_sizing_endpoint(client):
    # Volatility target
    res_vt = client.post("/api/sizing", json={"equity": 100000, "price": 100, "atr": 2.0, "method": "vol_target"})
    assert res_vt.status_code == 200
    data_vt = res_vt.get_json()
    assert data_vt["status"] == "ok"
    assert data_vt["shares"] > 0

    # Risk parity
    res_rp = client.post("/api/sizing", json={"equity": 100000, "price": 100, "atr": 2.0, "method": "risk_parity"})
    assert res_rp.status_code == 200
    assert res_rp.get_json()["status"] == "ok"

    # Kelly
    res_kelly = client.post("/api/sizing", json={"equity": 100000, "price": 100, "method": "kelly", "win_rate": 0.6, "avg_win": 150, "avg_loss": 100})
    assert res_kelly.status_code == 200
    assert res_kelly.get_json()["status"] == "ok"

    # Invalid input
    res_err = client.post("/api/sizing", json={"equity": 0, "price": 0})
    assert res_err.status_code == 400


def test_search_endpoint(client):
    res = client.post("/api/search", json={"query": "AAPL momentum buy", "top_k": 3})
    assert res.status_code == 200
    data = res.get_json()
    assert "results" in data


def test_weights_endpoint(client):
    res = client.get("/api/weights")
    assert res.status_code == 200
    assert "weights" in res.get_json()


def test_daily_report_endpoint(client):
    res = client.get("/api/report/daily")
    assert res.status_code == 200
    data = res.get_json()
    assert data["report_type"] == "daily"
    assert "summary" in data


def test_chart_data_endpoint(client, monkeypatch):
    dates = pd.date_range("2026-01-01", periods=100, freq="D")
    bars_df = pd.DataFrame({
        "timestamp": dates,
        "open": [100.0 + i for i in range(100)],
        "high": [102.0 + i for i in range(100)],
        "low": [98.0 + i for i in range(100)],
        "close": [101.0 + i for i in range(100)],
        "volume": [10000 + i * 10 for i in range(100)],
    })

    class FakeSnapshot:
        bars = bars_df

    monkeypatch.setattr("agents.market_agent.MarketAgent.snapshot", lambda *args, **kwargs: FakeSnapshot())

    res = client.post("/api/chart_data", json={"symbol": "AAPL", "days": 90})
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert data["symbol"] == "AAPL"
    assert len(data["close"]) == 100
    assert len(data["ema20"]) == 100
    assert len(data["rsi"]) == 100
