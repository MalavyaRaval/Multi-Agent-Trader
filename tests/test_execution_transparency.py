"""
Tests for PHASES_PLAN.md Phase 6 (Explain Every HOLD) and Phase 7
(Score Calculation Transparency): ExecutionAgent.analyze() must expose the
full score breakdown and a structured decision explanation alongside the
final action, for every action (including HOLD).
"""

from __future__ import annotations

from agents.execution_agent import BUY_THRESHOLD, SELL_THRESHOLD, ExecutionAgent


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


def test_score_breakdown_present_for_every_decision():
    agent = ExecutionAgent()
    result = agent.analyze("AAPL", context=_context())

    breakdown = result["score_breakdown"]
    for key in (
        "technical_score", "fundamental_score", "news_score", "risk_factor",
        "agent_score_pre_risk", "agent_score", "agent_contribution",
        "strategy_score", "strategy_contribution", "combined_score",
        "buy_threshold", "sell_threshold",
    ):
        assert key in breakdown

    assert breakdown["buy_threshold"] == BUY_THRESHOLD
    assert breakdown["sell_threshold"] == SELL_THRESHOLD


def test_score_breakdown_components_sum_to_agent_score():
    agent = ExecutionAgent()
    result = agent.analyze("AAPL", context=_context(rsi=20.0, fund_score=1, sentiment="positive", risk_level="low"))

    b = result["score_breakdown"]
    pre_risk = b["technical_score"] + b["fundamental_score"] + b["news_score"]
    assert abs(pre_risk - b["agent_score_pre_risk"]) < 1e-9
    assert abs(pre_risk * b["risk_factor"] - b["agent_score"]) < 1e-9
    assert abs(b["agent_score"] - result["agent_score"]) < 1e-9


def test_hold_decision_includes_explanation():
    agent = ExecutionAgent()
    # Neutral inputs on all fronts should land in HOLD (score near zero).
    result = agent.analyze("AAPL", context=_context())

    assert result["action"] == "hold"
    explanation = result["decision_explanation"]
    assert explanation["action"] == "hold"
    assert "buy_threshold" in explanation and "sell_threshold" in explanation
    assert isinstance(explanation["agent_reasons"], list)
    assert isinstance(explanation["strategy_reasons"], list)
    assert len(explanation["strategy_reasons"]) == 5  # one per strategy
    for strat_reason in explanation["strategy_reasons"]:
        assert "strategy" in strat_reason and "decision" in strat_reason and "reason" in strat_reason


def test_buy_decision_includes_explanation_with_reasons():
    agent = ExecutionAgent()
    result = agent.analyze("AAPL", context=_context(rsi=20.0, macd=0.5, macd_signal=0.1, fund_score=1, sentiment="positive", risk_level="low"))

    assert result["action"] == "buy"
    explanation = result["decision_explanation"]
    assert explanation["action"] == "buy"
    assert explanation["combined_score"] > BUY_THRESHOLD
    assert len(explanation["agent_reasons"]) > 0
