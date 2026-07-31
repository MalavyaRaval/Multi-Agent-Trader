"""
portfolio_agent.py

Tracks current Alpaca paper-trading positions and account state.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

load_dotenv()
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")


class PortfolioAgent:
    name = "portfolio_agent"

    def __init__(self) -> None:
        self._client: Optional[TradingClient] = None
        if ALPACA_API_KEY and ALPACA_SECRET_KEY:
            try:
                self._client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)
            except Exception:
                pass

    def analyze(self, symbol: str) -> dict:
        symbol = symbol.upper()
        result = {"symbol": symbol, "status": "portfolio check ready", "position": None, "account": {}}

        if self._client is None:
            result["status"] = "portfolio check skipped (no Alpaca client)"
            return result

        try:
            # Account info
            account = self._client.get_account()
            result["account"] = {
                "cash": account.cash,
                "buying_power": account.buying_power,
                "portfolio_value": account.portfolio_value,
                "equity": account.equity,
            }

            # Position for this symbol
            try:
                position = self._client.get_open_position(symbol)
                result["position"] = {
                    "symbol": position.symbol,
                    "qty": position.qty,
                    "avg_entry_price": position.avg_entry_price,
                    "current_price": position.current_price,
                    "market_value": position.market_value,
                    "unrealized_pl": position.unrealized_pl,
                    "unrealized_plpc": position.unrealized_plpc,
                }
            except Exception:
                result["position"] = None  # No open position

            # All positions
            all_positions = self._client.get_all_positions()
            result["all_positions"] = [
                {
                    "symbol": p.symbol,
                    "qty": p.qty,
                    "market_value": p.market_value,
                    "unrealized_pl": p.unrealized_pl,
                }
                for p in all_positions
            ]

        except Exception as e:
            result["status"] = f"portfolio check error: {e}"

        return result

    def get_account_summary(self) -> Dict[str, Any]:
        if self._client is None:
            return {}
        try:
            a = self._client.get_account()
            return {
                "cash": a.cash,
                "buying_power": a.buying_power,
                "portfolio_value": a.portfolio_value,
                "equity": a.equity,
            }
        except Exception:
            return {}
