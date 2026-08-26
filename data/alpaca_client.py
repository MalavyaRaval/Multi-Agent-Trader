"""
data/alpaca_client.py

Canonical factory for constructing Alpaca SDK clients, and for the small set
of Alpaca operations (submit a market order, shape an account/positions
response) that used to be copy-pasted across agents/execution_agent.py,
agents/portfolio_agent.py, agents/market_agent.py, and trading_agent.py.

Note: visualization/portfolio.py maintains its own separate Alpaca access
layer (a mix of the SDK and raw REST calls for endpoints the SDK client here
doesn't need) and has not been migrated onto this module.

Client construction is intentionally NOT cached: these constructors don't do
network I/O, and caching a None result (e.g. at process start before
credentials are configured) would keep every caller stuck on "unconfigured"
even after credentials become available, since nothing would ever call the
factory again to re-check.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest
from alpaca.common.exceptions import APIError
from alpaca.data.historical import StockHistoricalDataClient

from config import ALPACA_API_KEY, ALPACA_SECRET_KEY

logger = logging.getLogger(__name__)


def has_alpaca_credentials() -> bool:
    return bool(ALPACA_API_KEY and ALPACA_SECRET_KEY)


def get_trading_client() -> Optional[TradingClient]:
    """Return a paper-trading TradingClient, or None if credentials are missing/invalid."""
    if not has_alpaca_credentials():
        return None
    try:
        return TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)
    except Exception as exc:
        logger.warning("Could not initialize Alpaca trading client: %s", exc)
        return None


def get_market_data_client() -> Optional[StockHistoricalDataClient]:
    """Return an Alpaca market-data client, or None if credentials are missing/invalid."""
    if not has_alpaca_credentials():
        return None
    try:
        return StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
    except Exception as exc:
        logger.warning("Could not initialize Alpaca market data client: %s", exc)
        return None


def place_market_order(
    client: TradingClient,
    symbol: str,
    side: Union[str, OrderSide],
    qty: Optional[float] = None,
    notional: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Submit a market order on an already-constructed TradingClient.
    Caller is responsible for checking that `client` is not None first.
    """
    if qty is None and notional is None:
        return {"status": "error", "error": "Must specify either qty or notional."}
    if qty is not None and notional is not None:
        return {"status": "error", "error": "Specify only one of qty or notional, not both."}

    symbol = symbol.upper()
    side_enum = side if isinstance(side, OrderSide) else (
        OrderSide.BUY if str(side).lower() == "buy" else OrderSide.SELL
    )
    order_kwargs: Dict[str, Any] = dict(symbol=symbol, side=side_enum, time_in_force=TimeInForce.DAY)
    order_kwargs["qty" if qty is not None else "notional"] = qty if qty is not None else notional

    try:
        order = client.submit_order(order_data=MarketOrderRequest(**order_kwargs))
        return {
            "status": "submitted",
            "order_id": str(order.id),
            "symbol": order.symbol,
            "side": order.side.value,
            "qty": order.qty,
            "order_status": order.status.value,
        }
    except APIError as e:
        return {"status": "error", "error": str(e)}


def account_to_dict(account: Any) -> Dict[str, Any]:
    """Shape an Alpaca Account object into the dict every caller wants."""
    return {
        "cash": account.cash,
        "buying_power": account.buying_power,
        "portfolio_value": account.portfolio_value,
        "equity": account.equity,
    }


def positions_to_list(positions: Any) -> List[Dict[str, Any]]:
    """Shape a list of Alpaca Position objects into plain dicts."""
    return [
        {
            "symbol": p.symbol,
            "qty": p.qty,
            "avg_entry_price": getattr(p, "avg_entry_price", None),
            "current_price": getattr(p, "current_price", None),
            "market_value": p.market_value,
            "unrealized_pl": p.unrealized_pl,
        }
        for p in positions
    ]
