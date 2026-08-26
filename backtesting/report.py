"""
backtesting/report.py

Generate performance reports from backtest results.
"""

from __future__ import annotations

import json
import math
from typing import Any, Callable, Dict, List


def compute_trade_stats(
    trades: List[Any],
    pnl_getter: Callable[[Any], float] = lambda t: t.get("pnl", 0) or 0,
) -> Dict[str, Any]:
    """
    Partition trades by win/loss and summarize P&L. Shared by backtesting/report.py,
    backtesting/engine.py, and reporting/daily_report.py so the same win/loss/P&L
    numbers aren't computed three slightly-different ways.

    pnl_getter lets callers pass either plain dicts (the default, `t["pnl"]`) or
    objects like BacktestTrade (`pnl_getter=lambda t: t.pnl`).
    """
    pnls = [float(pnl_getter(t)) for t in trades]
    winning = [p for p in pnls if p > 0]
    losing = [p for p in pnls if p <= 0]
    total_pnl = sum(pnls)
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))

    return {
        "trade_count": len(trades),
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "total_pnl": round(total_pnl, 2),
        "avg_trade_pnl": round(total_pnl / len(trades), 2) if trades else 0.0,
        "best_trade_pnl": round(max(pnls), 2) if pnls else 0.0,
        "worst_trade_pnl": round(min(pnls), 2) if pnls else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0),
    }


def generate_report(backtest_dict: dict) -> dict:
    """Enrich a backtest result with additional performance metrics."""
    report = dict(backtest_dict)

    trades = report.get("trades", [])
    stats = compute_trade_stats(trades)
    report["total_pnl"] = stats["total_pnl"]
    report["avg_trade_pnl"] = stats["avg_trade_pnl"]
    report["profit_factor"] = stats["profit_factor"]
    report["best_trade_pnl"] = stats["best_trade_pnl"]
    report["worst_trade_pnl"] = stats["worst_trade_pnl"]
    report.setdefault("total_trades", stats["trade_count"])
    report.setdefault("winning_trades", stats["winning_trades"])
    report.setdefault("losing_trades", stats["losing_trades"])
    report.setdefault("max_drawdown_pct", 0.0)

    # Total return %
    initial = report.get("initial_cash", 1)
    final = report.get("final_cash", initial)
    report["total_return_pct"] = round((final - initial) / initial * 100, 2) if initial else 0.0

    equity_curve = report.get("equity_curve", [])
    if len(equity_curve) < 2:
        report["sharpe_ratio"] = 0.0
        return report

    # Compute daily returns from equity curve
    equities = [e["equity"] for e in equity_curve]
    returns = []
    for i in range(1, len(equities)):
        if equities[i - 1] > 0:
            returns.append((equities[i] - equities[i - 1]) / equities[i - 1])

    # Sharpe ratio (annualized, assuming 252 trading days)
    if returns:
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        std_dev = math.sqrt(variance) if variance > 0 else 0
        if std_dev > 0:
            sharpe = (avg_return / std_dev) * math.sqrt(252)
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0

    report["sharpe_ratio"] = round(sharpe, 2)

    return report


def format_report_text(report: dict) -> str:
    """Format a report as human-readable text."""
    lines = [
        f"Backtest Report: {report['symbol']}",
        f"Period: {report['start_date']} to {report['end_date']}",
        "",
        f"Initial Cash:    ${report['initial_cash']:,.2f}",
        f"Final Cash:      ${report['final_cash']:,.2f}",
        f"Total Return:    {report['total_return_pct']:+.2f}%",
        f"Total P&L:       ${report['total_pnl']:,.2f}",
        "",
        f"Total Trades:    {report['total_trades']}",
        f"Winning Trades:  {report['winning_trades']} ({report.get('win_rate', 0)}%)",
        f"Losing Trades:   {report['losing_trades']}",
        f"Avg Trade P&L:   ${report['avg_trade_pnl']:,.2f}",
        f"Best Trade:      ${report['best_trade_pnl']:,.2f}",
        f"Worst Trade:     ${report['worst_trade_pnl']:,.2f}",
        f"Profit Factor:   {report['profit_factor']}",
        "",
        f"Max Drawdown:    {report['max_drawdown_pct']:.2f}%",
        f"Sharpe Ratio:    {report['sharpe_ratio']}",
    ]
    return "\n".join(lines)
