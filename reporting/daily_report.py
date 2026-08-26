from __future__ import annotations

from typing import Any, Dict, List

from backtesting.report import compute_trade_stats


def build_daily_report(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a lightweight daily report from recent trades."""
    trades = trades or []
    stats = compute_trade_stats(trades)

    return {
        "report_type": "daily",
        "summary": {
            "trade_count": stats["trade_count"],
            "winning_trades": stats["winning_trades"],
            "losing_trades": stats["losing_trades"],
            "total_pnl": stats["total_pnl"],
            "avg_pnl": stats["avg_trade_pnl"],
        },
        "highlights": [
            f"Processed {len(trades)} trades",
            f"Net P&L: ${stats['total_pnl']:,.2f}",
        ],
    }
