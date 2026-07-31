"""
memory/reflections.py

LLM-powered trade reflection engine. Uses Gemini to analyze
past trades and generate insights.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from google import genai

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-3.1-flash-lite"


class ReflectionEngine:
    def __init__(self) -> None:
        self.notes: list[str] = []
        self._client = None
        if GEMINI_API_KEY:
            try:
                self._client = genai.Client(api_key=GEMINI_API_KEY)
            except Exception:
                pass

    def add(self, note: str) -> None:
        self.notes.append(note)

    def summarize(self) -> str:
        return "\n".join(self.notes) if self.notes else "No reflections yet."

    def reflect_on_trade(self, trade: dict) -> dict:
        """Use Gemini to generate a reflection on a single trade."""
        if self._client is None:
            return {"reflection": "Gemini API not configured.", "lessons": []}

        symbol = trade.get("symbol", "?")
        side = trade.get("side", "?")
        pnl = trade.get("pnl", 0)
        reason = trade.get("reason", "")

        prompt = f"""You are a trading coach. Analyze this paper trade and give brief, actionable feedback.

Trade: {side.upper()} {symbol}
P&L: ${pnl}
Reason given: {reason}

Provide:
1. One sentence on what went well or wrong
2. One specific lesson for future trades
Keep it under 80 words total."""

        try:
            response = self._client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
            )
            text = response.text or "No reflection generated."
            return {
                "reflection": text,
                "trade_id": trade.get("order_id", "unknown"),
                "symbol": symbol,
            }
        except Exception as e:
            return {"reflection": f"Reflection failed: {e}", "lessons": []}

    def reflect_on_period(self, trades: list[dict]) -> dict:
        """Generate a summary reflection across multiple trades."""
        if self._client is None or not trades:
            return {"reflection": "No data or API unavailable.", "patterns": []}

        wins = [t for t in trades if t.get("pnl", 0) > 0]
        losses = [t for t in trades if t.get("pnl", 0) <= 0]
        total_pnl = sum(t.get("pnl", 0) for t in trades)

        prompt = f"""You are a trading coach reviewing a batch of {len(trades)} paper trades.

Stats:
- Winning trades: {len(wins)}
- Losing trades: {len(losses)}
- Total P&L: ${total_pnl:.2f}

Give 2-3 bullet points of actionable advice based on these stats.
Keep under 100 words."""

        try:
            response = self._client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
            )
            return {
                "reflection": response.text or "No reflection generated.",
                "trade_count": len(trades),
                "win_count": len(wins),
                "loss_count": len(losses),
            }
        except Exception as e:
            return {"reflection": f"Reflection failed: {e}", "patterns": []}
