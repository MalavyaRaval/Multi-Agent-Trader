# Phases Plan — Multi-Agent Trading System

> **Last updated:** 2026-07-31  
> This document tracks what has been built in each phase and what remains planned.

---

## Phase 0 — Existing Foundation (Before My Work)

**Status:** ✅ Complete (pre-existing)

**What was already built:**
- `trading_agent.py` — A working Gemini-powered chat agent that can buy/sell stocks via Alpaca paper trading
- `app.py` — Flask web server with a basic dashboard (chat + technical agent)
- `templates/index.html` — Dark-themed dashboard UI
- `agents/market_agent.py` — Full Alpaca data fetcher with caching and retry logic
- `agents/technical_agent.py` — Partially working; called `compute_*` functions but indicators only had `calculate_*` stubs
- `indicators/*.py` — All stubs (returned dummy values like `prices[-1]`)
- `data/` folder — Alpaca provider, cache, retry, models
- `config.py`, `requirements.txt`, `.env` support
- `main.py` — Console entry point that runs all agents sequentially

**What was broken/missing:**
- `market_data_agent.py` did **not exist** — `app.py` imported it and would crash
- 4 of 7 agents were **empty placeholders** (Fundamental, News, Risk, Execution, Portfolio)
- `indicators/*.py` functions were **stubs** (e.g., `calculate_macd` always returned zeros)
- No orchestrator — agents ran independently with no coordination
- No inter-agent communication
- No trade history persistence
- No autonomous trading loop
- `strategies/*.py` were all stubs returning `"hold"`

---

## Phase 1 — Fix Foundation + Build Orchestrator + Real Agents

**Status:** ✅ Complete

### Goals
1. Fix all broken imports and stub functions
2. Create the missing `market_data_agent.py`
3. Build a central `orchestrator.py` that coordinates all agents
4. Implement real logic for all 5 placeholder agents
5. Add real-time agent communication log to the dashboard
6. Update the web UI to support multi-agent analysis

### What was built

| File | What Changed |
|------|-------------|
| `market_data_agent.py` | **Created.** Chat-based wrapper around MarketAgent with Gemini-powered natural language queries |
| `orchestrator.py` | **Created.** Central coordinator with `MessageBus` (thread-safe pub/sub), `analyze_symbol()` pipeline, and autonomous loop support |
| `indicators/rsi.py` | Real pandas-based RSI with `compute_rsi()` + backward compat `calculate_rsi()` |
| `indicators/macd.py` | Real MACD with EWM + `compute_macd()` + `calculate_macd()` |
| `indicators/ema.py` | Real EMA with EWM + `compute_ema()` + `calculate_ema()` |
| `indicators/bollinger.py` | Real Bollinger Bands with rolling std + `compute_bollinger()` |
| `indicators/atr.py` | Real ATR with true range + `compute_atr()` |
| `indicators/volume.py` | Volume ratio + trend classification |
| `agents/fundamental_agent.py` | Real logic: fetches Finnhub company profile, scores PE/beta |
| `agents/news_agent.py` | Real logic: fetches Finnhub news, keyword-based sentiment |
| `agents/risk_agent.py` | Real logic: ATR-based volatility, RSI extreme warnings |
| `agents/execution_agent.py` | Real logic: combines all agent outputs into BUY/SELL/HOLD with confidence score. Can place Alpaca trades. |
| `agents/portfolio_agent.py` | Real logic: fetches account + positions from Alpaca |
| `app.py` | Added `/api/analyze`, `/api/messages`, `/api/account`, `/api/positions`, `/api/autonomous/start/stop`, `/api/execute` |
| `templates/index.html` | Added Multi-Agent Analysis tab, Agent Communication Log panel, autonomous controls, account/positions sidebar |

### Key Design Decisions
- `MessageBus` uses threading.Lock for thread-safe message logging
- Orchestrator singleton pattern via `get_orchestrator()` for Flask
- All indicators export both `compute_*` (pandas) and `calculate_*` (list) for flexibility
- Agents are **stateless per call** — no memory of previous analyses

---

## Phase 2 — Strategies + Auto-Trade + Trade History

**Status:** ✅ Complete

### Goals
1. Replace all 5 strategy stubs with real trading logic
2. Wire strategies into ExecutionAgent as "voters"
3. Enable auto-execution of paper trades when confidence is high
4. Add persistent trade history logging
5. Add Trade History tab to the dashboard

### What was built

| File | What Changed |
|------|-------------|
| `strategies/momentum.py` | Real momentum logic: price change %, volume confirmation, RSI/MACD alignment |
| `strategies/trend_following.py` | Real trend logic: EMA20 vs EMA50, Bollinger position, ATR dampening |
| `strategies/mean_reversion.py` | Real reversion logic: RSI extremes, Bollinger band position, volume spikes |
| `strategies/breakout.py` | Real breakout logic: large daily moves, volume surges, Bollinger squeeze |
| `strategies/swing.py` | Real swing logic: RSI zones, MACD cross, fundamentals, portfolio anti-churn |
| `agents/execution_agent.py` | **Major refactor.** Now runs all 5 strategies, combines votes with agent score (40/60 weighting). Added `maybe_auto_trade()` with confidence threshold. Added `place_order()` with TradeHistory logging. |
| `orchestrator.py` | Added `auto_execute` parameter. Autonomous loop now passes `auto_execute=True`. Auto-trade results published to MessageBus. |
| `memory/trade_history.py` | **Created.** JSON-backed persistent storage. Thread-safe. Records orders and analyses. |
| `app.py` | Added `/api/history` and `/api/history/stats` endpoints. Added `trade_history` instance. |
| `templates/index.html` | Added "Trade History" tab with table, stats bar, and refresh button. |
| `data/finnhub.py` | Fixed `FinnhubClient.__init__()` to accept optional `api_key` (falls back to env var). |
| `agents/fundamental_agent.py` | Fixed to call `FinnhubClient()` with no args and use `company_profile()` method. |

