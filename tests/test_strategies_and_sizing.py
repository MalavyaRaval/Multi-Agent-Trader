from __future__ import annotations

import math
from unittest.mock import Mock, patch
import pandas as pd
import pytest

from strategies.momentum import MomentumStrategy
from strategies.trend_following import TrendFollowingStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.breakout import BreakoutStrategy
from strategies.swing import SwingStrategy

from sizing.kelly import kelly_fraction, kelly_position_size, half_kelly
from sizing.vol_target import target_volatility_size, risk_parity_size

from optimization.ensemble import StrategyEnsemble
from memory.vector_store import VectorStore, _tokenize, _tf, _idf, _cosine_similarity
from memory.trade_history import TradeHistory
from memory.reflections import ReflectionEngine
from reporting.daily_report import build_daily_report
from backtesting.report import generate_report, format_report_text
from observability.events import EventRecord
from observability.metrics import MetricsCollector
from observability.logger import EventLogger
from observability.run_tracker import RunTracker
from agents.screener_agent import ScreenerAgent


# ---------------------------------------------------------------------------
# Strategy Tests
# ---------------------------------------------------------------------------

def test_momentum_strategy_bullish_and_bearish():
    strat = MomentumStrategy()
    
    # Bullish context
    bull_ctx = {
        "technical": {
            "signals": {
                "change_percent": 4.5,
                "volume_ratio": 2.0,
                "rsi_14": 58.0,
                "macd": 1.5,
                "macd_signal": 0.5,
            }
        },
        "news": {"sentiment": "positive"},
    }
    bull_res = strat.evaluate(bull_ctx)
    assert bull_res["decision"] == "buy"
    assert bull_res["confidence"] > 0.5
    assert bull_res["data_status"] == "ok"

    # Bearish context
    bear_ctx = {
        "technical": {
            "signals": {
                "change_percent": -4.0,
                "volume_ratio": 1.8,
                "rsi_14": 40.0,
                "macd": -1.2,
                "macd_signal": -0.2,
            }
        },
        "news": {"sentiment": "negative"},
    }
    bear_res = strat.evaluate(bear_ctx)
    assert bear_res["decision"] == "sell"
    assert bear_res["confidence"] > 0.5


def test_trend_following_strategy():
    strat = TrendFollowingStrategy()
    
    uptrend_ctx = {
        "technical": {
            "signals": {
                "ema_20": 110.0,
                "ema_50": 100.0,
                "bollinger_upper": 120.0,
                "bollinger_lower": 90.0,
                "volume_trend": "strong_buy",
                "atr_14": 1.5,
            }
        },
        "risk": {"risk_level": "low"},
    }
    res = strat.evaluate(uptrend_ctx)
    assert res["decision"] == "buy"
    assert res["strategy"] == "trend_following"

    downtrend_ctx = {
        "technical": {
            "signals": {
                "ema_20": 90.0,
                "ema_50": 100.0,
                "bollinger_upper": 110.0,
                "bollinger_lower": 80.0,
                "volume_trend": "strong_sell",
                "atr_14": 1.5,
            }
        },
        "risk": {"risk_level": "low"},
    }
    res_down = strat.evaluate(downtrend_ctx)
    assert res_down["decision"] == "sell"


def test_mean_reversion_strategy():
    strat = MeanReversionStrategy()
    
    # Deeply oversold -> buy
    oversold_ctx = {
        "technical": {
            "signals": {
                "rsi_14": 20.0,
                "bollinger_upper": 120.0,
                "bollinger_lower": 100.0,
                "ema_20": 101.0,
                "macd_hist": 0.2,
                "volume_ratio": 1.8,
            }
        }
    }
    res = strat.evaluate(oversold_ctx)
    assert res["decision"] == "buy"

    # Deeply overbought -> sell
    overbought_ctx = {
        "technical": {
            "signals": {
                "rsi_14": 82.0,
                "bollinger_upper": 120.0,
                "bollinger_lower": 100.0,
                "ema_20": 119.5,
                "macd_hist": -0.2,
                "volume_ratio": 1.8,
            }
        }
    }
    res_ob = strat.evaluate(overbought_ctx)
    assert res_ob["decision"] == "sell"


def test_breakout_strategy():
    strat = BreakoutStrategy()
    
    breakout_ctx = {
        "technical": {
            "signals": {
                "change_percent": 5.0,
                "volume_ratio": 2.5,
                "atr_14": 2.0,
                "bollinger_upper": 105.0,
                "bollinger_lower": 100.0,
                "rsi_14": 55.0,
            }
        }
    }
    res = strat.evaluate(breakout_ctx)
    assert res["decision"] == "buy"
    assert res["confidence"] > 0.5


