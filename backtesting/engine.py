"""
backtesting/engine.py

Backtesting engine that runs the multi-agent pipeline on historical data
to simulate trades and compute performance metrics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from agents.market_agent import MarketAgent
from agents.technical_agent import TechnicalAgent
from backtesting.report import compute_trade_stats
from strategies.momentum import MomentumStrategy
from strategies.trend_following import TrendFollowingStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.breakout import BreakoutStrategy
from strategies.swing import SwingStrategy


@dataclass
class BacktestTrade:
    symbol: str
    side: str  # buy or sell
    entry_date: str
    exit_date: Optional[str] = None
    entry_price: float = 0.0
    exit_price: float = 0.0
    qty: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    reason: str = ""


@dataclass
class BacktestResult:
    symbol: str
    start_date: str
    end_date: str
    initial_cash: float
    final_cash: float
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown_pct: float = 0.0
    trades: List[BacktestTrade] = field(default_factory=list)
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)


class BacktestEngine:
    """Run a strategy on historical bars and simulate trades."""

    def __init__(
        self,
        initial_cash: float = 10000.0,
        position_size_pct: float = 0.1,  # 10% of cash per trade
        stop_loss_pct: float = 0.05,     # 5% stop loss
        take_profit_pct: float = 0.10,   # 10% take profit
    ) -> None:
        self.initial_cash = initial_cash
        self.position_size_pct = position_size_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

        self.market = MarketAgent()
        self.technical = TechnicalAgent()
        self.strategies = [
            MomentumStrategy(),
            TrendFollowingStrategy(),
            MeanReversionStrategy(),
            BreakoutStrategy(),
            SwingStrategy(),
        ]

    def run(
        self,
        symbol: str,
        days: int = 252,
        strategy_filter: Optional[List[str]] = None,
    ) -> BacktestResult:
        """Run backtest on historical data."""
        symbol = symbol.upper()

        # Fetch historical data
        snapshot = self.market.snapshot(symbol, timeframe="1d", days=days)
        bars = getattr(snapshot, "bars", None)
        if bars is None or getattr(bars, "empty", True) or len(bars) < 30:
            return BacktestResult(
                symbol=symbol,
                start_date="n/a",
                end_date="n/a",
                initial_cash=self.initial_cash,
                final_cash=self.initial_cash,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                total_pnl=0.0,
                max_drawdown_pct=0.0,
                trades=[],
                equity_curve=[],
            )

        # Build daily signals by walking through history
        # We simulate that we only know data up to day N when making day N decision
        cash = self.initial_cash
        position: Optional[Dict[str, Any]] = None  # None or {"qty", "entry_price", "entry_date", "stop", "target"}
        trades: List[BacktestTrade] = []
        equity_curve: List[Dict[str, Any]] = []

        max_equity = cash
        max_drawdown = 0.0

        for i in range(30, len(bars)):  # Start after 30 bars to have indicators
            current_bar = bars.iloc[i]
            date = str(current_bar.get("timestamp", "") or current_bar.name)
            price = float(current_bar["close"])
            prev_bars = bars.iloc[:i+1]

            # Compute technical signals from available history
            signals = self._compute_signals(prev_bars)

            # Build context for strategies (simplified)
            context = {
                "technical": {"signals": signals},
                "market": {"metrics": {}},
                "fundamental": {},
                "news": {},
                "risk": {},
                "portfolio": {},
            }

            # Aggregate strategy votes
            strat_score = 0.0
            active_strategies = self.strategies
            if strategy_filter:
                active_strategies = [s for s in self.strategies if s.name in strategy_filter]

            for strat in active_strategies:
                try:
                    vote = strat.evaluate(context)
                    conf = vote.get("confidence", 0)
                    if vote.get("decision") == "buy":
                        strat_score += conf
                    elif vote.get("decision") == "sell":
                        strat_score -= conf
                except Exception:
                    continue

            # Check existing position
            if position is not None:
                # Check stop loss / take profit
                entry = position["entry_price"]
                stop = entry * (1 - self.stop_loss_pct)
                target = entry * (1 + self.take_profit_pct)

                if price <= stop or price >= target or strat_score < -0.5:
                    # Close position
                    pnl = (price - entry) * position["qty"]
                    pnl_pct = (price - entry) / entry * 100 if entry > 0 else 0
                    cash += price * position["qty"]

                    trade = BacktestTrade(
                        symbol=symbol,
                        side="sell",
                        entry_date=position["entry_date"],
                        exit_date=date,
                        entry_price=entry,
                        exit_price=price,
                        qty=position["qty"],
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        reason="stop/target/signal",
                    )
                    trades.append(trade)
                    position = None

            # Open new position
            if position is None and strat_score > 0.8:
                qty = (cash * self.position_size_pct) / price
                if qty > 0:
                    position = {
                        "qty": qty,
                        "entry_price": price,
                        "entry_date": date,
                    }
                    cash -= qty * price

            # Record equity
            equity = cash
            if position is not None:
                equity += position["qty"] * price
            equity_curve.append({"date": date, "equity": round(equity, 2)})

            if equity > max_equity:
                max_equity = equity
            drawdown = (max_equity - equity) / max_equity * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # Close any open position at the end
        if position is not None:
            final_price = float(bars.iloc[-1]["close"])
            entry = position["entry_price"]
            pnl = (final_price - entry) * position["qty"]
            pnl_pct = (final_price - entry) / entry * 100 if entry > 0 else 0
            cash += position["qty"] * final_price

            trade = BacktestTrade(
                symbol=symbol,
                side="sell",
                entry_date=position["entry_date"],
                exit_date=str(bars.iloc[-1].get("timestamp", "") or bars.index[-1]),
                entry_price=entry,
                exit_price=final_price,
                qty=position["qty"],
                pnl=pnl,
                pnl_pct=pnl_pct,
                reason="end of backtest",
            )
            trades.append(trade)

        stats = compute_trade_stats(trades, pnl_getter=lambda t: t.pnl)

        return BacktestResult(
            symbol=symbol,
            start_date=str(bars.iloc[30].get("timestamp", "") or bars.index[30]),
            end_date=str(bars.iloc[-1].get("timestamp", "") or bars.index[-1]),
            initial_cash=self.initial_cash,
            final_cash=round(cash, 2),
            total_trades=stats["trade_count"],
            winning_trades=stats["winning_trades"],
            losing_trades=stats["losing_trades"],
            total_pnl=stats["total_pnl"],
            max_drawdown_pct=round(max_drawdown, 2),
            trades=trades,
            equity_curve=equity_curve,
        )

    def _compute_signals(self, bars: pd.DataFrame) -> dict:
        """Compute technical signals from a slice of bars."""
        from indicators.rsi import compute_rsi
        from indicators.macd import compute_macd
        from indicators.ema import compute_ema
        from indicators.volume import compute_volume_signals

        close = pd.to_numeric(bars["close"], errors="coerce")
        volume = pd.to_numeric(bars.get("volume", pd.Series([0]*len(bars))), errors="coerce")

        signals = {}
        if len(close) >= 15:
            try:
                signals["rsi_14"] = compute_rsi(close, 14)
            except Exception:
                pass
        if len(close) >= 26:
            try:
                signals["macd"], signals["macd_signal"], signals["macd_hist"] = compute_macd(close)
            except Exception:
                pass
        if len(close) >= 20:
            try:
                signals["ema_20"] = compute_ema(close, 20)
            except Exception:
                pass
        if len(close) >= 50:
            try:
                signals["ema_50"] = compute_ema(close, 50)
            except Exception:
                pass
        if len(volume) >= 20:
            try:
                vol_sigs = compute_volume_signals(volume, close)
                signals.update(vol_sigs)
            except Exception:
                pass

        return signals

    def to_dict(self, result: BacktestResult) -> dict:
        """Serialize BacktestResult to dict for JSON."""
        return {
            "symbol": result.symbol,
            "start_date": result.start_date,
            "end_date": result.end_date,
            "initial_cash": result.initial_cash,
            "final_cash": result.final_cash,
            "total_trades": result.total_trades,
            "winning_trades": result.winning_trades,
            "losing_trades": result.losing_trades,
            "total_pnl": result.total_pnl,
            "max_drawdown_pct": result.max_drawdown_pct,
            "win_rate": round(result.winning_trades / result.total_trades * 100, 1) if result.total_trades > 0 else 0,
            "trades": [
                {
                    "symbol": t.symbol,
                    "side": t.side,
                    "entry_date": t.entry_date,
                    "exit_date": t.exit_date,
                    "entry_price": round(t.entry_price, 2),
                    "exit_price": round(t.exit_price, 2),
                    "qty": round(t.qty, 4),
                    "pnl": round(t.pnl, 2),
                    "pnl_pct": round(t.pnl_pct, 2),
                }
                for t in result.trades
            ],
            "equity_curve": result.equity_curve,
        }
