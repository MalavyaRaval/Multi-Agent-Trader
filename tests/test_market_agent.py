import importlib
import os


def test_snapshot_falls_back_when_sip_data_is_unavailable(monkeypatch):
    os.environ.setdefault("ALPACA_API_KEY", "test")
    os.environ.setdefault("ALPACA_SECRET_KEY", "test")

    import agents.market_agent as market_agent_module

    market_agent_module = importlib.reload(market_agent_module)

    class FakeClient:
        def get_stock_latest_quote(self, request):
            raise Exception("subscription does not permit querying recent SIP data")

        def get_stock_latest_trade(self, request):
            raise Exception("subscription does not permit querying recent SIP data")

        def get_stock_bars(self, request):
            raise Exception("subscription does not permit querying recent SIP data")

    agent = market_agent_module.MarketAgent(cache_ttl_seconds=1)
    agent.client = FakeClient()

    snapshot = agent.snapshot("AAPL", timeframe="1d", days=5)

    assert snapshot.symbol == "AAPL"
    assert snapshot.quote is not None
    assert snapshot.trade is not None
    assert snapshot.bars.empty
    assert snapshot.metrics["change_percent"] is None
