from __future__ import annotations

from typing import Any, Dict, List


def build_daily_report(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a lightweight daily report from recent trades."""
    trades = trades or []
    total_pnl = sum(float(t.get("pnl", 0) or 0) for t in trades)
    winning = [t for t in trades if float(t.get("pnl", 0) or 0) > 0]
    losing = [t for t in trades if float(t.get("pnl", 0) or 0) <= 0]

    return {
        "report_type": "daily",
        "summary": {
            "trade_count": len(trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "total_pnl": round(total_pnl, 2),
            "avg_pnl": round(total_pnl / len(trades), 2) if trades else 0.0,
        },
        "highlights": [
            f"Processed {len(trades)} trades",
            f"Net P&L: ${round(total_pnl, 2):,.2f}",
        ],
    }
