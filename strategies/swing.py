"""
strategies/swing.py

Combines multiple signals for swing-trade entries/exits (2-10 day holds).
"""

from __future__ import annotations

from typing import Any, Dict


class SwingStrategy:
    name = "swing"

    def evaluate(self, context: Dict[str, Any]) -> dict:
        tech = context.get("technical", {})
        signals = tech.get("signals", {})
        fund = context.get("fundamental", {})
        news = context.get("news", {})
        risk = context.get("risk", {})
        portfolio = context.get("portfolio", {})

        score = 0.0
        reasons = []

        # Core technical setup
        rsi = signals.get("rsi_14")
        macd = signals.get("macd")
        macd_signal = signals.get("macd_signal")
        ema_20 = signals.get("ema_20")
        ema_50 = signals.get("ema_50")

        # RSI swing levels
        if rsi is not None:
            if 30 <= rsi <= 45:
                score += 1.0
                reasons.append(f"RSI in swing-buy zone ({rsi:.1f})")
            elif 55 <= rsi <= 70:
                score -= 1.0
                reasons.append(f"RSI in swing-sell zone ({rsi:.1f})")

        # MACD cross
        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                score += 0.5
                reasons.append("MACD above signal")
            else:
                score -= 0.5
                reasons.append("MACD below signal")

        # EMA alignment
        if ema_20 is not None and ema_50 is not None:
            if ema_20 > ema_50:
                score += 0.3
            else:
                score -= 0.3

        # Volume
        vol_ratio = signals.get("volume_ratio")
        if vol_ratio is not None and vol_ratio > 1.3:
            reasons.append(f"Volume elevated ({vol_ratio:.1f}x)")
            if score > 0:
                score += 0.3
            elif score < 0:
                score -= 0.3

        # Fundamentals
        fund_score = fund.get("score", 0)
        if fund_score != 0:
            score += fund_score * 0.3
            reasons.append(f"Fundamentals: {'+' if fund_score > 0 else ''}{fund_score}")

        # News
        sentiment = news.get("sentiment", "neutral")
        if sentiment == "positive":
            score += 0.3
            reasons.append("Positive news")
        elif sentiment == "negative":
            score -= 0.3
            reasons.append("Negative news")

        # Risk check — avoid swing trades in high-risk regime
        if risk.get("risk_level") == "high":
            score *= 0.6
            reasons.append("High risk — reducing swing size")

        # Portfolio context — don't double down excessively
        pos = portfolio.get("position")
        if pos and float(pos.get("qty", 0)) > 0 and score > 0:
            score *= 0.7  # Already long, less eager to add
            reasons.append("Already long — reducing add-on")

        decision, confidence = self._score_to_decision(score)
        data_status = "ok" if signals else "partial"
        return {
            "strategy": self.name,
            "decision": decision,
            "confidence": round(confidence, 2),
            "raw_score": round(score, 2),
            "reason": "; ".join(reasons) if reasons else "No swing setup",
            "data_status": data_status,
        }

    @staticmethod
    def _score_to_decision(score: float):
        if score >= 1.2:
            return "buy", min(score / 2.5, 1.0)
        if score <= -1.2:
            return "sell", min(abs(score) / 2.5, 1.0)
        return "hold", max(0.0, 1.0 - abs(score) / 1.2)
