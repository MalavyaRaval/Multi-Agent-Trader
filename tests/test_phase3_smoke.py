import pandas as pd

from app import app
from backtesting.engine import BacktestEngine


def test_reflection_endpoint_returns_fallback_payload():
    client = app.test_client()
    response = client.post(
        "/api/reflection",
        json={"trades": [{"symbol": "AAPL", "pnl": 25.0, "reason": "Momentum breakout"}]},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert "reflection" in payload


def test_backtest_engine_handles_empty_history(monkeypatch):
    engine = BacktestEngine()

    class DummySnapshot:
        bars = pd.DataFrame(columns=["close", "volume"])
        metrics = {}
        trade = None

    monkeypatch.setattr(engine.market, "snapshot", lambda *args, **kwargs: DummySnapshot())

    result = engine.run("AAPL", days=30)

    assert result.total_trades == 0
    assert result.final_cash == engine.initial_cash
