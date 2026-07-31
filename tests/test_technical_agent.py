from agents.technical_agent import TechnicalAgent


def test_analyze_uses_market_snapshot_when_available(monkeypatch):
    class FakeMarketAgent:
        def snapshot(self, symbol, timeframe="1d", days=200):
            return type(
                "Snapshot",
                (),
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "metrics": {"relative_volume": 2.5, "change_percent": 3.2},
                    "bars": [1, 2, 3],
                },
            )()

    agent = TechnicalAgent(market_agent=FakeMarketAgent())
    result = agent.analyze("AAPL")

    assert result["symbol"] == "AAPL"
    assert result["timeframe"] == "1d"
    assert result["signals"]["relative_volume"] == 2.5
    assert result["signals"]["change_percent"] == 3.2
    assert result["status"] == "technical analysis ready"
