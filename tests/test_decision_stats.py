"""
Tests for PHASES_PLAN.md Phase 8 -- Find Out Why HOLD Happens.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from agents.execution_agent import ExecutionAgent, HOLD_REASON_LABELS
from memory.trade_history import TradeHistory


def _context(rsi=50.0, macd=0.1, macd_signal=0.1, fund_score=0, sentiment="neutral", risk_level="medium", qty=0):
    return {
        "market": {"metrics": {"relative_volume": 1.0, "change_percent": 0.0, "spread": 0.1}},
        "technical": {
            "status": "ok",
            "signals": {
                "rsi_14": rsi,
                "macd": macd,
                "macd_signal": macd_signal,
                "ema_20": 100.0,
                "ema_50": 100.0,
                "atr_14": 1.0,
                "last_price": 100.0,
                "volume_trend": "neutral",
            },
        },
        "fundamental": {"score": fund_score},
        "news": {"sentiment": sentiment},
        "risk": {"status": "ok", "risk_level": risk_level},
        "portfolio": {"position": {"qty": qty}},
    }


# ---------------------------------------------------------------------------
# _classify_hold_reason unit tests (pure function, no I/O)
# ---------------------------------------------------------------------------

def test_classify_returns_none_for_buy_sell():
    assert ExecutionAgent._classify_hold_reason("buy", "NORMAL", "ok", "low", {}, [], []) is None
    assert ExecutionAgent._classify_hold_reason("sell", "NORMAL", "ok", "low", {}, [], []) is None


def test_classify_insufficient_data():
    result = ExecutionAgent._classify_hold_reason("hold", "DATA_UNAVAILABLE", "insufficient_data", "medium", {}, [], [])
    assert result == "insufficient_data"


def test_classify_risk_error_takes_priority_over_data_unavailable():
    result = ExecutionAgent._classify_hold_reason("hold", "DATA_UNAVAILABLE", "risk_error", "medium", {}, [], [])
    assert result == "risk_gate"


def test_classify_high_risk_level():
    result = ExecutionAgent._classify_hold_reason("hold", "INSUFFICIENT_EDGE", "ok", "high", {}, [], ["some reason"])
    assert result == "risk_gate"


def test_classify_existing_position():
    portfolio = {"position": {"qty": 10}}
    result = ExecutionAgent._classify_hold_reason("hold", "INSUFFICIENT_EDGE", "ok", "low", portfolio, [], ["some reason"])
    assert result == "existing_position"


def test_classify_mixed_strategy_signals():
    votes = [{"decision": "buy"}, {"decision": "sell"}, {"decision": "hold"}]
    result = ExecutionAgent._classify_hold_reason("hold", "INSUFFICIENT_EDGE", "ok", "low", {}, votes, ["some reason"])
    assert result == "mixed_strategy_signals"


def test_classify_no_technical_catalyst():
    votes = [{"decision": "hold"}] * 5
    result = ExecutionAgent._classify_hold_reason("hold", "INSUFFICIENT_EDGE", "ok", "low", {}, votes, [])
    assert result == "no_technical_catalyst"


def test_classify_below_confidence_threshold_default():
    votes = [{"decision": "hold"}] * 5
    result = ExecutionAgent._classify_hold_reason("hold", "INSUFFICIENT_EDGE", "ok", "low", {}, votes, ["weak signal"])
    assert result == "below_confidence_threshold"


def test_all_hold_reason_codes_have_labels():
    for code in ("insufficient_data", "risk_gate", "existing_position", "mixed_strategy_signals", "no_technical_catalyst", "below_confidence_threshold"):
        assert code in HOLD_REASON_LABELS


# ---------------------------------------------------------------------------
# End-to-end: ExecutionAgent.analyze() sets hold_reason correctly
# ---------------------------------------------------------------------------

def test_analyze_sets_hold_reason_for_neutral_context():
    agent = ExecutionAgent()
    result = agent.analyze("AAPL", context=_context())
    assert result["action"] == "hold"
    assert result["hold_reason"] in HOLD_REASON_LABELS


def test_analyze_sets_hold_reason_none_for_buy():
    agent = ExecutionAgent()
    result = agent.analyze("AAPL", context=_context(rsi=20.0, macd=0.5, macd_signal=0.1, fund_score=1, sentiment="positive", risk_level="low"))
    if result["action"] == "buy":
        assert result["hold_reason"] is None


def test_analyze_no_context_sets_insufficient_data():
    agent = ExecutionAgent()
    result = agent.analyze("AAPL", context=None)
    assert result["action"] == "hold"
    assert result["hold_reason"] == "insufficient_data"


# ---------------------------------------------------------------------------
# TradeHistory.get_decision_stats aggregation (isolated temp file)
# ---------------------------------------------------------------------------

def test_get_decision_stats_aggregates_correctly():
    with tempfile.TemporaryDirectory() as tmpdir:
        history = TradeHistory(filepath=str(Path(tmpdir) / "history.json"))
        history.record_analysis("AAPL", "buy", 0.8, "strong buy", decision_status="NORMAL", hold_reason=None)
        history.record_analysis("AAPL", "hold", 0.1, "no edge", decision_status="INSUFFICIENT_EDGE", hold_reason="below_confidence_threshold")
        history.record_analysis("AAPL", "hold", 0.0, "no data", decision_status="DATA_UNAVAILABLE", hold_reason="insufficient_data")
        history.record_analysis("AAPL", "hold", 0.1, "risky", decision_status="INSUFFICIENT_EDGE", hold_reason="risk_gate")
        history.record_analysis("AAPL", "sell", 0.7, "strong sell", decision_status="NORMAL", hold_reason=None)

        stats = history.get_decision_stats(limit=100)

        assert stats["sample_size"] == 5
        assert stats["action_counts"] == {"buy": 1, "sell": 1, "hold": 3}
        assert stats["action_percentages"]["hold"] == 60.0
        assert stats["hold_reason_counts"] == {
            "below_confidence_threshold": 1,
            "insufficient_data": 1,
            "risk_gate": 1,
        }


def test_get_decision_stats_respects_limit():
    with tempfile.TemporaryDirectory() as tmpdir:
        history = TradeHistory(filepath=str(Path(tmpdir) / "history.json"))
        for _ in range(5):
            history.record_analysis("AAPL", "hold", 0.1, "no edge", hold_reason="below_confidence_threshold")
        for _ in range(3):
            history.record_analysis("AAPL", "buy", 0.8, "buy", hold_reason=None)

        stats = history.get_decision_stats(limit=3)
        assert stats["sample_size"] == 3
        assert stats["action_counts"]["buy"] == 3


def test_get_decision_stats_empty_history():
    with tempfile.TemporaryDirectory() as tmpdir:
        history = TradeHistory(filepath=str(Path(tmpdir) / "history.json"))
        stats = history.get_decision_stats(limit=100)
        assert stats["sample_size"] == 0
        assert stats["action_percentages"] == {"buy": 0.0, "sell": 0.0, "hold": 0.0}
