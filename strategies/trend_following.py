"""
strategies/trend_following.py

Follows trends using EMA crossovers and price structure.
"""

from __future__ import annotations

from typing import Any, Dict


class TrendFollowingStrategy:
    name = "trend_following"

    def evaluate(self, context: Dict[str, Any]) -> dict:
        tech = context.get("technical", {})
        signals = tech.get("signals", {})
        risk = context.get("risk", {})

        score = 0.0
        reasons = []

        ema_20 = signals.get("ema_20")
        ema_50 = signals.get("ema_50")
        close = signals.get("close")  # may not exist; use ema_20 as proxy

        # EMA golden cross / death cross
        if ema_20 is not None and ema_50 is not None:
            if ema_20 > ema_50:
                score += 1.0
                reasons.append("EMA20 above EMA50 (uptrend)")
                # Distance matters
                dist = (ema_20 - ema_50) / ema_50 * 100
                if dist > 2:
                    score += 0.5
                    reasons.append("Strong trend distance")
            else:
                score -= 1.0
                reasons.append("EMA20 below EMA50 (downtrend)")
                dist = (ema_50 - ema_20) / ema_50 * 100
                if dist > 2:
                    score -= 0.5
                    reasons.append("Strong downtrend distance")

        # Price vs EMA20
        if signals.get("bollinger_upper") is not None and signals.get("bollinger_lower") is not None:
            bb_upper = signals["bollinger_upper"]
            bb_lower = signals["bollinger_lower"]
            bb_mid = (bb_upper + bb_lower) / 2
            if ema_20 is not None:
                if ema_20 > bb_mid:
                    score += 0.3
                else:
                    score -= 0.3

        # Trend strength via ATR
        atr = signals.get("atr_14")
        if atr is not None and atr > 0:
            if risk.get("risk_level") == "high":
                score *= 0.7  # reduce conviction in high volatility
                reasons.append("High volatility — reducing trend conviction")

        # Volume trend
        vol_trend = signals.get("volume_trend", "neutral")
        if "buy" in vol_trend and score > 0:
            score += 0.3
            reasons.append("Volume supports uptrend")
        elif "sell" in vol_trend and score < 0:
            score -= 0.3
            reasons.append("Volume supports downtrend")

        decision, confidence = self._score_to_decision(score)
        return {
            "strategy": self.name,
            "decision": decision,
            "confidence": round(confidence, 2),
            "reason": "; ".join(reasons) if reasons else "No clear trend",
            "raw_score": round(score, 2),
        }

    @staticmethod
    def _score_to_decision(score: float):
        if score >= 1.2:
            return "buy", min(score / 2.5, 1.0)
        if score <= -1.2:
            return "sell", min(abs(score) / 2.5, 1.0)
        return "hold", max(0.0, 1.0 - abs(score) / 1.2)
