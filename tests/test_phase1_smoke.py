from agents.technical_agent import TechnicalAgent
from agents.execution_agent import ExecutionAgent
from agents.portfolio_agent import PortfolioAgent


def test_technical_agent_handles_simple_list_input():
    class FakeMarketAgent:
        def snapshot(self, symbol, timeframe="1d", days=200):
            return type(
                "Snapshot",
                (),
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "metrics": {"relative_volume": 2.5, "change_percent": 3.2},
                    "bars": [{"close": 100, "high": 101, "low": 99, "volume": 1000} for _ in range(30)],
                },
            )()

    agent = TechnicalAgent(market_agent=FakeMarketAgent())
    result = agent.analyze("AAPL")

    assert result["status"] == "technical analysis ready"
    assert result["symbol"] == "AAPL"
    assert result["signals"]["change_percent"] == 3.2


def test_execution_agent_handles_missing_context():
    agent = ExecutionAgent()
    result = agent.analyze("AAPL", context={})
    assert result["status"] == "execution analysis skipped (no context)"


def test_portfolio_agent_handles_missing_client(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)

    agent = PortfolioAgent()
    result = agent.analyze("AAPL")
    assert result["status"] == "portfolio check skipped (no Alpaca client)"


def test_execution_agent_reduces_signal_strength_in_high_risk():
    class DummyStrategy:
        name = "dummy"

        def evaluate(self, context):
            return {"strategy": self.name, "decision": "buy", "confidence": 1.0}

    agent = ExecutionAgent()
    agent.strategies = [DummyStrategy() for _ in range(5)]

    result = agent.analyze(
        "AAPL",
        context={
            "technical": {"signals": {"rsi_14": 20, "macd": 1.2, "macd_signal": 0.2, "ema_20": 110, "ema_50": 100, "volume_trend": "strong_buy"}},
            "fundamental": {"score": 1.0},
            "news": {"sentiment": "positive"},
            "risk": {"risk_level": "high"},
            "portfolio": {},
        },
    )

    assert result["action"] == "hold"
    assert result["confidence"] < 0.5
