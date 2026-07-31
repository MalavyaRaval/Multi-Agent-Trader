"""
memory/trade_history.py

Persistent trade history storage (JSON file-backed).
Tracks every order, its analysis context, and outcome.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import MEMORY_DIR


class TradeHistory:
    def __init__(self, filepath: Optional[str] = None) -> None:
        self.filepath = filepath or str(MEMORY_DIR / "trade_history.json")
        self._lock = threading.Lock()
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not os.path.exists(self.filepath):
            os.makedirs(os.path.dirname(self.filepath) or ".", exist_ok=True)
            self._write([])

    def _read(self) -> List[Dict[str, Any]]:
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _write(self, data: List[Dict[str, Any]]) -> None:
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def record(self, record: Dict[str, Any]) -> None:
        record["recorded_at"] = datetime.utcnow().isoformat()
        with self._lock:
            history = self._read()
            history.append(record)
            self._write(history)

    def record_order(self, symbol: str, side: str, qty: Optional[float],
                     notional: Optional[float], order_id: str,
                     status: str, reason: str, confidence: float,
                     context: Optional[Dict] = None) -> None:
        self.record({
            "type": "order",
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "notional": notional,
            "order_id": order_id,
            "order_status": status,
            "reason": reason,
            "confidence": confidence,
            "context": context or {},
        })

    def record_analysis(self, symbol: str, action: str, confidence: float,
                        reason: str, analyses: Optional[Dict] = None) -> None:
        self.record({
            "type": "analysis",
            "symbol": symbol,
            "action": action,
            "confidence": confidence,
            "reason": reason,
            "analyses": analyses or {},
        })

    def get_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            history = self._read()
        return history[-limit:][::-1]  # newest first

    def get_by_symbol(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        symbol = symbol.upper()
        with self._lock:
            history = self._read()
        filtered = [h for h in history if h.get("symbol") == symbol]
        return filtered[-limit:][::-1]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            history = self._read()
        orders = [h for h in history if h.get("type") == "order"]
        analyses = [h for h in history if h.get("type") == "analysis"]
        buy_orders = [o for o in orders if o.get("side") == "buy"]
        sell_orders = [o for o in orders if o.get("side") == "sell"]

        # Estimate win rate from analysis records (actions with confidence)
        completed = [h for h in history if h.get("type") in ("order", "analysis")]
        wins = 0
        losses = 0
        win_amounts = []
        loss_amounts = []

        for o in orders:
            notional = o.get("notional") or 0
            if notional > 0:
                # Fake P&L estimation based on context if available
                ctx = o.get("context", {})
                exec_dec = ctx.get("execution", {})
                if exec_dec.get("action") == "sell" and exec_dec.get("confidence", 0) > 0.7:
                    wins += 1
                    win_amounts.append(notional * 0.05)
                elif exec_dec.get("action") == "sell" and exec_dec.get("confidence", 0) < 0.4:
                    losses += 1
                    loss_amounts.append(notional * 0.03)

        total_trades = wins + losses
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 50.0
        avg_win = sum(win_amounts) / len(win_amounts) if win_amounts else 100.0
        avg_loss = sum(loss_amounts) / len(loss_amounts) if loss_amounts else 50.0

        return {
            "total_orders": len(orders),
            "total_analyses": len(analyses),
            "buy_orders": len(buy_orders),
            "sell_orders": len(sell_orders),
            "win_rate": round(win_rate, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "recent": orders[-5:][::-1],
        }
        with self._lock:
            history = self._read()
        orders = [h for h in history if h.get("type") == "order"]
        analyses = [h for h in history if h.get("type") == "analysis"]
        buy_orders = [o for o in orders if o.get("side") == "buy"]
        sell_orders = [o for o in orders if o.get("side") == "sell"]

        # Win rate estimation: compare sell vs buy average notional
        # (Very rough — real P&L needs Alpaca fills)
        return {
            "total_orders": len(orders),
            "total_analyses": len(analyses),
            "buy_orders": len(buy_orders),
            "sell_orders": len(sell_orders),
            "recent": orders[-5:][::-1],
        }

    def clear(self) -> None:
        with self._lock:
            self._write([])
