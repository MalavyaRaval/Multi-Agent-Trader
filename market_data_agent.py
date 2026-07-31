"""
market_data_agent.py

Chat-based wrapper around the MarketAgent so it can be used from the web UI
just like the trading_agent. It responds to natural-language queries about
market data with structured snapshots.
"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from google import genai

from agents.market_agent import MarketAgent

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-3.1-flash-lite"
MAX_TOOL_ROUNDS = 8

market_agent = MarketAgent()
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

SYSTEM_INSTRUCTION = """You are a market data assistant. You help users get stock quotes,
historical prices, and market snapshots. Use the provided tools to fetch real data.
Never make up numbers. Keep replies concise.
"""


def get_stock_price(symbol: str):
    symbol = symbol.upper()
    try:
        quote = market_agent.latest_quote(symbol)
        trade = market_agent.latest_trade(symbol)
        return {
            "symbol": symbol,
            "bid": quote.bid_price,
            "ask": quote.ask_price,
            "last_price": trade.price,
            "last_size": trade.size,
        }
    except Exception as e:
        return {"error": str(e)}


def get_stock_snapshot(symbol: str, timeframe: str = "1d", days: int = 200):
    symbol = symbol.upper()
    try:
        snap = market_agent.snapshot(symbol, timeframe=timeframe, days=days)
        metrics = snap.metrics or {}
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "last_price": snap.trade.price if snap.trade else None,
            "bid": snap.quote.bid_price if snap.quote else None,
            "ask": snap.quote.ask_price if snap.quote else None,
            "change_percent": metrics.get("change_percent"),
            "relative_volume": metrics.get("relative_volume"),
            "vwap": metrics.get("vwap"),
            "bars_count": len(snap.bars),
        }
    except Exception as e:
        return {"error": str(e)}


def get_historical_bars(symbol: str, timeframe: str = "1d", days: int = 30):
    symbol = symbol.upper()
    try:
        bars = market_agent.historical_bars(symbol, timeframe=timeframe, days=days)
        records = bars.to_dict(orient="records")
        # Return only last 10 rows to keep token count low
        return {"symbol": symbol, "timeframe": timeframe, "rows": len(records), "last_10": records[-10:]}
    except Exception as e:
        return {"error": str(e)}


TOOL_IMPLS = {
    "get_stock_price": get_stock_price,
    "get_stock_snapshot": get_stock_snapshot,
    "get_historical_bars": get_historical_bars,
}

TOOL_DECLARATIONS = [
    {
        "type": "function",
        "name": "get_stock_price",
        "description": "Get the latest bid/ask quote and last trade price for a stock ticker.",
        "parameters": {
            "type": "object",
            "properties": {"symbol": {"type": "string", "description": "Ticker symbol, e.g. AAPL"}},
            "required": ["symbol"],
        },
    },
    {
        "type": "function",
        "name": "get_stock_snapshot",
        "description": "Get a comprehensive market snapshot including price, volume metrics, and VWAP.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "timeframe": {"type": "string", "description": "e.g. 1d, 1h, 15m"},
                "days": {"type": "integer", "description": "Number of days of history"},
            },
            "required": ["symbol"],
        },
    },
    {
        "type": "function",
        "name": "get_historical_bars",
        "description": "Get historical OHLCV bars for a stock.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "timeframe": {"type": "string", "description": "e.g. 1d, 1h, 15m"},
                "days": {"type": "integer"},
            },
            "required": ["symbol"],
        },
    },
]


def run_turn(user_text: str, previous_interaction_id):
    if gemini_client is None:
        return "(Gemini API key not configured.)", previous_interaction_id

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
                    is_error = isinstance(result, dict) and result.get("error")
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
            return f"(Gemini API error: {e})", interaction.id

    return (interaction.output_text or "(no response text)"), interaction.id
