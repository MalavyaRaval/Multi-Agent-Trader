from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MEMORY_DIR = BASE_DIR / "memory"
AGENTS_DIR = BASE_DIR / "agents"
INDICATORS_DIR = BASE_DIR / "indicators"
STRATEGIES_DIR = BASE_DIR / "strategies"

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MEMORY_DIR, exist_ok=True)

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

DEFAULT_SYMBOL = os.getenv("DEFAULT_SYMBOL", "AAPL")

# PHASES_PLAN.md section 4 / Phase 14 -- explicit market-data feed. The free
# Alpaca plan only has IEX; never silently assume SIP. Every Alpaca market
# data request should pass this explicitly rather than relying on an SDK
# default.
ALPACA_DATA_FEED = os.getenv("ALPACA_DATA_FEED", "iex").strip().lower() or "iex"

# Alpaca's documented Market Data API limit on the free "Basic" plan is 200
# requests/minute (Algo Trader Plus raises this to 10,000). Used only to
# self-track this process's own request rate for the diagnostics panel --
# not read from live response headers, since alpaca-py does not expose them.
ALPACA_DATA_RATE_LIMIT_PER_MIN = int(os.getenv("ALPACA_DATA_RATE_LIMIT_PER_MIN", "200"))
