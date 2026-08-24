"""
Chat-based PAPER TRADING agent.

- Alpaca (paper account) executes buy/sell orders -- simulated money, no real trades.
- Google Gemini (gemini-3.5-flash) is the natural-language brain: it reads what you
  type, decides which tool to call (get price, get positions, buy, sell...), and
  replies in plain English once the tool result comes back.

Run it with:  python trading_agent.py
"""

import os
import json

from dotenv import load_dotenv
from google import genai

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.common.exceptions import APIError
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

MODEL_NAME = "gemini-3.1-flash-lite"          # current free-tier Gemini model
MAX_TOOL_ROUNDS = 8                      # safety cap on chained tool calls per turn

# Ask "y/n" before any order actually gets sent to Alpaca. Flip to False if you
# want the agent to place orders immediately without a confirmation prompt.
REQUIRE_CONFIRMATION = True

CONFIGURED = bool(ALPACA_API_KEY and ALPACA_SECRET_KEY and GEMINI_API_KEY)

# Keep the dashboard usable without credentials. API-backed actions return a
# clear configuration error until paper-trading credentials are supplied.
trading_client = (
    TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)
    if ALPACA_API_KEY and ALPACA_SECRET_KEY
    else None
)
data_client = (
    StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
    if ALPACA_API_KEY and ALPACA_SECRET_KEY
    else None
)
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


def _configuration_error() -> dict:
    missing = [
        name
        for name, value in (
            ("ALPACA_API_KEY", ALPACA_API_KEY),
            ("ALPACA_SECRET_KEY", ALPACA_SECRET_KEY),
            ("GEMINI_API_KEY", GEMINI_API_KEY),
        )
        if not value
    ]
    return {
        "status": "not_configured",
        "error": f"Add {', '.join(missing)} to enable paper-trading actions.",
    }

SYSTEM_INSTRUCTION = """You are a trading assistant chatting with a user about their
Alpaca PAPER TRADING account. This is simulated money -- no real funds are ever at risk.

Rules:
- Always use the provided tools to check prices, positions, or account info. Never
  guess or make up a number.
- Translate company names to ticker symbols yourself (e.g. "Apple" -> AAPL,
  "Tesla" -> TSLA, "Google"/"Alphabet" -> GOOGL).
- If the user wants to buy or sell but gives no amount, ask whether they mean a
  number of shares or a dollar amount -- do not guess a quantity.
- If the user says "sell all" / "sell everything" of a symbol, call get_positions
  first to find the exact quantity they hold, then sell that exact quantity.
- After a tool call returns, tell the user plainly what actually happened
  (order id, status, filled price if available). If status is "cancelled_by_user",
  say the order was not placed.
- Never claim a trade executed unless a tool result confirms it.
- Keep replies short and conversational.
"""

# --------------------------------------------------------------------------
# Tool implementations -- these are the only things that ever touch Alpaca
# --------------------------------------------------------------------------


def get_account_info():
    """Get paper account cash, buying power, portfolio value, and equity."""
    if trading_client is None:
        return _configuration_error()
    a = trading_client.get_account()
    return {
        "cash": a.cash,
        "buying_power": a.buying_power,
        "portfolio_value": a.portfolio_value,
        "equity": a.equity,
    }


def get_positions():
    """List every stock currently held in the paper account, with qty and P&L."""
    if trading_client is None:
        return _configuration_error()
    positions = trading_client.get_all_positions()
    return {
        "positions": [
            {
                "symbol": p.symbol,
                "qty": p.qty,
                "avg_entry_price": p.avg_entry_price,
                "current_price": p.current_price,
                "market_value": p.market_value,
                "unrealized_pl": p.unrealized_pl,
            }
            for p in positions
        ]
    }


def get_stock_price(symbol: str):
    """Get the latest bid/ask quote for a stock ticker symbol."""
    if data_client is None:
        return _configuration_error()
    symbol = symbol.upper()
    try:
        req = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
        quote = data_client.get_stock_latest_quote(req)[symbol]
        return {"symbol": symbol, "bid_price": quote.bid_price, "ask_price": quote.ask_price}
    except Exception as e:
        return {"error": str(e)}


def buy_stock(symbol: str, qty: float = None, notional: float = None):
    """Place a market order to BUY a stock in the paper account.
    Provide exactly one of qty (number of shares, fractional OK) or notional
    (a dollar amount to spend)."""
    return _place_order(symbol, OrderSide.BUY, qty, notional)


def sell_stock(symbol: str, qty: float = None, notional: float = None):
    """Place a market order to SELL a stock in the paper account.
    Provide exactly one of qty (number of shares, fractional OK) or notional
    (a dollar amount to sell)."""
    return _place_order(symbol, OrderSide.SELL, qty, notional)