### Key Design Decisions
- **Strategy voting system:** Each strategy returns a vote (buy/sell/hold + confidence). Votes are aggregated into a net score.
- **Confidence threshold:** `AUTO_EXECUTE_CONFIDENCE=0.75` means agents only auto-trade when ≥75% confident.
- **Anti-churn:** Auto-trade won't buy if already long, won't sell if no position.
- **Default size:** `$500` notional per auto-trade (configurable).
- **TradeHistory** is JSON-file-backed for simplicity. Future phases may use SQLite.

---

## Phase 3 — Performance & Intelligence

**Status:** ✅ Complete

### Goals
1. **Backtesting module** — Test strategies on historical data to see how they would have performed
2. **Performance reporting** — Calculate actual P&L from Alpaca paper trades, not just order counts
3. **Watchlist / Screener Agent** — Automatically discover symbols worth analyzing (e.g., top movers, volume leaders)
4. **LLM Reflection** — Use Gemini to generate post-trade reflections ("Why did this trade win/lose?")

### What was built
- `backtesting/engine.py` — Runs strategy simulations over historical bars and produces a simple equity curve and trade log
- `backtesting/report.py` — Produces sharpe ratio, win rate, profit factor, drawdown, and return statistics
- `agents/screener_agent.py` — Screens a watchlist of symbols using momentum, volume, RSI, MACD, and trend filters
- `memory/reflections.py` — Adds a Gemini-backed reflection engine that can summarize trade reasoning and trade batches
- `app.py` — Exposes `/api/backtest`, `/api/screen`, and `/api/reflection`

---

## Phase 4 — Advanced Features

**Status:** ✅ Complete

### Goals
1. **Vector-based memory** — Store trade rationale and notes for semantic search
2. **Multi-timeframe analysis** — TechnicalAgent analyzes multiple timeframes and aggregates them into a single signal
3. **Position sizing algorithms** — Kelly criterion, risk-parity, volatility-targeting
4. **Scheduled reporting** — Daily/weekly summary of agent activity and performance
5. **Strategy ensemble optimization** — Learn optimal weights for strategy votes based on historical performance

### What was built
- `memory/vector_store.py` — Lightweight TF-IDF semantic search for trade history and notes
- `sizing/kelly.py` and `sizing/vol_target.py` — Position sizing helpers for dynamic trade sizing
- `indicators/multiframe.py` — Aggregates multiple timeframes into a unified bullish/bearish signal
- `reporting/daily_report.py` — Produces a simple daily performance summary from recent trades
- `app.py` — Exposes `/api/report/daily`, `/api/optimize`, `/api/weights`, and `/api/sizing`
- `optimization/ensemble.py` — Aggregates strategy votes with stored weights for a more adaptive ensemble

### Current maturity
- The system is now beyond a prototype and can support backtesting, candidate screening, dynamic sizing, and richer memory/search workflows.
- It remains a research and paper-trading assistant rather than a turnkey live-trading platform.

---

## Phase 5 — Live Trading Bridge (Future / Advanced)

**Status:** ⏳ Not Started — Requires explicit user confirmation

### Goals
1. **Live trading switch** — Option to route orders to Alpaca live account instead of paper
2. **Circuit breakers** — Auto-stop trading if daily loss exceeds threshold, market halts, etc.
3. **Broker diversity** — Support multiple brokers (Alpaca, Interactive Brokers, etc.)

### ⚠️ Safety Requirements Before Live Trading
- [ ] Comprehensive backtest on 1+ years of data
- [ ] Paper trading run for 30+ days with positive P&L
- [ ] Circuit breaker implementation
- [ ] Manual approval step before every live order
- [ ] Logging and alerting for all live trades

---

## Quick Reference: What's Working Right Now

| Feature | Status | How to Use |
|---------|--------|-----------|
| Chat with Trading Agent | ✅ | Dashboard → Chat tab → select "Trading Agent" |
| Chat with Market Data Agent | ✅ | Dashboard → Chat tab → select "Market Data Collector" |
| Technical Analysis | ✅ | Dashboard → Chat tab → select "Technical Agent" or Analysis tab |
| Multi-Agent Analysis | ✅ | Dashboard → Analysis tab → enter symbol → Run Analysis |
| Agent Communication Log | ✅ | Right panel of dashboard — auto-updates every 2s |
| Account/Positions View | ✅ | Left sidebar — auto-refreshes every 30s |
| Manual Trade Execution | ✅ | Analysis tab → Buy/Sell buttons |
| Autonomous Trading Loop | ✅ | Left sidebar → Start Loop (configurable symbols + interval) |
| Auto-execution on high confidence | ✅ | Enabled automatically in autonomous mode |
| Trade History | ✅ | Dashboard → Trade History tab |
| Paper trading only | ✅ | Hardcoded `paper=True` — no live money risk |

---

## Known Limitations

1. **News sentiment is still heuristic-based.** It uses keyword matching rather than deeper contextual understanding.
2. **Fundamental data requires Finnhub API key.** Without it, those agents skip gracefully.
3. **Trade history is JSON-file-backed.** Good for now, but may need SQLite or a proper database for scale.
4. **Backtesting is still lightweight.** It does not yet include slippage, commissions, or multi-order execution realism.
5. **Strategies use fixed rules, not ML.** They do not learn from past performance automatically.
6. **Position sizing is dynamic but simple.** It uses volatility targeting and Kelly-style heuristics, but still lacks full portfolio-level risk management.
7. **Reflections depend on Gemini availability.** If the API is unavailable, the system falls back to a simple summary.
