"""
backtesting/report.py

Generate performance reports from backtest results.
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, List


def generate_report(backtest_dict: dict) -> dict:
    """Enrich a backtest result with additional performance metrics."""
    report = dict(backtest_dict)

    equity_curve = report.get("equity_curve", [])
    if len(equity_curve) < 2:
        report["sharpe_ratio"] = 0.0
        report["avg_trade_pnl"] = 0.0
        report["profit_factor"] = 0.0
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

    # Average trade P&L
    trades = report.get("trades", [])
    if trades:
        report["avg_trade_pnl"] = round(sum(t["pnl"] for t in trades) / len(trades), 2)
    else:
        report["avg_trade_pnl"] = 0.0

    # Profit factor = gross profit / gross loss
    gross_profit = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    report["profit_factor"] = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

    # Total return %
    initial = report.get("initial_cash", 1)
    final = report.get("final_cash", initial)
    report["total_return_pct"] = round((final - initial) / initial * 100, 2)

    # Best / worst trade
    if trades:
        report["best_trade_pnl"] = round(max(t["pnl"] for t in trades), 2)
        report["worst_trade_pnl"] = round(min(t["pnl"] for t in trades), 2)
    else:
        report["best_trade_pnl"] = 0.0
        report["worst_trade_pnl"] = 0.0

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
