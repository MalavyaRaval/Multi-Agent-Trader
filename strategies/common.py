"""
strategies/common.py

Shared scoring/result-shaping logic used by every Strategy.evaluate(). Each
strategy previously defined its own private `_score_to_decision` static method
(identical shape, different threshold/scale constants) and repeated the same
result-dict assembly at the end of evaluate().
"""

from __future__ import annotations

from typing import Any, Dict, List


def score_to_decision(
    score: float,
    threshold: float,
    scale: float,
    *,
    zero_confidence_at_zero_score: bool = False,
) -> tuple[str, float]:
    """Classify a raw strategy score into (decision, confidence) using a
    symmetric buy/sell threshold and a confidence scaling divisor.

    zero_confidence_at_zero_score: when True, an exact-zero score (no signal
    fired at all) reports "hold" with 0.0 confidence instead of the formula's
    usual near-max hold-confidence at score==0. Used by MomentumStrategy.
    """
    if score >= threshold:
        return "buy", min(score / scale, 1.0)
    if score <= -threshold:
        return "sell", min(abs(score) / scale, 1.0)
    if zero_confidence_at_zero_score and abs(score) < 1e-9:
        return "hold", 0.0
    return "hold", max(0.0, 1.0 - abs(score) / threshold)


def finalize_vote(
    name: str,
    score: float,
    reasons: List[str],
    signals: Dict[str, Any],
    threshold: float,
    scale: float,
    empty_reason: str,
    *,
    zero_confidence_at_zero_score: bool = False,
) -> Dict[str, Any]:
    """Build the standard {strategy, decision, confidence, raw_score, reason,
    data_status} vote dict every strategy returns from evaluate()."""
    decision, confidence = score_to_decision(
        score, threshold, scale, zero_confidence_at_zero_score=zero_confidence_at_zero_score
    )
    return {
        "strategy": name,
        "decision": decision,
        "confidence": round(confidence, 2),
        "raw_score": round(score, 2),
        "reason": "; ".join(reasons) if reasons else empty_reason,
        "data_status": "ok" if signals else "partial",
    }
