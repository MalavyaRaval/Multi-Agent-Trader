"""
memory/reasoning.py

Detailed AI Reasoning Synthesis Engine.
Generates comprehensive, multi-layer natural language trade theses and
step-by-step reasoning explanations for every multi-agent decision.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from llm.gemini_client import get_gemini_client, safe_generate


class ReasoningEngine:
    """Synthesizes structured trade reasoning combining rule-based math and Gemini LLM insights."""

    def __init__(self) -> None:
        self._client = get_gemini_client()

    def synthesize_reasoning(
        self,
        symbol: str,
        action: str,
        confidence: float,
        raw_score: float,
        agent_score: float,
        strat_score: float,
        strategy_votes: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build a comprehensive reasoning payload explaining why the decision was made.
        """
        symbol = symbol.upper()
        action = action.upper()
        
        # 1. Build deterministic structural components first
        tech = context.get("technical", {}).get("signals", {}) or {}
        fund = context.get("fundamental", {}).get("data", {}).get("company", {}) or {}
        news = context.get("news", {}) or {}
        risk = context.get("risk", {}) or {}
        port = context.get("portfolio", {}) or {}

        bullish_args = []
        bearish_args = []
        step_by_step = []

        # Technical signals
        rsi = tech.get("rsi_14")
        macd = tech.get("macd")
        macd_sig = tech.get("macd_signal")
        ema20 = tech.get("ema_20")
        ema50 = tech.get("ema_50")
        vol_trend = tech.get("volume_trend", "neutral")

        if rsi is not None:
            if rsi < 30:
                bullish_args.append(f"RSI is oversold at {rsi:.1f}, indicating strong momentum bounce potential.")
            elif rsi > 70:
                bearish_args.append(f"RSI is overbought at {rsi:.1f}, warning of potential buying exhaustion.")
            else:
                step_by_step.append(f"RSI is neutral at {rsi:.1f}.")

        if macd is not None and macd_sig is not None:
            if macd > macd_sig:
                bullish_args.append(f"MACD line ({macd:.2f}) is above Signal ({macd_sig:.2f}), confirming bullish momentum.")
            else:
                bearish_args.append(f"MACD line ({macd:.2f}) is below Signal ({macd_sig:.2f}), indicating bearish pressure.")

        if ema20 is not None and ema50 is not None:
            if ema20 > ema50:
                bullish_args.append(f"EMA(20) [{ema20:.2f}] is above EMA(50) [{ema50:.2f}], confirming an active uptrend.")
            else:
                bearish_args.append(f"EMA(20) [{ema20:.2f}] is below EMA(50) [{ema50:.2f}], confirming a downtrend.")

        if "strong_buy" in str(vol_trend).lower():
            bullish_args.append("Volume surge confirms strong buyer participation.")
        elif "strong_sell" in str(vol_trend).lower():
            bearish_args.append("Volume surge confirms heavy selling pressure.")

        # Fundamental & News
        pe = fund.get("pe_ratio")
        if pe:
            if pe < 18:
                bullish_args.append(f"Company P/E ratio is attractive at {pe:.1f}x.")
            elif pe > 40:
                bearish_args.append(f"Valuation is rich with P/E ratio at {pe:.1f}x.")

        sentiment = news.get("sentiment", "neutral")
        if sentiment == "positive":
            bullish_args.append("News sentiment scanner returned positive headline sentiment.")
        elif sentiment == "negative":
            bearish_args.append("News sentiment scanner identified negative risk factors.")

        # Risk assessment
        risk_level = risk.get("risk_level", "medium")
        atr_pct = risk.get("checks", {}).get("atr_percent")
        risk_text = f"Risk level assessed as {risk_level.upper()}."
        if atr_pct:
            risk_text += f" ATR volatility is {atr_pct:.2f}% of current price."

        # Strategy consensus
        buy_votes = [v for v in strategy_votes if str(v.get("decision", "")).lower() == "buy"]
        sell_votes = [v for v in strategy_votes if str(v.get("decision", "")).lower() == "sell"]
        hold_votes = [v for v in strategy_votes if str(v.get("decision", "")).lower() == "hold"]

        strat_summary = f"{len(buy_votes)} BUY, {len(sell_votes)} SELL, {len(hold_votes)} HOLD across 5 strategies."

        # Heuristic executive summary fallback
        exec_summary = (
            f"The multi-agent system issued a {action} recommendation for {symbol} with {confidence*100:.0f}% confidence. "
            f"Combined score is {raw_score:+.2f} (Agent signals: {agent_score:+.2f}, Strategy consensus: {strat_score:+.2f}). "
            f"Risk profile is {risk_level}. Strategy consensus: {strat_summary}"
        )

        # Build step-by-step breakdown
        steps = [
            f"1. Market Agent gathered price data for {symbol} (Last Price: ${tech.get('last_price', 'N/A')}).",
            f"2. Technical & Multi-timeframe Agents computed indicators: RSI={rsi if rsi else 'N/A'}, MACD={macd if macd else 'N/A'}.",
            f"3. Fundamental & News Agents scanned financial profile and headline sentiment ({sentiment}).",
            f"4. Risk Agent computed volatility factor (ATR%={atr_pct if atr_pct else 'N/A'}, Risk={risk_level}).",
            f"5. Strategy Ensemble ran 5 independent hypothesis voters: {strat_summary}",
            f"6. Execution Agent weighted agent metrics (60%) and strategy ensemble (40%) to derive final decision: {action}.",
        ]

        reasoning_dict = {
            "executive_summary": exec_summary,
            "bullish_arguments": bullish_args if bullish_args else ["No major bullish catalysts detected."],
            "bearish_arguments": bearish_args if bearish_args else ["No major bearish threats detected."],
            "risk_assessment": risk_text,
            "strategy_summary": strat_summary,
            "score_breakdown": {
                "agent_score": round(agent_score, 2),
                "strategy_score": round(strat_score, 2),
                "combined_score": round(raw_score, 2),
                "action": action,
                "confidence": round(confidence, 2),
            },
            "step_by_step_reasoning": steps,
        }

        # Try to refine executive summary with Gemini if API key available
        llm_prompt = f"""You are the Chief Investment Officer AI of a multi-agent trading system.
Synthesize a concise, 2-3 sentence executive rationale for a user based on the following analysis data:

Symbol: {symbol}
Decision: {action} (Confidence: {confidence*100:.0f}%, Combined Score: {raw_score})
Agent Score: {agent_score}, Strategy Ensemble Score: {strat_score}
Bullish Factors: {', '.join(bullish_args) if bullish_args else 'None'}
Bearish Factors: {', '.join(bearish_args) if bearish_args else 'None'}
Risk Level: {risk_level}
Strategies Voting: {strat_summary}

Explain clearly WHY this decision was reached in professional, accessible terms."""

        llm_summary = safe_generate(self._client, llm_prompt)
        if llm_summary:
            reasoning_dict["executive_summary"] = llm_summary

        return reasoning_dict
