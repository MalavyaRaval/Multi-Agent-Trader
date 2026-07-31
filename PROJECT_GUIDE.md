# Project Guide — Multi-Agent Paper Trading System

> **Last updated:** 2026-07-30  
> **Project root:** `C:\Users\malav\OneDrive_San Francisco State University\Desktop\claude alpaca`

---

## Table of Contents

1. [High-Level Architecture](#high-level-architecture)
2. [Folder-by-Folder Breakdown](#folder-by-folder-breakdown)
3. [File-by-File Reference](#file-by-file-reference)
4. [Agent Interactions (The Pipeline)](#agent-interactions-the-pipeline)
5. [Data Flow Diagram](#data-flow-diagram)
6. [API Endpoints](#api-endpoints)
7. [Environment Variables](#environment-variables)
8. [How to Run](#how-to-run)

---

## High-Level Architecture

This is a **multi-agent AI trading platform** that uses **Alpaca paper trading** (simulated money, zero real risk). It consists of:

- **7 specialized agents** that each analyze a different dimension of a stock
- **5 trading strategies** that vote on buy/sell/hold decisions
- **1 orchestrator** that coordinates the agents, logs their communication, and can auto-execute trades
- **1 web dashboard** where you chat with agents, trigger analyses, and watch agents communicate in real-time
- **1 standalone trading agent** for direct natural-language buy/sell commands

```
┌─────────────────────────────────────────────────────────────────────┐
│                          WEB DASHBOARD                               │
│  (Flask + HTML/JS — tabs: Chat, Analysis, History, Comm Log)        │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR                                 │
│  Coordinates 7 agents → runs 5 strategies → decides → optionally    │
│  auto-trades. Logs everything to MessageBus + TradeHistory.          │
└─────────────────────────────────────────────────────────────────────┘
                                │
    ┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
    ▼          ▼          ▼          ▼          ▼          ▼          ▼
┌───────┐ ┌───────┐ ┌─────────┐ ┌──────┐ ┌───────┐ ┌─────────┐ ┌─────────┐
│Market │ │Techni-│ │Fundamen-│ │ News │ │ Risk  │ │Execution│ │Portfolio│
│ Agent │ │ cal   │ │  tal    │ │ Agent│ │ Agent │ │  Agent  │ │  Agent  │
└───────┘ └───────┘ └─────────┘ └──────┘ └───────┘ └─────────┘ └─────────┘
    │          │          │          │          │          │          │
    ▼          ▼          ▼          ▼          ▼          ▼          ▼
Alpaca   Indicators  Finnhub   Finnhub   Market+    Alpaca    Alpaca
Market   (RSI,MACD,  (PE,EPS,  News API  Technical  (trades)  (positions)
Data     EMA,etc.)   Beta)                         + Strategies
```

---

## Folder-by-Folder Breakdown

### `agents/` — The 7 Analysis Agents
Each agent is a self-contained class with an `analyze(symbol)` method. They are **stateless** per call and return a dictionary of findings.

### `data/` — Data Providers & Utilities
Contains everything that talks to external APIs (Alpaca, Finnhub) plus caching, retry logic, and data models.

### `indicators/` — Technical Indicators
Pure math functions that operate on pandas Series or lists of prices. Used exclusively by the TechnicalAgent.

### `memory/` — Persistence Layer
JSON-backed storage for trade history. Also has placeholder reflection and vector store modules for future AI memory features.

### `strategies/` — Trading Strategies
Each strategy evaluates the full analysis context and casts a "vote" (buy/sell/hold with confidence). Used by the ExecutionAgent.

### `templates/` — Web UI
Single `index.html` with all CSS and JS inline. Dark-themed dashboard with tabs for Chat, Multi-Agent Analysis, and Trade History.

### Root Files
Entry points and configuration for the entire system.

---

## File-by-File Reference

### Root-Level Files

#### `app.py` — **Flask Web Server (Main Entry Point)**
- **What it does:** Hosts the web dashboard and exposes all REST API endpoints.
- **Key components:**
  - `technical_agent` — handles single-agent chat queries
  - `portfolio_agent` — fetches live account info for the sidebar
  - `orchestrator` — singleton from `get_orchestrator()`
  - `trade_history` — persists trade/analysis records
- **Routes:**
  - `GET /` — renders dashboard
  - `POST /chat` — chat with TradingAgent, MarketDataAgent, or TechnicalAgent
  - `POST /api/analyze` — trigger full multi-agent pipeline
  - `GET /api/messages?since=N` — poll agent communication log
  - `GET /api/account` — live account snapshot (cash, equity, buying power)
  - `GET /api/positions` — all open positions with unrealized P&L
  - `POST /api/autonomous/start` — start background trading loop
  - `POST /api/autonomous/stop` — stop background loop
  - `POST /api/execute` — manual trade execution
  - `GET /api/history?limit=N` — trade/analysis history
  - `GET /api/history/stats` — summary counts

#### `trading_agent.py` — **Standalone Natural-Language Trading Agent**
- **What it does:** A chat-based agent powered by Google Gemini that talks to Alpaca. You text it things like "buy 10 shares of AAPL" and it executes.
- **How it works:**
  1. Takes user text → sends to Gemini with tool declarations
  2. Gemini decides which tool to call (get price, buy, sell, get positions)
  3. Code executes the tool → sends result back to Gemini
  4. Gemini replies in plain English
- **Tools available:** `get_account_info`, `get_positions`, `get_stock_price`, `buy_stock`, `sell_stock`
- **Safety:** `paper=True` on Alpaca client. Never touches live money.
- **Used by:** Chat tab in dashboard when agent_id = `"trading_agent"`

#### `market_data_agent.py` — **Standalone Market Data Chat Agent**
- **What it does:** Same pattern as `trading_agent.py`, but for market data queries.
- **Tools:** `get_stock_price`, `get_stock_snapshot`, `get_historical_bars`
- **Used by:** Chat tab when agent_id = `"market_data_collector"`

#### `orchestrator.py` — **The Conductor**
- **What it does:** Coordinates all 7 agents into a single analysis pipeline. Can run manually or on an autonomous schedule.
- **Key classes:**
  - `MessageBus` — thread-safe pub/sub that logs every inter-agent message with timestamps. Powers the real-time Communication Log in the UI.
  - `Orchestrator` — the coordinator
- **`analyze_symbol(symbol, auto_execute=False)` pipeline:**
  1. MarketAgent fetches snapshot (price, bars, metrics)
  2. TechnicalAgent computes RSI, MACD, EMA, Bollinger, ATR, volume
  3. FundamentalAgent fetches company profile from Finnhub
  4. NewsAgent fetches news + keyword sentiment
  5. RiskAgent evaluates volatility (ATR) and RSI extremes
  6. PortfolioAgent checks if you already own the stock
  7. ExecutionAgent combines all inputs + runs 5 strategies → final decision
  8. If `auto_execute=True` and confidence ≥ threshold → places real paper trade
- **Autonomous loop:** `_autonomous_loop()` runs on a background thread, analyzing each symbol every N seconds.

#### `main.py` — **Console Entry Point (No Web UI)**
- **What it does:** Simple CLI that instantiates all agents and prints their analyses as JSON.
- **Usage:** `python main.py` → type a symbol → see raw agent outputs.
- **Useful for:** Debugging agent outputs without the web server.

#### `config.py` — **Central Configuration**
- Defines directory paths (`BASE_DIR`, `DATA_DIR`, `MEMORY_DIR`, etc.)
- Loads API keys from environment variables:
  - `ALPACA_API_KEY` / `ALPACA_SECRET_KEY`
  - `GEMINI_API_KEY`
  - `FINNHUB_API_KEY`
- `DEFAULT_SYMBOL = "AAPL"`

#### `requirements.txt` — Python dependencies
- `google-genai` — Gemini LLM
- `alpaca-py` — Alpaca trading + market data
- `flask` — web server
- `pandas`, `numpy` — data processing
- `requests`, `python-dotenv`

---

### `agents/` — The 7 Agents

#### `agents/market_agent.py` — **Data Fetcher**
- **Responsibility:** Fetches raw market data from Alpaca. No AI decisions.
- **Key methods:**
  - `snapshot(symbol, timeframe, days)` → `MarketSnapshot` with bars, quote, trade, computed metrics
  - `snapshot_multi_timeframe()` → snapshots across 1m, 5m, 15m, 1h, 1d
  - `latest_quote()`, `latest_trade()`, `historical_bars()`
- **Metrics computed:** change %, relative volume, VWAP, spread, gap %
- **Caching:** Built-in TTL cache (default 60s) to avoid redundant API calls
- **SIP handling:** Gracefully handles Alpaca SIP subscription errors with warnings
- **Output:** `MarketSnapshot` dataclass (also defined in `data/models.py`)

#### `agents/technical_agent.py` — **Chart Analyst**
- **Responsibility:** Computes technical indicators from historical price data.
- **How it works:** Calls `MarketAgent.snapshot()` → gets `bars` DataFrame → runs indicators.
- **Indicators computed:**
  - RSI(14)
  - MACD + signal + histogram
  - EMA(20), EMA(50)
  - Bollinger Bands (upper, lower, mid)
  - ATR(14)
  - Volume ratio + volume trend (strong_buy/buy/neutral/sell/strong_sell)
- **Output:** `{"status": "technical analysis ready", "symbol": "AAPL", "signals": {...}}`

#### `agents/fundamental_agent.py` — **Company Analyst**
- **Responsibility:** Evaluates company fundamentals via Finnhub.
- **Data fetched:** Company profile → name, industry, sector, market cap, PE ratio, EPS, beta, dividend yield
- **Scoring:**
  - PE < 15 → +1 (value)
  - PE > 40 → -1 (overvalued)
  - Beta commentary (high = volatile, low = defensive)
- **Output:** `{"symbol": "AAPL", "status": "...", "data": {"company": {...}}, "score": N, "reasons": [...]}`
- **Graceful degradation:** Works fine without Finnhub API key (just skips company data)

#### `agents/news_agent.py` — **Sentiment Scanner**
- **Responsibility:** Fetches news articles and estimates sentiment.
- **Data source:** Finnhub company-news API (last 7 days)
- **Sentiment method:** Keyword counting
  - Positive: beat, strong, growth, rise, rally, gain, bull, upgrade, outperform
  - Negative: miss, weak, drop, fall, crash, bear, downgrade, underperform, loss
- **Output:** `{"symbol": "AAPL", "articles": [...], "sentiment": "positive"|"negative"|"neutral", "sentiment_score": N}`
- **Graceful degradation:** Skips if no Finnhub API key

#### `agents/risk_agent.py` — **Risk Evaluator**
- **Responsibility:** Assesses how risky a trade would be.
- **Checks:**
  - ATR(14) as % of price → < 2.5% = low, 2.5-5% = medium, > 5% = high
  - RSI extremes (> 75 overbought warning, < 25 oversold warning)
- **Output:** `{"risk_level": "low"|"medium"|"high", "checks": {"atr_percent": X, ...}}`

#### `agents/execution_agent.py` — **The Decision Maker**
- **Responsibility:** Combines ALL agent outputs + strategy votes into a final BUY/SELL/HOLD decision. Can place real trades.
- **How the decision works:**
  1. Runs all 5 strategies → each returns a vote (decision + confidence)
  2. Computes agent-based score from technical/fundamental/news/risk/portfolio signals
  3. **Combined score** = (agent_score × 0.6) + (strategy_score × 1.5)
  4. Thresholds: score > 1.5 → BUY, score < -1.5 → SELL, else HOLD
  5. Confidence = |score| / 4.0 (capped at 1.0)
- **Auto-trade:** `maybe_auto_trade()` checks:
  - Confidence ≥ `AUTO_EXECUTE_CONFIDENCE` (default 0.75, from `.env`)
  - Anti-churn: won't buy if already long, won't sell if no position
  - Default size: `$500` notional (configurable via `AUTO_TRADE_NOTIONAL`)
- **Logging:** Every analysis and every order is logged to `TradeHistory`
- **Output:** `{"action": "buy"|"sell"|"hold", "confidence": 0.0-1.0, "reason": "...", "raw_score": N, "strategy_votes": [...]}`

#### `agents/portfolio_agent.py` — **Portfolio Tracker**
- **Responsibility:** Reports current Alpaca paper account state.
- **Data fetched:**
  - Account: cash, buying power, portfolio value, equity
  - Position for requested symbol (qty, avg entry, current price, unrealized P&L)
  - ALL positions (for the sidebar positions table)
- **Output:** `{"account": {...}, "position": {...}, "all_positions": [...]}`

---

### `strategies/` — The 5 Strategy Voters

Each strategy receives the full `context` dict (technical, fundamental, news, risk, portfolio, market) and returns a vote.

| Strategy | Core Logic | Key Signals |
|----------|-----------|-------------|
| **Momentum** | `strategies/momentum.py` | Price change %, volume confirmation, RSI alignment, MACD direction |
| **Trend Following** | `strategies/trend_following.py` | EMA20 vs EMA50, trend distance, Bollinger position, volume |
| **Mean Reversion** | `strategies/mean_reversion.py` | RSI extremes, Bollinger band position, MACD histogram reversal |
| **Breakout** | `strategies/breakout.py` | Large daily moves (>4%), massive volume surges (>2x), Bollinger squeeze |
| **Swing** | `strategies/swing.py` | RSI swing zones (30-45, 55-70), MACD cross, fundamentals, portfolio anti-churn |

**How votes are aggregated:** Positive votes add confidence, negative votes subtract. The net score feeds into ExecutionAgent's combined score.

---

### `indicators/` — Math Utilities

| File | Function | What it computes |
|------|----------|-----------------|
| `rsi.py` | `compute_rsi(series, period=14)` | Wilder-style RSI on pandas Series |
| `macd.py` | `compute_macd(series, fast=12, slow=26, signal=9)` | MACD line, signal line, histogram |
| `ema.py` | `compute_ema(series, period=20)` | Exponential moving average |
| `bollinger.py` | `compute_bollinger(series, period=20, std=2)` | Upper, lower, middle bands |
| `atr.py` | `compute_atr(high, low, close, period=14)` | Average True Range |
| `volume.py` | `compute_volume_signals(volume, close)` | Volume ratio + trend classification |

Each file also exports a `calculate_*` variant for backward compatibility with list-based callers.

---

### `data/` — Data Layer

#### `data/finnhub.py` — Finnhub API Client
- Methods: `company_profile()`, `basic_financials()`, `news()`, `quote()`
- Auto-injects API token. Gracefully returns `{"error": ...}` if no key.

#### `data/providers/alpaca.py` — `AlpacaMarketDataProvider`
- Production-grade Alpaca data provider with caching, retry logic, SIP error handling.
- Methods: `latest_quote()`, `latest_trade()`, `historical_bars()`, `snapshot()`, `snapshot_multi_timeframe()`

#### `data/providers/base.py` — Abstract Base Class
- `MarketDataProvider` ABC defining the interface for any data provider.

#### `data/models.py` — Data Classes
- `MarketQuote`, `MarketTrade`, `MarketSnapshot` — structured containers for market data.

#### `data/cache.py` — Simple TTL Cache
- In-memory key-value cache with time-based expiration. Used by Alpaca provider.

#### `data/retry.py` — Retry Decorator
- `@retry(max_retries=3, delay=1.0)` — exponential backoff for API calls.

#### Other `data/` files
- `alpaca_data.py` — Thin wrapper around Alpaca quote API (legacy)
- `sec.py`, `economic_calendar.py`, `validation.py` — Placeholders for future SEC filings and macro data

---

### `memory/` — Persistence

#### `memory/trade_history.py` — **Trade & Analysis Ledger**
- **What it does:** JSON-file-backed persistent storage for every order placed and every analysis run.
- **File location:** `memory/trade_history.json`
- **Methods:**
  - `record_order(...)` — logs a placed trade
  - `record_analysis(...)` — logs an analysis decision
  - `get_all(limit)` — newest-first history
  - `get_stats()` — counts of orders, buys, sells, analyses
- **Thread-safe:** Uses `threading.Lock()` for concurrent access.

#### `memory/reflections.py` — Placeholder
- Simple in-memory note taker. Future: LLM-generated post-trade reflections.

#### `memory/vector_store.py` — Placeholder
- Simple keyword search over documents. Future: embedding-based semantic search for news/articles.

---

### `templates/index.html` — The Dashboard

A single-page dark-themed web app with:

| Section | Description |
|---------|-------------|
| **Sidebar** | Live account snapshot (cash, portfolio, buying power, equity), positions table, autonomous trading controls |
| **Chat Tab** | Talk to Trading Agent, Market Data Agent, or Technical Agent |
| **Multi-Agent Analysis Tab** | Enter a symbol → click Run Analysis → see all 6 agent cards + Execution decision + Buy/Sell buttons |
| **Trade History Tab** | Table of all past orders and analyses with stats (total orders, buy/sell counts) |
| **Agent Communication Log** (right panel) | Real-time stream of every message agents send to each other, color-coded by sender |

**Auto-refresh:** Account/positions every 30s. Communication log polls every 2s.

---

## Agent Interactions (The Pipeline)

When you trigger an analysis (or the autonomous loop does), here's exactly what happens:

```
Step 1: ORCHESTRATOR → MARKET_AGENT
        "Fetch data for AAPL"
        ← Returns: MarketSnapshot (price, bars, volume, metrics)

Step 2: ORCHESTRATOR → TECHNICAL_AGENT (parallel-ready)
        ← Returns: RSI, MACD, EMA, Bollinger, ATR, volume signals

Step 3: ORCHESTRATOR → FUNDAMENTAL_AGENT
        ← Returns: PE, EPS, market cap, beta, score

Step 4: ORCHESTRATOR → NEWS_AGENT
        ← Returns: sentiment (+/-/neutral), article headlines

Step 5: ORCHESTRATOR → RISK_AGENT
        ← Returns: risk level (low/medium/high), ATR%, warnings

Step 6: ORCHESTRATOR → PORTFOLIO_AGENT
        ← Returns: cash, positions, unrealized P&L

Step 7: ORCHESTRATOR → EXECUTION_AGENT
        ExecutionAgent internally:
          a) Runs MomentumStrategy → vote
          b) Runs TrendFollowingStrategy → vote
          c) Runs MeanReversionStrategy → vote
          d) Runs BreakoutStrategy → vote
          e) Runs SwingStrategy → vote
          f) Computes combined score
        ← Returns: action (buy/sell/hold), confidence, reason, raw_score

Step 8: ORCHESTRATOR (if auto_execute=True)
        → EXECUTION_AGENT.maybe_auto_trade()
        If confidence ≥ threshold:
          → Places Alpaca paper order
          → Logs to TradeHistory
          → Publishes to MessageBus: "AUTO-TRADE EXECUTED"
```

Every step publishes messages to the `MessageBus`, which the dashboard polls every 2 seconds to display in the Communication Log.

---

## Data Flow Diagram

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Alpaca    │────▶│ MarketAgent │────▶│TechnicalAgent│
│   API       │     │             │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
                                              │
┌─────────────┐     ┌─────────────┐     ┌────▼────────┐
│  Finnhub    │────▶│Fundamental  │────▶│             │
│   API       │     │   Agent     │     │             │
└─────────────┘     └─────────────┘     │  Execution  │
                                        │   Agent     │
┌─────────────┐     ┌─────────────┐     │  (combines  │
│  Finnhub    │────▶│  NewsAgent  │────▶│   all +     │
│  News API   │     │             │     │ strategies) │
└─────────────┘     └─────────────┘     └────┬────────┘
                                             │
┌─────────────┐     ┌─────────────┐     ┌────▼────────┐
│   Alpaca    │────▶│Portfolio/   │────▶│  Alpaca     │
│  Trading    │     │  RiskAgent  │     │  (order)    │
│   API       │     │             │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
                                             │
                                             ▼
                                    ┌─────────────────┐
                                    │  TradeHistory   │
                                    │ (JSON file)     │
                                    └─────────────────┘
                                             │
                                             ▼
                                    ┌─────────────────┐
                                    │   Dashboard     │
                                    │ (Flask + HTML)  │
                                    └─────────────────┘
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard HTML |
| `/chat` | POST | Chat with an agent (`message`, `agent_id`) |
| `/api/analyze` | POST | Run full pipeline (`symbol`) |
| `/api/messages` | GET | Poll comm log (`since` index) |
| `/api/account` | GET | Account snapshot |
| `/api/positions` | GET | All positions |
| `/api/autonomous/start` | POST | Start loop (`symbols`, `interval_seconds`) |
| `/api/autonomous/stop` | POST | Stop loop |
| `/api/execute` | POST | Manual trade (`symbol`, `side`, `qty`\|`notional`) |
| `/api/history` | GET | History entries (`limit`) |
| `/api/history/stats` | GET | History stats |

---

## Environment Variables

Create a `.env` file in the project root:

```env
# Required
ALPACA_API_KEY=your_paper_key
ALPACA_SECRET_KEY=your_paper_secret
GEMINI_API_KEY=your_gemini_key

# Optional
FINNHUB_API_KEY=your_finnhub_key

# Auto-trading tuning
AUTO_EXECUTE_CONFIDENCE=0.75    # 0.0 to 1.0
AUTO_TRADE_NOTIONAL=500         # dollars per auto-trade
DEFAULT_SYMBOL=AAPL
```

---

## How to Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure .env (see above)

# 3. Run the web dashboard
python app.py
# → Open http://127.0.0.1:5000/

# 4. Or run the console version
python main.py
```

---

## Notes & Warnings

- **This is PAPER TRADING only.** The `paper=True` flag on Alpaca clients ensures no real money is at risk. Never change this to `paper=False`.
- **Finnhub API key is optional.** Without it, FundamentalAgent and NewsAgent will gracefully skip their data sources.
- **Auto-trading is opt-in.** You must click "Start Loop" in the dashboard or call the API to enable autonomous trades.
- **Strategies do not guarantee profits.** They are rule-based heuristics, not financial advice.
