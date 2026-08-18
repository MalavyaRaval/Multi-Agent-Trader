from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from agents.execution_agent import ExecutionAgent
from agents.fundamental_agent import FundamentalAgent
from agents.market_agent import MarketAgent, MarketQuote, MarketTrade
from agents.risk_agent import RiskAgent
from agents.technical_agent import TechnicalAgent


class FakeMarket:
    def __init__(self, bars: pd.DataFrame, metrics=None):
        self.bars = bars
        self.metrics = metrics or {
            "relative_volume": 1.2,
            "change_percent": 0.5,
            "spread": 0.1,
            "previous_close": 100.0,
            "vwap": 100.5,
        }
        self.quote = MarketQuote(
            symbol="AAPL",
            bid_price=100.0,
            ask_price=101.0,
            bid_size=10,
            ask_size=10,
            timestamp=pd.Timestamp("2026-01-01").to_pydatetime(),
            source="alpaca",
            status="ok",
        )
        self.trade = MarketTrade(
            symbol="AAPL",
            price=101.5,
            size=5,
            timestamp=pd.Timestamp("2026-01-01").to_pydatetime(),
            source="alpaca",
            status="ok",
        )

    def snapshot(self, symbol, timeframe="1d", days=200):
        return SimpleNamespace(symbol=symbol, bars=self.bars, metrics=self.metrics, timeframe=timeframe)


@pytest.fixture
def valid_ohlcv_200():
    closes = [100.0 + i * 0.2 for i in range(200)]
    highs = [c + 1.5 for c in closes]
    lows = [c - 1.5 for c in closes]
    opens = [c - 0.7 for c in closes]
    volumes = [1000 + i for i in range(200)]
    return pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )


def test_valid_alpaca_quote_returns_status_ok(monkeypatch):
    agent = MarketAgent()

    class FakeClient:
        def get_stock_latest_quote(self, request):
            return {"AAPL": SimpleNamespace(bid_price=100.0, ask_price=101.0, bid_size=10, ask_size=12, timestamp=pd.Timestamp("2026-01-01"))}

    agent.client = FakeClient()
    quote = agent.latest_quote("AAPL")

    assert quote.status == "ok"
    assert quote.bid_price == 100.0
    assert quote.ask_price == 101.0


def test_invalid_alpaca_quote_is_marked_invalid(monkeypatch):
    agent = MarketAgent()

    class FakeClient:
        def get_stock_latest_quote(self, request):
            return {"AAPL": SimpleNamespace(bid_price=10.0, ask_price=200.0, bid_size=10, ask_size=12, timestamp=pd.Timestamp("2026-01-01"))}

    agent.client = FakeClient()
    quote = agent.latest_quote("AAPL")

    assert quote.status == "invalid"


def test_suspiciously_wide_spread_is_flagged_invalid(monkeypatch):
    agent = MarketAgent()

    class FakeClient:
        def get_stock_latest_quote(self, request):
            return {"AAPL": SimpleNamespace(bid_price=50.0, ask_price=60.0, bid_size=10, ask_size=12, timestamp=pd.Timestamp("2026-01-01"))}

    agent.client = FakeClient()
    quote = agent.latest_quote("AAPL")

    assert quote.status == "invalid"


def test_missing_fundamental_fields_remain_none(monkeypatch):
    agent = FundamentalAgent()
    monkeypatch.setattr(agent.finnhub, "company_profile", lambda symbol: {"name": "Example", "finnhubIndustry": "Automobiles"})
    monkeypatch.setattr(agent.finnhub, "basic_financials", lambda symbol: {"metric": {"peBasicExclExtraTTM": None, "epsBasicExclExtraTTM": None, "beta": None}})

    result = agent.analyze("TSLA")

    assert result["status"] in {"partial", "ok"}
    assert result["pe"] is None
    assert result["eps"] is None
    assert result["beta"] is None
    assert result["score"] is None


def test_fundamental_api_failure_returns_error_status(monkeypatch):
    agent = FundamentalAgent()
    monkeypatch.setattr(agent.finnhub, "company_profile", lambda symbol: {"error": "bad key"})

    result = agent.analyze("TSLA")

    assert result["status"] == "error"
    assert result["error"]