def _place_order(symbol: str, side: OrderSide, qty, notional):
    symbol = symbol.upper()

    if trading_client is None:
        return _configuration_error()
    if qty is None and notional is None:
        return {"status": "error", "error": "Must specify either qty or notional."}
    if qty is not None and notional is not None:
        return {"status": "error", "error": "Specify only one of qty or notional, not both."}

    order_kwargs = dict(symbol=symbol, side=side, time_in_force=TimeInForce.DAY)
    if qty is not None:
        order_kwargs["qty"] = qty
    else:
        order_kwargs["notional"] = notional

    try:
        order = trading_client.submit_order(order_data=MarketOrderRequest(**order_kwargs))
        return {
            "status": "submitted",
            "order_id": str(order.id),
            "symbol": order.symbol,
            "qty": order.qty,
            "side": order.side.value,
            "order_status": order.status.value,
        }
    except APIError as e:
        return {"status": "error", "error": str(e)}


TOOL_IMPLS = {
    "get_account_info": get_account_info,
    "get_positions": get_positions,
    "get_stock_price": get_stock_price,
    "buy_stock": buy_stock,
    "sell_stock": sell_stock,
}

TOOL_DECLARATIONS = [
    {
        "type": "function",
        "name": "get_account_info",
        "description": "Get paper trading account cash, buying power, portfolio value, and equity.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "get_positions",
        "description": "List every stock currently held in the paper account, with quantity and P&L.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "get_stock_price",
        "description": "Get the latest bid/ask price quote for a stock ticker symbol.",
        "parameters": {
            "type": "object",
            "properties": {"symbol": {"type": "string", "description": "Ticker symbol, e.g. AAPL"}},
            "required": ["symbol"],
        },
    },
    {
        "type": "function",
        "name": "buy_stock",
        "description": (
            "Place a market order to buy a stock in the paper account. "
            "Provide exactly one of qty or notional."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker symbol, e.g. AAPL"},
                "qty": {"type": "number", "description": "Number of shares to buy (fractional allowed)."},
                "notional": {"type": "number", "description": "Dollar amount to spend, e.g. 500."},
            },
            "required": ["symbol"],
        },
    },
    {
        "type": "function",
        "name": "sell_stock",
        "description": (
            "Place a market order to sell a stock in the paper account. "
            "Provide exactly one of qty or notional."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker symbol, e.g. AAPL"},
                "qty": {"type": "number", "description": "Number of shares to sell (fractional allowed)."},
                "notional": {"type": "number", "description": "Dollar amount to sell, e.g. 500."},
            },
            "required": ["symbol"],
        },
    },
]

# --------------------------------------------------------------------------
# Agent loop -- talks to Gemini, executes any tool calls, repeats until Gemini
# gives a final plain-text answer
# --------------------------------------------------------------------------


def run_turn(user_text: str, previous_interaction_id):
    if gemini_client is None:
        return (
            "The AI trading assistant is not configured yet. Add GEMINI_API_KEY "
            "to enable chat, and Alpaca paper credentials for account actions.",
            previous_interaction_id,
        )

    kwargs = dict(
        model=MODEL_NAME,
        input=user_text,
        tools=TOOL_DECLARATIONS,
        system_instruction=SYSTEM_INSTRUCTION,
    )
    if previous_interaction_id:
        kwargs["previous_interaction_id"] = previous_interaction_id

    try:
        interaction = gemini_client.interactions.create(**kwargs)
    except Exception as e:
        return f"(Gemini API error: {e})", previous_interaction_id

    for _ in range(MAX_TOOL_ROUNDS):
        fn_calls = [s for s in interaction.steps if s.type == "function_call"]
        if not fn_calls:
            break

        results_input = []
        for step in fn_calls:
            fn = TOOL_IMPLS.get(step.name)
            if fn is None:
                result, is_error = {"error": f"Unknown tool '{step.name}'"}, True
            else:
                try:
                    result = fn(**step.arguments)
                    is_error = isinstance(result, dict) and result.get("status") == "error"
                except Exception as e:
                    result, is_error = {"error": str(e)}, True

            results_input.append(
                {
                    "type": "function_result",
                    "name": step.name,
                    "call_id": step.id,
                    "result": [{"type": "text", "text": json.dumps(result)}],
                    "is_error": is_error,
                }
            )

        try:
            interaction = gemini_client.interactions.create(
                model=MODEL_NAME,
                input=results_input,
                tools=TOOL_DECLARATIONS,
                system_instruction=SYSTEM_INSTRUCTION,
                previous_interaction_id=interaction.id,
            )
        except Exception as e:
            return f"(Gemini API error while sending tool result: {e})", interaction.id

    return (interaction.output_text or "(no response text)"), interaction.id
