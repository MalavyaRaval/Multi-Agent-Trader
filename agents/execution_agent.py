"""
execution_agent.py

Makes the final BUY / SELL / HOLD decision by combining:
- All agent analyses (technical, fundamental, news, risk, portfolio)
- All strategy evaluations (momentum, trend, mean-reversion, breakout, swing)
- Risk-adjusted position sizing

Can place real paper trades through Alpaca and logs everything to TradeHistory.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.common.exceptions import APIError

from strategies.momentum import MomentumStrategy
from strategies.trend_following import TrendFollowingStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.breakout import BreakoutStrategy
from strategies.swing import SwingStrategy
from memory.trade_history import TradeHistory
from sizing import target_volatility_size, risk_parity_size, half_kelly
from optimization.ensemble import StrategyEnsemble

load_dotenv()

# Auto-execute threshold: only trade if confidence >= this value
AUTO_EXECUTE_CONFIDENCE = float(os.getenv("AUTO_EXECUTE_CONFIDENCE", "0.75"))
# Default notional size for auto-trades (fallback when smart sizing fails)
AUTO_TRADE_NOTIONAL = float(os.getenv("AUTO_TRADE_NOTIONAL", "500"))


class ExecutionAgent:
    name = "execution_agent"

    def __init__(self) -> None:
        self._client: Optional[TradingClient] = None
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")
        if api_key and secret_key:
            try:
                self._client = TradingClient(api_key, secret_key, paper=True)
            except Exception:
                self._client = None
        self.history = TradeHistory()
        self.ensemble = StrategyEnsemble()
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
            "reason": "",
            "strategy_votes": [],
            "ensemble": {},
        }

        if not ctx:
            result["status"] = "execution analysis skipped (no context)"
            return result

        # ---- Run all strategies ----
        strategy_results = []
        for strat in self.strategies:
            try:
                vote = strat.evaluate(ctx)
                # Ensure vote has a name for ensemble weighting
                if isinstance(vote, dict) and "name" not in vote:
                    vote["name"] = getattr(strat, "name", strat.__class__.__name__)
                strategy_results.append(vote)
            except Exception:
                pass
        result["strategy_votes"] = strategy_results

        # ---- Aggregate strategy votes with ensemble weights ----
        ensemble_result = self.ensemble.aggregate(strategy_results)
        result["ensemble"] = ensemble_result
        strat_score = ensemble_result.get("weighted_score", 0.0)

        # ---- Agent-based scoring (from Phase 1) ----
        tech = ctx.get("technical", {})
        fund = ctx.get("fundamental", {})
        news = ctx.get("news", {})
        risk = ctx.get("risk", {})
        port = ctx.get("portfolio", {})

        agent_score = 0.0
        reasons = []

        signals = tech.get("signals", {})
        rsi = signals.get("rsi_14")
        macd = signals.get("macd")
        macd_signal = signals.get("macd_signal")
        ema_20 = signals.get("ema_20")
        ema_50 = signals.get("ema_50")
        volume_trend = signals.get("volume_trend", "neutral")

        if rsi is not None:
            if rsi < 30:
                agent_score += 1.5
                reasons.append(f"RSI oversold ({rsi:.1f})")
            elif rsi > 70:
                agent_score -= 1.5
                reasons.append(f"RSI overbought ({rsi:.1f})")

        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                agent_score += 1.0
                reasons.append("MACD bullish crossover")
            else:
                agent_score -= 1.0
                reasons.append("MACD bearish crossover")

        if ema_20 is not None and ema_50 is not None:
            if ema_20 > ema_50:
                agent_score += 0.5
                reasons.append("Price above EMA50 (uptrend)")
            else:
                agent_score -= 0.5
                reasons.append("Price below EMA50 (downtrend)")

        if "strong_buy" in volume_trend:
            agent_score += 0.5
            reasons.append("Volume confirms upside")
        elif "strong_sell" in volume_trend:
            agent_score -= 0.5
            reasons.append("Volume confirms downside")

        fund_score = fund.get("score", 0)
        agent_score += fund_score * 0.5
        if fund_score > 0:
            reasons.append("Fundamentals look good")
        elif fund_score < 0:
            reasons.append("Fundamentals weak")

        sentiment = news.get("sentiment", "neutral")
        if sentiment == "positive":
            agent_score += 0.5
            reasons.append("Positive news sentiment")
        elif sentiment == "negative":
            agent_score -= 0.5
            reasons.append("Negative news sentiment")

        risk_level = str(risk.get("risk_level", "medium")).lower()
        risk_factor = 1.0
        if risk_level == "high":
            risk_factor = 0.35
            reasons.append("High risk - reducing position size and conviction")
        elif risk_level == "medium":
            risk_factor = 0.7
        elif risk_level == "low":
            risk_factor = 0.9

        agent_score *= risk_factor

        # ---- Combine strategy + agent scores ----
        # Strategies get 40% weight, agents get 60%
        combined_score = (agent_score * 0.6 + strat_score * 1.5) * risk_factor  # strategies already scaled 0..1

        # Portfolio context
        position = port.get("position")
        if position and position.get("qty"):
            qty = float(position.get("qty", 0))
            if qty > 0 and combined_score < -1.5:
                result["action"] = "sell"
                result["confidence"] = min(abs(combined_score) / 4.0, 1.0)
            elif qty == 0 and combined_score > 1.5:
                result["action"] = "buy"
                result["confidence"] = min(combined_score / 4.0, 1.0)
            else:
                result["action"] = "hold"
                result["confidence"] = max(0.0, 1.0 - abs(combined_score) / 1.5)
        else:
            if combined_score > 1.5:
                result["action"] = "buy"
                result["confidence"] = min(combined_score / 4.0, 1.0)
            elif combined_score < -1.5:
                result["action"] = "sell"
                result["confidence"] = min(abs(combined_score) / 4.0, 1.0)
            else:
                result["action"] = "hold"
                result["confidence"] = max(0.0, 1.0 - abs(combined_score) / 1.5)

        result["reason"] = "; ".join(reasons) if reasons else "No strong signals"
        result["raw_score"] = round(combined_score, 2)
        result["agent_score"] = round(agent_score, 2)
        result["strategy_score"] = round(strat_score, 2)

        # Log analysis safely
        try:
            self.history.record_analysis(
                symbol=symbol,
                action=result["action"],
                confidence=result["confidence"],
                reason=result["reason"],
                analyses={"strategies": strategy_results, "agent_score": agent_score, "ensemble": ensemble_result},
            )
        except Exception:
            pass
        return result

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
        symbol = symbol.upper()
        side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        order_kwargs = dict(symbol=symbol, side=side_enum, time_in_force=TimeInForce.DAY)
        if qty is not None:
            order_kwargs["qty"] = qty
        elif notional is not None:
            order_kwargs["notional"] = notional
        else:
            return {"status": "error", "error": "Must specify qty or notional"}

        try:
            order = self._client.submit_order(order_data=MarketOrderRequest(**order_kwargs))
            result = {
                "status": "submitted",
                "order_id": str(order.id),
                "symbol": order.symbol,
                "side": side.upper(),
                "qty": order.qty,
                "order_status": order.status.value,
            }
            self.history.record_order(
                symbol=symbol, side=side, qty=qty, notional=notional,
                order_id=str(order.id), status=order.status.value,
                reason=reason, confidence=confidence, context=context,
            )
            return result
        except APIError as e:
            return {"status": "error", "error": str(e)}

    def maybe_auto_trade(self, symbol: str, analysis: Dict[str, Any],
                         context: Optional[Dict] = None) -> Optional[dict]:
        """Execute a trade if confidence exceeds AUTO_EXECUTE_CONFIDENCE."""
        action = analysis.get("action", "hold")
        confidence = analysis.get("confidence", 0.0)
        reason = analysis.get("reason", "")

        if action == "hold" or confidence < AUTO_EXECUTE_CONFIDENCE:
            return None

        # Check if we already have a position (simple anti-churn)
        port = context.get("portfolio", {}) if context else {}
        pos = port.get("position")
        if action == "buy" and pos and float(pos.get("qty", 0)) > 0:
            return {"status": "skipped", "reason": "Already long, skipping duplicate buy"}
        if action == "sell" and (not pos or float(pos.get("qty", 0)) <= 0):
            return {"status": "skipped", "reason": "No position to sell"}

        # Smart position sizing
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

        # Fallback to fixed notional
        return self.place_order(
            symbol=symbol,
            side=action,
            notional=AUTO_TRADE_NOTIONAL,
            reason=reason,
            confidence=confidence,
            context=context,
        )
