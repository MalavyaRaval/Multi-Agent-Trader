"""
strategies/breakout.py

Detects breakouts from consolidation using ATR and volume.
"""

from __future__ import annotations

from typing import Any, Dict


class BreakoutStrategy:
    name = "breakout"

    def evaluate(self, context: Dict[str, Any]) -> dict:
        tech = context.get("technical", {})
        signals = tech.get("signals", {})
        market = context.get("market", {})
        metrics = market.get("metrics", {}) if isinstance(market, dict) else {}

        score = 0.0
        reasons = []

        # ATR expansion signals breakout potential
        atr = signals.get("atr_14")
        change_pct = signals.get("change_percent") or metrics.get("change_percent")
        vol_ratio = signals.get("volume_ratio")

        if change_pct is not None:
            if change_pct > 4:
                score += 1.5
                reasons.append(f"Large daily move ({change_pct:+.1f}%) — breakout potential")
            elif change_pct > 2:
                score += 0.5
                reasons.append(f"Notable daily move ({change_pct:+.1f}%)")
            elif change_pct < -4:
                score -= 1.5
                reasons.append(f"Large breakdown ({change_pct:+.1f}%)")
            elif change_pct < -2:
                score -= 0.5
                reasons.append(f"Notable decline ({change_pct:+.1f}%)")

        # Volume spike is critical for breakout validity
        if vol_ratio is not None:
            if vol_ratio > 2.0:
                if score > 0:
                    score += 1.0
                    reasons.append(f"Massive volume surge ({vol_ratio:.1f}x) confirms breakout")
                elif score < 0:
                    score -= 1.0
                    reasons.append(f"Massive volume on decline confirms breakdown")
            elif vol_ratio > 1.5:
                if score > 0:
                    score += 0.5
                    reasons.append(f"Above-average volume ({vol_ratio:.1f}x)")
                elif score < 0:
                    score -= 0.5

        # Bollinger squeeze then expansion
        bb_upper = signals.get("bollinger_upper")
        bb_lower = signals.get("bollinger_lower")
        if bb_upper is not None and bb_lower is not None:
            band_width = bb_upper - bb_lower
            if band_width > 0 and atr is not None:
                # If band width is tight relative to ATR, squeeze may be ending
                if atr > band_width * 0.3 and change_pct and abs(change_pct) > 2:
                    score += 0.5
                    reasons.append("Bollinger squeeze expansion")

        # RSI should support direction but not be extreme
        rsi = signals.get("rsi_14")
        if rsi is not None:
            if 40 < rsi < 65 and score > 0:
                score += 0.3
                reasons.append("RSI healthy for breakout continuation")
            elif 35 < rsi < 60 and score < 0:
                score -= 0.3
                reasons.append("RSI supports breakdown continuation")

        decision, confidence = self._score_to_decision(score)
        data_status = "ok" if signals else "partial"
        return {
            "strategy": self.name,
            "decision": decision,
            "confidence": round(confidence, 2),
            "raw_score": round(score, 2),
            "reason": "; ".join(reasons) if reasons else "No breakout signal",
            "data_status": data_status,
        }

    @staticmethod
    def _score_to_decision(score: float):
        if score >= 2.0:
            return "buy", min(score / 4.0, 1.0)
        if score <= -2.0:
            return "sell", min(abs(score) / 4.0, 1.0)
        return "hold", max(0.0, 1.0 - abs(score) / 2.0)
