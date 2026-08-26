# Paper Trading Multi-Agent Platform

This project is now a working multi-agent paper-trading research platform built in Python. It combines:

- a Flask-based web dashboard
- a multi-agent orchestration layer
- real technical, fundamental, news, risk, and portfolio analysis
- a strategy voting system with auto-trade support
- backtesting, screening, daily reporting, and semantic memory features

It is designed for experimentation and learning rather than guaranteed profits. The system runs entirely in paper-trading mode by default, so it is safe to explore without risking real money.

## What the system does

At a high level, the app can:

- analyze a symbol using multiple AI-style agents
- compute technical indicators and trading signals
- combine several strategy opinions into a single buy/sell/hold decision
- optionally place paper trades through Alpaca
- store every decision and order in persistent trade history
- backtest strategies on historical data
- screen a watchlist for promising symbols
- generate reflections and simple daily summaries
- search through stored trade notes and history semantically

## Project structure

```text
.
├── agents/
├── backtesting/
├── data/
├── indicators/
├── memory/
├── optimization/
├── reporting/
├── sizing/
├── strategies/
├── templates/
├── app.py
├── config.py
├── main.py
├── market_data_agent.py
├── orchestrator.py
├── requirements.txt
├── trading_agent.py
└── Readme.md
```

## Main modules

- [app.py](app.py) — Flask app and REST API
- [orchestrator.py](orchestrator.py) — coordinates agents and publishes inter-agent messages
- [agents/](agents) — market, technical, fundamental, news, risk, execution, portfolio, and screener modules
- [strategies/](strategies) — five strategy voters for momentum, trend, mean reversion, breakout, and swing
- [backtesting/](backtesting) — historical strategy simulation and reporting
- [memory/](memory) — trade history, reflections, and semantic memory
- [sizing/](sizing) — Kelly and volatility-targeting position sizing helpers
- [reporting/](reporting) — daily reporting summaries

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file and add:

```env
ALPACA_API_KEY=your_paper_key
ALPACA_SECRET_KEY=your_paper_secret
GEMINI_API_KEY=your_gemini_key
FINNHUB_API_KEY=for market data and news
AUTO_EXECUTE_CONFIDENCE=0.75
AUTO_TRADE_NOTIONAL=500
```

### 3. Run the dashboard

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:5000/
```

### 4. Run the console entry point

```bash
python main.py
```

## How it works

1. The orchestrator starts a symbol analysis flow.
2. Market and technical agents collect data and indicators.
3. Fundamental, news, risk, and portfolio agents add context.
4. Strategies vote independently.
5. The execution agent merges the signals, calculates confidence, and may place a paper trade.
6. Every action is logged in the trade ledger for later review.

## Key features

- Multi-agent analysis pipeline
- Real-time communication log in the dashboard
- Autonomous trading loop
- Paper-trading execution via Alpaca
- Trade history persistence
- Backtesting and performance reporting
- Screener for candidate symbols
- Daily report generation
- Lightweight semantic search over trade memory

## Important notes

- This is paper trading only. The project is intentionally safe by default.
- Some features gracefully degrade if API keys are missing.
- The strategies and agents are heuristic-based tools for research, not guaranteed profit generators.

## Suggested next upgrades

If you want to push this project further, the best next steps are:

- add slippage and commissions to backtests
- add daily loss and drawdown safeguards for autonomous mode
- connect richer data sources like macro and SEC data
- improve the UI with charts and richer trade explanations
- replace the lightweight memory layer with a more advanced embedding-based store

## Troubleshooting

- `Could not connect to Alpaca`: double check you copied the **paper** keys into `.env`.
- `Gemini API error`: verify the Gemini API key is active and the environment has internet access.
- `No data returned`: market data may be unavailable for some symbols or timeframes, and the system will fall back gracefully.