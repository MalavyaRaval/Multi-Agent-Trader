"""
Chat-based PAPER TRADING agent.

- Alpaca (paper account) executes buy/sell orders -- simulated money, no real trades.
- Google Gemini (gemini-3.5-flash) is the natural-language brain: it reads what you
  type, decides which tool to call (get price, get positions, buy, sell...), and
  replies in plain English once the tool result comes back.

Run it with:  python trading_agent.py
"""

from alpaca.trading.enums import OrderSide

from agents.market_agent import MarketAgent
from config import ALPACA_API_KEY, ALPACA_SECRET_KEY, GEMINI_API_KEY
from data.alpaca_client import (
    account_to_dict,
    get_trading_client,
    place_market_order,
    positions_to_list,
)
from llm.gemini_client import get_gemini_client, run_tool_loop

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

# Ask "y/n" before any order actually gets sent to Alpaca. Flip to False if you
# want the agent to place orders immediately without a confirmation prompt.
REQUIRE_CONFIRMATION = True

CONFIGURED = bool(ALPACA_API_KEY and ALPACA_SECRET_KEY and GEMINI_API_KEY)

# Keep the dashboard usable without credentials. API-backed actions return a
# clear configuration error until paper-trading credentials are supplied.
trading_client = get_trading_client()
market_agent = MarketAgent()
gemini_client = get_gemini_client()


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
    return account_to_dict(trading_client.get_account())


def get_positions():
    """List every stock currently held in the paper account, with qty and P&L."""
    if trading_client is None:
        return _configuration_error()
    return {"positions": positions_to_list(trading_client.get_all_positions())}


def get_stock_price(symbol: str):
    """Get the latest bid/ask quote for a stock ticker symbol."""
    if market_agent.client is None:
        return _configuration_error()
    symbol = symbol.upper()
    try:
        quote = market_agent.latest_quote(symbol)
        return {"symbol": symbol, "bid_price": quote.bid_price, "ask_price": quote.ask_price}
    except Exception as e:
        return {"status": "error", "error": str(e)}


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
    if trading_client is None:
        return _configuration_error()
    return place_market_order(trading_client, symbol, side, qty=qty, notional=notional)


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

    return run_tool_loop(
        gemini_client,
        user_text,
        previous_interaction_id,
        tool_impls=TOOL_IMPLS,
        tool_declarations=TOOL_DECLARATIONS,
        system_instruction=SYSTEM_INSTRUCTION,
        # Use the default is_error (checks both "error" and status=="error"): this
        # file's tool functions return a mix of {"error": ...} (get_stock_price) and
        # {"status": "error"/"not_configured", "error": ...} (everything else), and
        # the default catches all of those shapes.
    )
