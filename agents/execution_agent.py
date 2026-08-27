"""
execution_agent.py

Makes the final BUY / SELL / HOLD decision by combining:
- All agent analyses (technical, fundamental, news, risk, portfolio)
- All strategy evaluations (momentum, trend, mean-reversion, breakout, swing)
- Risk-adjusted position sizing

Can place real paper trades through Alpaca and logs everything to TradeHistory.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from alpaca.trading.client import TradingClient

from strategies.momentum import MomentumStrategy
from strategies.trend_following import TrendFollowingStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.breakout import BreakoutStrategy
from strategies.swing import SwingStrategy
from memory.trade_history import TradeHistory
from memory.reasoning import ReasoningEngine
from sizing import target_volatility_size, risk_parity_size, half_kelly
from optimization.ensemble import StrategyEnsemble
from data.alpaca_client import get_trading_client, place_market_order

logger = logging.getLogger(__name__)

# Auto-execute threshold: only trade if confidence >= this value
AUTO_EXECUTE_CONFIDENCE = float(os.getenv("AUTO_EXECUTE_CONFIDENCE", "0.75"))
# Default notional size for auto-trades (fallback when smart sizing fails)
AUTO_TRADE_NOTIONAL = float(os.getenv("AUTO_TRADE_NOTIONAL", "500"))
ALLOW_DEGRADED_TRADING = os.getenv("ALLOW_DEGRADED_TRADING", "false").strip().lower() in {"1", "true", "yes", "on"}

# Combined-score gates for BUY/SELL vs HOLD (combined_score lives in roughly [-1, 1]
# after the 60/40 agent/strategy weighting below). Named here -- rather than left as
# bare 0.25 / -0.25 literals at each decision branch -- so they can be surfaced
# verbatim in the decision explanation (PHASES_PLAN.md Phase 6/7).
BUY_THRESHOLD = 0.25
SELL_THRESHOLD = -0.25
AGENT_WEIGHT = 0.60
STRATEGY_WEIGHT = 0.40

# PHASES_PLAN.md Phase 8 -- Find Out Why HOLD Happens. Canonical HOLD-reason
# buckets (stable machine-readable codes -> display labels), aggregated by
# memory.trade_history.TradeHistory.get_decision_stats().
HOLD_REASON_LABELS = {
    "insufficient_data": "Insufficient data",
    "risk_gate": "Risk gate",
    "existing_position": "Existing position",
    "mixed_strategy_signals": "Mixed strategy signals",
    "no_technical_catalyst": "No technical catalyst",
    "below_confidence_threshold": "Below confidence threshold",
}


class ExecutionAgent:
    name = "execution_agent"

    def __init__(self) -> None:
        self._client: Optional[TradingClient] = get_trading_client()
        self.history = TradeHistory()
        self.ensemble = StrategyEnsemble()
        self.reasoning_engine = ReasoningEngine()
        self.strategies = [
            MomentumStrategy(),
            TrendFollowingStrategy(),
            MeanReversionStrategy(),
            BreakoutStrategy(),
            SwingStrategy(),
        ]

    def analyze(self, symbol: str, context: Optional[Dict[str, Any]] = None) -> dict:
        symbol = symbol.upper()
        ctx = context or {}
        result = {
            "symbol": symbol,
            "status": "execution analysis ready",
            "action": "hold",
            "confidence": 0.0,
            "decision_status": "DATA_UNAVAILABLE",
            "hold_reason": "insufficient_data",
            "reason": "",
            "strategy_votes": [],
            "ensemble": {},
            "data_available": True,
            "data_quality": {
                "market": True,
                "technical": True,
                "fundamental": True,
                "news": True,
                "risk": True,
                "portfolio": True,
            },
            "data_quality_score": 100,
        }

        if not ctx:
            result["status"] = "execution analysis skipped (no context)"
            result["decision_status"] = "DATA_UNAVAILABLE"
            result["data_available"] = False
            result["data_quality_score"] = 0
            return result

        tech = ctx.get("technical", {})
        market = ctx.get("market", {})
        required_fields = ["rsi_14", "macd", "macd_signal", "ema_20", "ema_50", "atr_14", "last_price"]
        if tech.get("status") != "ok":
            result["status"] = "insufficient_data"
            result["action"] = "hold"
            result["decision_status"] = "DATA_UNAVAILABLE"
            result["confidence"] = 0.0
            result["reason"] = "Insufficient market/technical data"
            result["data_available"] = False
            result["data_quality"]["technical"] = False
            result["data_quality_score"] = 40
            return result

        signals = tech.get("signals", {})
        missing_required = [field for field in required_fields if signals.get(field) is None]
        if market.get("metrics") is None or any(signals.get(field) is None for field in required_fields):
            result["status"] = "insufficient_data"
            result["action"] = "hold"
            result["decision_status"] = "DATA_UNAVAILABLE"
            result["confidence"] = 0.0
            result["reason"] = "Insufficient market/technical data" if not missing_required else f"Missing required fields: {missing_required}"
            result["data_available"] = False
            result["data_quality"]["market"] = market.get("metrics") is not None
            result["data_quality"]["technical"] = not bool(missing_required)
            result["data_quality_score"] = 40
            return result

        strategy_results = []
        for strat in self.strategies:
            try:
                vote = strat.evaluate(ctx)
                if isinstance(vote, dict) and "name" not in vote:
                    vote["name"] = getattr(strat, "name", strat.__class__.__name__)
                if "data_status" not in vote:
                    vote["data_status"] = "ok"
                strategy_results.append(vote)
            except Exception as exc:
                logger.exception("Strategy evaluation failed for %s (%s)", getattr(strat, "name", strat.__class__.__name__), symbol)
                strategy_results.append({
                    "strategy": getattr(strat, "name", strat.__class__.__name__),
                    "decision": "hold",
                    "confidence": 0.0,
                    "raw_score": 0.0,
                    "reason": f"Strategy evaluation error: {exc}",
                    "data_status": "data_missing",
                })
        result["strategy_votes"] = strategy_results

        ensemble_result = self.ensemble.aggregate(strategy_results)
        result["ensemble"] = ensemble_result
        strat_score = float(ensemble_result.get("weighted_score", 0.0))

        fund = ctx.get("fundamental", {})
        news = ctx.get("news", {})
        risk = ctx.get("risk", {})
        port = ctx.get("portfolio", {})

        technical_score = 0.0
        fundamental_score = 0.0
        news_score = 0.0
        reasons = []
        risk_status = str(risk.get("status", "ok")).lower()
        risk_level = str(risk.get("risk_level", "medium")).lower()
        risk_factor = 1.0

        if risk_status == "error":
            result["status"] = "risk_error"
            result["action"] = "hold"
            result["decision_status"] = "DATA_UNAVAILABLE"
            result["hold_reason"] = "risk_gate"
            result["confidence"] = 0.0
            result["reason"] = "Risk agent failed: " + str(risk.get("error", "unknown risk error"))
            result["data_quality"]["risk"] = False
            result["data_quality_score"] = 40
            return result

        if risk_level in {"unknown", "none"}:
            risk_factor = 0.2
            reasons.append("Risk unknown - reducing conviction")
            result["data_quality"]["risk"] = False
        elif risk_level == "high":
            risk_factor = 0.35
            reasons.append("High risk - reducing position size and conviction")
        elif risk_level == "medium":
            risk_factor = 0.7
        elif risk_level == "low":
            risk_factor = 0.9

        signals = tech.get("signals", {})
        rsi = signals.get("rsi_14")
        macd = signals.get("macd")
        macd_signal = signals.get("macd_signal")
        ema_20 = signals.get("ema_20")
        ema_50 = signals.get("ema_50")
        volume_trend = signals.get("volume_trend", "neutral")

        if rsi is not None:
            if rsi < 30:
                technical_score += 1.5
                reasons.append(f"RSI oversold ({rsi:.1f})")
            elif rsi > 70:
                technical_score -= 1.5
                reasons.append(f"RSI overbought ({rsi:.1f})")

        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                technical_score += 1.0
                reasons.append("MACD bullish crossover")
            else:
                technical_score -= 1.0
                reasons.append("MACD bearish crossover")

        if ema_20 is not None and ema_50 is not None:
            if ema_20 > ema_50:
                technical_score += 0.5
                reasons.append("Price above EMA50 (uptrend)")
            else:
                technical_score -= 0.5
                reasons.append("Price below EMA50 (downtrend)")

        if "strong_buy" in volume_trend:
            technical_score += 0.5
            reasons.append("Volume confirms upside")
        elif "strong_sell" in volume_trend:
            technical_score -= 0.5
            reasons.append("Volume confirms downside")

        fund_score = fund.get("score") if isinstance(fund, dict) else None
        if fund_score is None:
            reasons.append("Fundamentals unavailable")
            result["data_quality"]["fundamental"] = False
            result["data_quality_score"] = min(result["data_quality_score"], 60)
        else:
            fundamental_score += float(fund_score) * 0.5
            if fund_score > 0:
                reasons.append("Fundamentals look good")
            elif fund_score < 0:
                reasons.append("Fundamentals weak")

        sentiment = news.get("sentiment", "neutral") if isinstance(news, dict) else "neutral"
        if sentiment == "positive":
            news_score += 0.5
            reasons.append("Positive news sentiment")
        elif sentiment == "negative":
            news_score -= 0.5
            reasons.append("Negative news sentiment")

        agent_score_pre_risk = technical_score + fundamental_score + news_score
        agent_score = agent_score_pre_risk * risk_factor

        # Normalized to [-1, 1] for a mathematically clear 60/40 weighting.
        # agent_score is built from additive heuristics; strategy_score already comes from the ensemble in [-1, 1].
        agent_norm = max(-1.0, min(1.0, agent_score / 4.0))
        strat_norm = max(-1.0, min(1.0, strat_score))
        agent_contribution = agent_norm * AGENT_WEIGHT
        strategy_contribution = strat_norm * STRATEGY_WEIGHT
        combined_score = agent_contribution + strategy_contribution

        position = port.get("position") if isinstance(port, dict) else None
        if position and position.get("qty"):
            qty = float(position.get("qty", 0))
            if qty > 0 and combined_score < SELL_THRESHOLD:
                result["action"] = "sell"
                result["confidence"] = min(abs(combined_score) / 1.5, 1.0)
                result["decision_status"] = "NORMAL"
            elif qty == 0 and combined_score > BUY_THRESHOLD:
                result["action"] = "buy"
                result["confidence"] = min(abs(combined_score) / 1.5, 1.0)
                result["decision_status"] = "NORMAL"
            else:
                result["action"] = "hold"
                result["confidence"] = 0.13 if abs(combined_score) < BUY_THRESHOLD else min(abs(combined_score) / 2.0, 0.30)
                result["decision_status"] = "INSUFFICIENT_EDGE"
        else:
            if combined_score > BUY_THRESHOLD:
                result["action"] = "buy"
                result["confidence"] = min(abs(combined_score) / 1.5, 1.0)
                result["decision_status"] = "NORMAL"
            elif combined_score < SELL_THRESHOLD:
                result["action"] = "sell"
                result["confidence"] = min(abs(combined_score) / 1.5, 1.0)
                result["decision_status"] = "NORMAL"
            else:
                result["action"] = "hold"
                result["confidence"] = 0.13 if abs(combined_score) < BUY_THRESHOLD else min(abs(combined_score) / 2.0, 0.30)
                result["decision_status"] = "INSUFFICIENT_EDGE"

        result["reason"] = "; ".join(reasons) if reasons else "No strong signals"
        result["raw_score"] = round(combined_score, 2)
        result["agent_score"] = round(agent_score, 2)
        result["strategy_score"] = round(strat_score, 2)
        result["normalized_agent_score"] = round(agent_norm, 4)
        result["normalized_strategy_score"] = round(strat_norm, 4)
        result["agent_contribution"] = round(agent_contribution, 4)
        result["strategy_contribution"] = round(strategy_contribution, 4)

        # PHASES_PLAN.md Phase 7 -- Score Calculation Transparency: every term that
        # fed into the final combined_score, laid out explicitly instead of only
        # exposing the already-summed agent_score/strategy_score.
        result["score_breakdown"] = {
            "technical_score": round(technical_score, 4),
            "fundamental_score": round(fundamental_score, 4),
            "news_score": round(news_score, 4),
            "risk_level": risk_level,
            "risk_factor": round(risk_factor, 4),
            "agent_score_pre_risk": round(agent_score_pre_risk, 4),
            "agent_score": round(agent_score, 4),
            "agent_score_normalized": round(agent_norm, 4),
            "agent_weight": AGENT_WEIGHT,
            "agent_contribution": round(agent_contribution, 4),
            "strategy_score": round(strat_score, 4),
            "strategy_score_normalized": round(strat_norm, 4),
            "strategy_weight": STRATEGY_WEIGHT,
            "strategy_contribution": round(strategy_contribution, 4),
            "combined_score": round(combined_score, 4),
            "buy_threshold": BUY_THRESHOLD,
            "sell_threshold": SELL_THRESHOLD,
        }

        # PHASES_PLAN.md Phase 6 -- Explain Every HOLD (and every BUY/SELL): a
        # structured "why", not just the final action, so a HOLD is never shown
        # by itself.
        result["decision_explanation"] = {
            "action": result["action"],
            "confidence": round(result["confidence"], 4),
            "combined_score": round(combined_score, 4),
            "buy_threshold": BUY_THRESHOLD,
            "sell_threshold": SELL_THRESHOLD,
            "agent_reasons": list(reasons),
            "strategy_reasons": [
                {
                    "strategy": vote.get("strategy") or vote.get("name"),
                    "decision": vote.get("decision"),
                    "confidence": vote.get("confidence"),
                    "reason": vote.get("reason"),
                }
                for vote in strategy_results
            ],
        }

        result["hold_reason"] = self._classify_hold_reason(
            action=result["action"],
            decision_status=result["decision_status"],
            status=result["status"],
            risk_level=risk_level,
            portfolio=port,
            strategy_results=strategy_results,
            agent_reasons=reasons,
        )

        # Generate comprehensive AI detailed reasoning breakdown
        try:
            result["detailed_reasoning"] = self.reasoning_engine.synthesize_reasoning(
                symbol=symbol,
                action=result["action"],
                confidence=result["confidence"],
                raw_score=combined_score,
                agent_score=agent_score,
                strat_score=strat_score,
                strategy_votes=strategy_results,
                context=ctx,
            )
        except Exception:
            result["detailed_reasoning"] = {}

        # Log analysis safely
        try:
            self.history.record_analysis(
                symbol=symbol,
                action=result["action"],
                confidence=result["confidence"],
                reason=result["reason"],
                decision_status=result["decision_status"],
                hold_reason=result["hold_reason"],
                analyses={"strategies": strategy_results, "agent_score": agent_score, "ensemble": ensemble_result},
            )
        except Exception:
            pass
        return result

    @staticmethod
    def _classify_hold_reason(
        action: str,
        decision_status: str,
        status: str,
        risk_level: str,
        portfolio: Any,
        strategy_results: list,
        agent_reasons: list,
    ) -> Optional[str]:
        """
        PHASES_PLAN.md Phase 8 -- bucket a HOLD decision into one of
        HOLD_REASON_LABELS using only fields already computed this call, so
        "why did we HOLD" statistics can be aggregated later without
        re-deriving anything from stored history. Returns None for buy/sell.
        """
        if action != "hold":
            return None

        if status == "risk_error":
            return "risk_gate"

        if decision_status == "DATA_UNAVAILABLE" or status == "insufficient_data":
            return "insufficient_data"

        if risk_level in {"high", "unknown", "none"}:
            return "risk_gate"

        if decision_status == "INSUFFICIENT_EDGE":
            position = portfolio.get("position") if isinstance(portfolio, dict) else None
            has_position = bool(position and float(position.get("qty", 0) or 0) != 0)
            if has_position:
                return "existing_position"

            buy_votes = sum(1 for v in strategy_results if v.get("decision") == "buy")
            sell_votes = sum(1 for v in strategy_results if v.get("decision") == "sell")
            if buy_votes >= 1 and sell_votes >= 1:
                return "mixed_strategy_signals"
            if not agent_reasons and buy_votes == 0 and sell_votes == 0:
                return "no_technical_catalyst"

        return "below_confidence_threshold"

    def compute_position_size(
        self,
        action: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[float]:
        """
        Compute shares to trade using volatility targeting or Kelly criterion.

        Priority:
        1. Volatility targeting (if ATR + equity + price available)
        2. Kelly criterion (if trade history stats available)
        3. Fallback to fixed notional
        """
        if action not in ("buy", "sell"):
            return None

        ctx = context or {}
        port = ctx.get("portfolio", {})
        tech = ctx.get("technical", {})

        equity = None
        try:
            acct = port.get("account", {})
            equity = float(acct.get("equity", 0))
        except Exception:
            pass

        price = None
        try:
            price = float(tech.get("signals", {}).get("last_price", 0))
        except Exception:
            pass
        if not price:
            # Try market snapshot
            mkt = ctx.get("market", {})
            price = float(mkt.get("price", 0)) if mkt else None

        if not equity or equity <= 0 or not price or price <= 0:
            return None

        # Try volatility targeting first
        atr = None
        try:
            atr = float(tech.get("signals", {}).get("atr_14", 0))
        except Exception:
            pass

        if atr and atr > 0:
            shares = target_volatility_size(equity, price, atr)
            if shares:
                return shares
            shares = risk_parity_size(equity, price, atr)
            if shares:
                return shares

        # Try Kelly criterion from trade history
        stats = self.history.get_stats()
        if stats:
            win_rate = stats.get("win_rate", 0) / 100.0
            avg_win = stats.get("avg_win", 0)
            avg_loss = stats.get("avg_loss", 0)
            if win_rate > 0 and avg_loss > 0:
                shares = half_kelly(equity, win_rate, avg_win, avg_loss, price)
                if shares:
                    return shares

        return None

    def place_order(self, symbol: str, side: str,
                    qty: Optional[float] = None,
                    notional: Optional[float] = None,
                    reason: str = "",
                    confidence: float = 0.0,
                    context: Optional[Dict] = None) -> dict:
        """Place a paper trade via Alpaca and log it."""
        if self._client is None:
            return {"status": "error", "error": "Alpaca client not initialized"}

        result = place_market_order(self._client, symbol, side, qty=qty, notional=notional)
        if result.get("status") == "submitted":
            self.history.record_order(
                symbol=symbol.upper(), side=side, qty=qty, notional=notional,
                order_id=result["order_id"], status=result["order_status"],
                reason=reason, confidence=confidence, context=context,
            )
        return result

    def maybe_auto_trade(self, symbol: str, analysis: Dict[str, Any],
                         context: Optional[Dict] = None) -> Optional[dict]:
        """Execute a trade if confidence exceeds AUTO_EXECUTE_CONFIDENCE."""
        action = analysis.get("action", "hold")
        confidence = analysis.get("confidence", 0.0)
        reason = analysis.get("reason", "")

        if not ALLOW_DEGRADED_TRADING:
            if analysis.get("status") in {"insufficient_data", "risk_error"}:
                return {"status": "skipped", "reason": "Auto-trading disabled because critical data is missing or risky"}
            if analysis.get("data_quality_score", 100) < 60:
                return {"status": "skipped", "reason": "Auto-trading disabled because data quality is below acceptable threshold"}
            risk = (context or {}).get("risk", {}) if context else {}
            if str(risk.get("status", "ok")).lower() == "error":
                return {"status": "skipped", "reason": "Auto-trading disabled because risk agent failed"}

        if action == "hold" or confidence < AUTO_EXECUTE_CONFIDENCE:
            return None

        port = context.get("portfolio", {}) if context else {}
        pos = port.get("position")
        if action == "buy" and pos and float(pos.get("qty", 0)) > 0:
            return {"status": "skipped", "reason": "Already long, skipping duplicate buy"}
        if action == "sell" and (not pos or float(pos.get("qty", 0)) <= 0):
            return {"status": "skipped", "reason": "No position to sell"}

        qty = self.compute_position_size(action, context)
        if qty is not None and qty > 0:
            return self.place_order(
                symbol=symbol,
                side=action,
                qty=qty,
                reason=reason,
                confidence=confidence,
                context=context,
            )

        return self.place_order(
            symbol=symbol,
            side=action,
            notional=AUTO_TRADE_NOTIONAL,
            reason=reason,
            confidence=confidence,
            context=context,
        )