def test_risk_agent_receiving_none_symbol_returns_error():
    result = RiskAgent().analyze(None)

    assert result["status"] == "error"
    assert result["risk_level"] == "unknown"


def test_risk_agent_api_failure_returns_error(monkeypatch):
    agent = RiskAgent()
    monkeypatch.setattr(agent.market, "snapshot", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("market failure")))

    result = agent.analyze("AAPL")

    assert result["status"] == "error"
    assert result["risk_level"] == "unknown"
    assert "market failure" in result["error"]


def test_technical_calculation_with_valid_200_bars(valid_ohlcv_200):
    agent = TechnicalAgent(market_agent=FakeMarket(valid_ohlcv_200))
    result = agent.analyze("AAPL")

    assert result["status"] == "ok"
    assert result["source"] == "Alpaca"
    assert result["bars_used"] == 200
    assert "rsi_14" in result["signals"]
    assert "macd" in result["signals"]
    assert "macd_signal" in result["signals"]
    assert "macd_hist" in result["signals"]
    assert "ema_20" in result["signals"]
    assert "ema_50" in result["signals"]
    assert "bollinger_middle" in result["signals"]
    assert "atr_14" in result["signals"]


def test_technical_calculation_with_insufficient_bars():
    bars = pd.DataFrame({
        "open": [100.0] * 20,
        "high": [101.0] * 20,
        "low": [99.0] * 20,
        "close": [100.0] * 20,
        "volume": [1000] * 20,
    })
    agent = TechnicalAgent(market_agent=FakeMarket(bars))

    result = agent.analyze("AAPL")

    assert result["status"] == "error"


def test_execution_with_missing_fundamentals():
    agent = ExecutionAgent()
    context = {
        "market": {"metrics": {"relative_volume": 1.2, "change_percent": 0.5, "spread": 0.1}},
        "technical": {
            "status": "ok",
            "signals": {
                "rsi_14": 52.0,
                "macd": 0.4,
                "macd_signal": 0.2,
                "ema_20": 101.0,
                "ema_50": 100.0,
                "atr_14": 1.2,
                "last_price": 100.5,
            },
        },
        "fundamental": {"score": None},
        "news": {"sentiment": "neutral"},
        "risk": {"status": "ok", "risk_level": "medium"},
        "portfolio": {"position": {"qty": 0}},
    }

    result = agent.analyze("AAPL", context=context)

    assert result["data_quality"]["fundamental"] is False
    assert result["action"] in {"buy", "sell", "hold"}


def test_execution_with_risk_failure():
    agent = ExecutionAgent()
    context = {
        "market": {"metrics": {"relative_volume": 1.2, "change_percent": 0.5, "spread": 0.1}},
        "technical": {
            "status": "ok",
            "signals": {
                "rsi_14": 52.0,
                "macd": 0.4,
                "macd_signal": 0.2,
                "ema_20": 101.0,
                "ema_50": 100.0,
                "atr_14": 1.2,
                "last_price": 100.5,
            },
        },
        "fundamental": {"score": 1},
        "news": {"sentiment": "neutral"},
        "risk": {"status": "error", "risk_level": "unknown", "error": "risk failed"},
        "portfolio": {"position": {"qty": 0}},
    }

    result = agent.analyze("AAPL", context=context)

    assert result["status"] == "risk_error"
    assert result["action"] == "hold"
    assert result["confidence"] == 0.0


def test_execution_with_valid_data_from_all_agents():
    agent = ExecutionAgent()
    context = {
        "market": {"metrics": {"relative_volume": 1.2, "change_percent": 0.5, "spread": 0.1}},
        "technical": {
            "status": "ok",
            "signals": {
                "rsi_14": 52.0,
                "macd": 0.4,
                "macd_signal": 0.2,
                "ema_20": 101.0,
                "ema_50": 100.0,
                "atr_14": 1.2,
                "last_price": 100.5,
                "volume_trend": "buy",
            },
        },
        "fundamental": {"score": 1},
        "news": {"sentiment": "positive"},
        "risk": {"status": "ok", "risk_level": "low"},
        "portfolio": {"position": {"qty": 0}},
    }

    result = agent.analyze("AAPL", context=context)

    assert result["status"] == "execution analysis ready"
    assert result["data_quality_score"] >= 60
