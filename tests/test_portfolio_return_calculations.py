from unittest.mock import Mock

import pandas as pd
import pytest

from visualization.portfolio import (
    calculate_position_period_return,
    compute_range_return_pct,
    get_stock_bars,
    summarize_portfolio_period,
)
from orchestrator import Orchestrator


def test_orchestrator_returns_run_id_for_each_analysis(monkeypatch):
    orchestrator = Orchestrator()

    class FakeSnapshot:
        trade = Mock(price=100.0)
        metrics = {"relative_volume": 1.25, "spread": 0.05}

    monkeypatch.setattr(orchestrator.market, "snapshot", lambda *args, **kwargs: FakeSnapshot())
    monkeypatch.setattr(
        orchestrator.technical,
        "analyze",
        lambda symbol: {
            "status": "technical analysis ready",
            "signals": {
                "rsi_14": 52.0,
                "macd": 0.5,
                "macd_signal": 0.2,
                "ema_20": 100.5,
                "ema_50": 99.5,
                "atr_14": 1.2,
            },
        },
    )
    monkeypatch.setattr(
        orchestrator.fundamental,
        "analyze",
        lambda symbol: {"status": "fundamental analysis ready", "data": {"pe": 22.0}},
    )
    monkeypatch.setattr(
        orchestrator.news,
        "analyze",
        lambda symbol: {"status": "news analysis ready", "articles": [], "sentiment": "neutral"},
    )
    monkeypatch.setattr(
        orchestrator.risk,
        "analyze",
        lambda symbol: {"status": "risk analysis ready", "risk_level": "medium", "checks": {}},
    )
    monkeypatch.setattr(
        orchestrator.portfolio,
        "analyze",
        lambda symbol: {"status": "portfolio analysis ready", "data": {"equity": 1000.0}},
    )
    monkeypatch.setattr(
        orchestrator.execution,
        "analyze",
        lambda symbol, context=None: {"status": "execution analysis ready", "action": "hold", "confidence": 0.1, "reason": "test"},
    )

    result = orchestrator.analyze_symbol("aapl")

    assert result["run_id"].startswith("RUN-")
    assert result["symbol"] == "AAPL"
    assert result["status"] == "completed"
    assert result["started_at"]
    assert orchestrator.bus.get_messages(session_id=result["run_id"]) 


def test_compute_range_return_pct_uses_first_valid_equity_baseline():
    df = pd.DataFrame(
        {
            "equity": [0.0, 0.0, 1000.0, 1100.0, 1200.0],
            "profit_loss_pct": [None, None, None, None, None],
        }
    )

    result = compute_range_return_pct(df)

    assert result.tolist() == [0.0, 0.0, 0.0, 10.0, 20.0]


def test_compute_range_return_pct_ignores_alpaca_profit_loss_pct():
    df = pd.DataFrame(
        {
            "equity": [0.0, 0.0, 500.0, 550.0, 600.0],
            "profit_loss_pct": [0.0, 0.0, 0.0, 10.0, 20.0],
        }
    )

    result = compute_range_return_pct(df)

    assert result.tolist() == [0.0, 0.0, 0.0, 10.0, 20.0]


def test_summarize_portfolio_period():
    df = pd.DataFrame(
        {
            "equity": [1000.0, 1100.0, 1050.0],
            "return_pct": [0.0, 10.0, 5.0],
        }
    )

    summary = summarize_portfolio_period(df)

    assert summary["current_value"] == 1050.0
    assert summary["period_return_pct"] == 5.0
    assert summary["period_start_equity"] == 1000.0


def test_calculate_position_period_return_uses_first_owned_bar_as_baseline():
    position_df = pd.DataFrame(
        {
            "symbol": ["AAPL", "AAPL", "AAPL", "AAPL"],
            "timestamp": pd.to_datetime(
                [
                    "2026-01-01",
                    "2026-01-02",
                    "2026-01-03",
                    "2026-01-04",
                ],
                utc=True,
            ),
            "qty": [0.0, 10.0, 10.0, 0.0],
            "close": [100.0, 100.0, 110.0, 105.0],
            "market_value": [0.0, 1000.0, 1100.0, 0.0],
        }
    )

    result = calculate_position_period_return(
        position_df,
        "AAPL",
    )

    assert pd.isna(result.iloc[0]["return_pct"])
    assert result.iloc[1]["return_pct"] == 0.0
    assert result.iloc[2]["return_pct"] == pytest.approx(10.0)
    assert pd.isna(result.iloc[3]["return_pct"])


def test_get_stock_bars_falls_back_to_sip_when_iex_has_no_data(monkeypatch):
    feed_calls = []

    def fake_get(url, headers=None, params=None, timeout=None):
        feed_calls.append(params["feed"])

        if params["feed"] == "iex":
            return Mock(
                raise_for_status=lambda: None,
                json=lambda: {"bars": []},
            )

        return Mock(
            raise_for_status=lambda: None,
            json=lambda: {
                "bars": [
                    {"t": "2026-08-14T20:15:00Z", "c": 123.45},
                    {"t": "2026-08-14T20:20:00Z", "c": 124.00},
                ]
            },
        )

    monkeypatch.setattr("visualization.portfolio.requests.get", fake_get)

    result = get_stock_bars(
        ["AAPL"],
        pd.Timestamp("2026-08-14T20:00:00Z"),
        pd.Timestamp("2026-08-15T20:00:00Z"),
        "5Min",
    )

    assert feed_calls[:2] == ["iex", "sip"]
    assert len(result) == 2
    assert set(result["symbol"]) == {"AAPL"}


def test_neutral_signal_has_low_hold_confidence():
    from strategies.momentum import MomentumStrategy

    vote = MomentumStrategy().evaluate(
        {"technical": {"signals": {}}, "fundamental": {}, "news": {}}
    )

    assert vote["decision"] == "hold"
    assert vote["confidence"] == 0.0


def test_indicator_missing_data_returns_none_not_zero():
    import pandas as pd

    from indicators.atr import compute_atr
    from indicators.bollinger import compute_bollinger
    from indicators.ema import compute_ema
    from indicators.macd import compute_macd
    from indicators.rsi import compute_rsi
    from indicators.volume import compute_volume_signals

    short_close = pd.Series([100.0, 101.0, 102.0])
    short_high = pd.Series([101.0, 102.0, 103.0])
    short_low = pd.Series([99.0, 100.0, 101.0])
    short_volume = pd.Series([1000.0, 1001.0, 1002.0])

    assert compute_rsi(short_close, 14) is None
    assert compute_ema(short_close, 20) is None
    assert compute_macd(short_close, slow=26, signal=9) == (None, None, None)
    assert compute_atr(short_high, short_low, short_close, 14) is None
    assert compute_bollinger(short_close, 20) == (None, None, None)
    assert compute_volume_signals(short_volume, short_close) == {"volume_ratio": None, "volume_trend": "neutral"}