def test_swing_strategy():
    strat = SwingStrategy()
    
    swing_ctx = {
        "technical": {
            "signals": {
                "rsi_14": 35.0,
                "macd": 1.0,
                "macd_signal": 0.5,
                "ema_20": 105.0,
                "ema_50": 100.0,
                "volume_ratio": 1.5,
            }
        },
        "fundamental": {"score": 1},
        "news": {"sentiment": "positive"},
        "risk": {"risk_level": "low"},
        "portfolio": {"position": None},
    }
    res = strat.evaluate(swing_ctx)
    assert res["decision"] == "buy"


# ---------------------------------------------------------------------------
# Sizing Tests
# ---------------------------------------------------------------------------

def test_volatility_targeting_and_risk_parity_sizing():
    equity = 100000.0
    price = 100.0
    atr = 2.0  # 2% volatility

    # Volatility target: 2% of equity = $2,000. vol_ratio = 2/100 = 0.02. target_value = 0.02 * 100k / 0.02 = 100k -> capped at 25k -> 250 shares
    shares = target_volatility_size(equity, price, atr, target_volatility_pct=0.02, max_position_pct=0.25)
    assert shares == 250.0

    # Risk parity
    rp_shares = risk_parity_size(equity, price, atr, risk_budget=0.01, max_position_pct=0.25)
    assert rp_shares is not None
    assert rp_shares > 0

    # Invalid inputs
    assert target_volatility_size(-100, price, atr) is None
    assert target_volatility_size(equity, 0, atr) is None
    assert target_volatility_size(equity, price, 0) is None
    assert risk_parity_size(0, price, atr) is None


def test_kelly_sizing():
    win_rate = 0.60
    avg_win = 150.0
    avg_loss = 100.0

    fraction = kelly_fraction(win_rate, avg_win, avg_loss)
    assert fraction > 0

    shares = kelly_position_size(equity=50000.0, win_rate=win_rate, avg_win=avg_win, avg_loss=avg_loss, price=100.0)
    assert shares is not None
    assert shares > 0

    h_shares = half_kelly(50000.0, win_rate, avg_win, avg_loss, 100.0)
    assert h_shares == pytest.approx(shares * 0.5, rel=1e-3)

    # Edge cases
    assert kelly_fraction(0.0, avg_win, avg_loss) == 0.0
    assert kelly_fraction(1.0, avg_win, avg_loss) == 0.0
    assert kelly_fraction(win_rate, avg_win, -10.0) == 0.0
    assert kelly_position_size(50000.0, 0.2, 50.0, 100.0, 100.0) is None


# ---------------------------------------------------------------------------
# Ensemble Optimization Tests
# ---------------------------------------------------------------------------

def test_strategy_ensemble(tmp_path):
    weights_file = tmp_path / "test_weights.json"
    ensemble = StrategyEnsemble(weights_path=str(weights_file))

    backtests = [
        {"strategy_name": "momentum", "sharpe_ratio": 2.1, "total_trades": 10, "max_drawdown_pct": 5.0},
        {"strategy_name": "trend_following", "sharpe_ratio": 1.8, "total_trades": 12, "max_drawdown_pct": 8.0},
        {"strategy_name": "mean_reversion", "sharpe_ratio": 0.5, "total_trades": 8, "max_drawdown_pct": 25.0},
    ]

    weights = ensemble.compute_weights(backtests, metric="sharpe")
    assert "momentum" in weights
    assert "trend_following" in weights
    assert weights["momentum"] > weights["mean_reversion"]
    assert pytest.approx(sum(weights.values()), 1e-4) == 1.0

    votes = [
        {"name": "momentum", "decision": "buy", "confidence": 0.8},
        {"name": "trend_following", "decision": "buy", "confidence": 0.7},
        {"name": "mean_reversion", "decision": "sell", "confidence": 0.4},
    ]

    agg = ensemble.aggregate(votes)
    assert agg["weighted_score"] > 0
    assert len(agg["breakdown"]) == 3


# ---------------------------------------------------------------------------
# Vector Store Tests
# ---------------------------------------------------------------------------

