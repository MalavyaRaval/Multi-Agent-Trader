"""
portfolio_agent.py

Tracks current Alpaca paper-trading positions and account state.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from alpaca.trading.client import TradingClient

from data.alpaca_client import account_to_dict, get_trading_client, positions_to_list


class PortfolioAgent:
    name = "portfolio_agent"

    def __init__(self) -> None:
        self._client: Optional[TradingClient] = get_trading_client()

    def analyze(self, symbol: str) -> dict:
        symbol = symbol.upper()
        result = {"symbol": symbol, "status": "portfolio check ready", "position": None, "account": {}}

        if self._client is None:
            result["status"] = "portfolio check skipped (no Alpaca client)"
            return result

        try:
            # Account info
            account = self._client.get_account()
            result["account"] = account_to_dict(account)

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
            result["all_positions"] = positions_to_list(self._client.get_all_positions())

        except Exception as e:
            result["status"] = f"portfolio check error: {e}"
            result["position"] = None
            result["account"] = {}

        return result

    def get_account_summary(self) -> Dict[str, Any]:
        if self._client is None:
            return {}
        try:
            return account_to_dict(self._client.get_account())
        except Exception:
            return {}
