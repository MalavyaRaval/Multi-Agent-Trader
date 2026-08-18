"""
strategies/mean_reversion.py

Looks for oversold/overbought conditions to revert to mean.
"""

from __future__ import annotations

from typing import Any, Dict


class MeanReversionStrategy:
    name = "mean_reversion"

    def evaluate(self, context: Dict[str, Any]) -> dict:
        tech = context.get("technical", {})
        signals = tech.get("signals", {})

        score = 0.0
        reasons = []

        rsi = signals.get("rsi_14")
        if rsi is not None:
            if rsi < 25:
                score += 2.0
                reasons.append(f"Deeply oversold (RSI {rsi:.1f})")
            elif rsi < 35:
                score += 1.0
                reasons.append(f"Oversold (RSI {rsi:.1f})")
            elif rsi > 75:
                score -= 2.0
                reasons.append(f"Deeply overbought (RSI {rsi:.1f})")
            elif rsi > 65:
                score -= 1.0
                reasons.append(f"Overbought (RSI {rsi:.1f})")

        # Bollinger Band position
        bb_upper = signals.get("bollinger_upper")
        bb_lower = signals.get("bollinger_lower")
        ema_20 = signals.get("ema_20")
        if bb_upper is not None and bb_lower is not None and ema_20 is not None:
            band_width = bb_upper - bb_lower
            if band_width > 0:
                position = (ema_20 - bb_lower) / band_width
                if position < 0.1:
                    score += 1.0
                    reasons.append("Price at lower Bollinger band")
                elif position > 0.9:
                    score -= 1.0
                    reasons.append("Price at upper Bollinger band")

        # MACD divergence hint
        macd_hist = signals.get("macd_hist")
        if macd_hist is not None:
            if macd_hist > 0 and score > 0:
                score += 0.3
                reasons.append("MACD histogram turning positive")
            elif macd_hist < 0 and score < 0:
                score -= 0.3
                reasons.append("MACD histogram turning negative")

        # Volume confirmation for reversal
        vol_ratio = signals.get("volume_ratio")
        if vol_ratio is not None and vol_ratio > 1.5:
            if score > 0:
                score += 0.3
                reasons.append("Volume spike on dip (possible reversal)")
            elif score < 0:
                score -= 0.3
                reasons.append("Volume spike on rally (possible top)")

        decision, confidence = self._score_to_decision(score)
        data_status = "ok" if signals else "partial"
        return {
            "strategy": self.name,
            "decision": decision,
            "confidence": round(confidence, 2),
            "raw_score": round(score, 2),
            "reason": "; ".join(reasons) if reasons else "No mean-reversion signal",
            "data_status": data_status,
        }

    @staticmethod
    def _score_to_decision(score: float):
        if score >= 1.5:
            return "buy", min(score / 3.0, 1.0)
        if score <= -1.5:
            return "sell", min(abs(score) / 3.0, 1.0)
        return "hold", max(0.0, 1.0 - abs(score) / 1.5)