def test_vector_store():
    store = VectorStore()
    store.add("AAPL tech earnings breakout strong revenue growth", symbol="AAPL", category="earnings")
    store.add("TSLA electric vehicle deliveries decline margin squeeze", symbol="TSLA", category="delivery")
    store.add("NVDA semiconductor AI chip demand accelerates", symbol="NVDA", category="ai")

    assert store.count() == 3

    # Search for chip / AI
    results = store.search("AI semiconductor chips", top_k=1)
    assert len(results) == 1
    assert results[0]["symbol"] == "NVDA"

    # Search for EV
    ev_results = store.search("vehicle deliveries", top_k=1)
    assert len(ev_results) == 1
    assert ev_results[0]["symbol"] == "TSLA"

    # Empty query
    assert store.search("") == []

    # Keyword search
    kw_res = store.keyword_search("breakout")
    assert len(kw_res) == 1
    assert kw_res[0]["symbol"] == "AAPL"

    store.clear()
    assert store.count() == 0


# ---------------------------------------------------------------------------
# Trade History Tests
# ---------------------------------------------------------------------------

def test_trade_history(tmp_path):
    history_file = tmp_path / "trade_history.json"
    th = TradeHistory(filepath=str(history_file))

    th.record_order(
        symbol="AAPL",
        side="buy",
        qty=10.0,
        notional=1500.0,
        order_id="ORD-1",
        status="filled",
        reason="Momentum buy",
        confidence=0.85,
    )
    th.record_analysis(
        symbol="AAPL",
        action="buy",
        confidence=0.85,
        reason="Momentum setup",
    )

    all_records = th.get_all()
    assert len(all_records) == 2

    by_sym = th.get_by_symbol("AAPL")
    assert len(by_sym) == 2

    stats = th.get_stats()
    assert stats["total_orders"] == 1
    assert stats["total_analyses"] == 1
    assert stats["buy_orders"] == 1

    th.clear()
    assert len(th.get_all()) == 0


# ---------------------------------------------------------------------------
# Backtesting Report Tests
# ---------------------------------------------------------------------------

def test_backtesting_report():
    backtest_data = {
        "symbol": "AAPL",
        "start_date": "2026-01-01",
        "end_date": "2026-06-01",
        "initial_cash": 10000.0,
        "final_cash": 11500.0,
        "total_trades": 4,
        "winning_trades": 3,
        "losing_trades": 1,
        "trades": [
            {"pnl": 500.0},
            {"pnl": 600.0},
            {"pnl": 700.0},
            {"pnl": -300.0},
        ],
        "equity_curve": [
            {"date": "2026-01-01", "equity": 10000.0},
            {"date": "2026-02-01", "equity": 10500.0},
            {"date": "2026-03-01", "equity": 11100.0},
            {"date": "2026-04-01", "equity": 11800.0},
            {"date": "2026-05-01", "equity": 11500.0},
        ],
    }

    report = generate_report(backtest_data)
    assert report["total_return_pct"] == 15.0
    assert report["avg_trade_pnl"] == 375.0
    assert report["best_trade_pnl"] == 700.0
    assert report["worst_trade_pnl"] == -300.0
    assert report["profit_factor"] == pytest.approx(1800.0 / 300.0)
    assert report["sharpe_ratio"] != 0.0

    text = format_report_text(report)
    assert "Backtest Report: AAPL" in text
    assert "+15.00%" in text


# ---------------------------------------------------------------------------
# Daily Reporting Tests
# ---------------------------------------------------------------------------

def test_daily_report():
    trades = [
        {"pnl": 150.0, "symbol": "AAPL"},
        {"pnl": -50.0, "symbol": "TSLA"},
        {"pnl": 200.0, "symbol": "NVDA"},
    ]
    report = build_daily_report(trades)
    assert report["summary"]["trade_count"] == 3
    assert report["summary"]["winning_trades"] == 2
    assert report["summary"]["losing_trades"] == 1
    assert report["summary"]["total_pnl"] == 300.0


# ---------------------------------------------------------------------------
# Observability Tests
# ---------------------------------------------------------------------------

def test_observability_event_logger_and_metrics():
    events = [
        {"event": "api_call", "status": "success", "provider": "alpaca"},
        {"event": "api_call", "status": "success", "provider": "finnhub"},
        {"event": "trade_execution", "status": "success"},
        {"event": "api_call", "status": "error", "provider": "finnhub"},
    ]

    summary = MetricsCollector.summarize_run("RUN-1", events)
    assert summary["run_id"] == "RUN-1"
    assert summary["event_count"] == 4
    assert summary["success_count"] == 3
    assert summary["error_count"] == 1
    assert summary["event_types"]["api_call"] == 3

    # EventRecord
    rec = EventRecord.from_payload({
        "run_id": "RUN-TEST",
        "agent": "MarketAgent",
        "event": "snapshot",
        "symbol": "AAPL",
        "custom_metric": 42,
    })
    as_dict = rec.to_dict()
    assert as_dict["run_id"] == "RUN-TEST"
    assert as_dict["custom_metric"] == 42
