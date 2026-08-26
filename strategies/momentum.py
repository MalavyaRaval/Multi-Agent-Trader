"""
strategies/momentum.py

Evaluates momentum signals: price change, volume surge, RSI/MACD alignment.
"""

from __future__ import annotations

from typing import Any, Dict

from strategies.common import finalize_vote


class MomentumStrategy:
    name = "momentum"

    def evaluate(self, context: Dict[str, Any]) -> dict:
        """
        Returns {"decision": "buy"|"sell"|"hold", "confidence": 0..1, "reason": str}
        """
        tech = context.get("technical", {})
        signals = tech.get("signals", {})
        fund = context.get("fundamental", {})
        news = context.get("news", {})

        score = 0.0
        reasons = []

        # Price momentum
        change = signals.get("change_percent")
        if change is not None:
            if change > 3:
                score += 1.5
                reasons.append(f"Strong upward momentum (+{change:.1f}%)")
            elif change > 1:
                score += 0.5
                reasons.append(f"Positive momentum (+{change:.1f}%)")
            elif change < -3:
                score -= 1.5
                reasons.append(f"Strong downward momentum ({change:.1f}%)")
            elif change < -1:
                score -= 0.5
                reasons.append(f"Negative momentum ({change:.1f}%)")

        # Volume confirmation
        vol_ratio = signals.get("volume_ratio")
        if vol_ratio is not None and vol_ratio > 1.5:
            if score > 0:
                score += 0.5
                reasons.append("Volume confirms momentum")
            elif score < 0:
                score -= 0.5
                reasons.append("Volume confirms downward momentum")

        # RSI alignment
        rsi = signals.get("rsi_14")
        if rsi is not None:
            if 50 < rsi < 70 and score > 0:
                score += 0.5
                reasons.append("RSI confirms momentum (not overbought)")
            elif rsi > 70 and score > 0:
                score -= 0.5
                reasons.append("RSI overbought — momentum may fade")
            elif 30 < rsi < 50 and score < 0:
                score -= 0.5
                reasons.append("RSI confirms downtrend")

        # MACD
        macd = signals.get("macd")
        macd_signal = signals.get("macd_signal")
        if macd is not None and macd_signal is not None:
            if macd > macd_signal and score > 0:
                score += 0.5
                reasons.append("MACD bullish")
            elif macd < macd_signal and score < 0:
                score -= 0.5
                reasons.append("MACD bearish")

        # News boost
        if news.get("sentiment") == "positive" and score > 0:
            score += 0.3
            reasons.append("Positive news supports momentum")

        return finalize_vote(
            self.name, score, reasons, signals,
            threshold=1.5, scale=3.0, empty_reason="No clear momentum",
            zero_confidence_at_zero_score=True,
        )
