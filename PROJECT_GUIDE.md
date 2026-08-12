# Project Guide — Multi-Agent Paper Trading System

> **Last updated:** 2026-08-11  
> **Project root:** C:\Users\malav\OneDrive_San Francisco State University\Desktop\claude alpaca

---

## Table of Contents

1. [High-Level Architecture](#high-level-architecture)
2. [How the System Works](#how-the-system-works)
3. [Folder-by-Folder Breakdown](#folder-by-folder-breakdown)
4. [File-by-File Reference](#file-by-file-reference)
5. [Agent Interactions & Telemetry Pipeline](#agent-interactions--telemetry-pipeline)
6. [Data Flow Diagram](#data-flow-diagram)
7. [API Endpoints Reference](#api-endpoints-reference)
8. [Environment Variables](#environment-variables)
9. [How to Run](#how-to-run)
10. [Recent Major Improvements](#recent-major-improvements)

---

## High-Level Architecture

This is an advanced **multi-agent AI trading platform** powered by **Alpaca paper trading** (simulated money, zero real risk). It combines **7 specialized AI agents**, **5 trading strategies**, **Gemini LLM reasoning synthesis**, **interactive Chart.js financial charts**, and a **real-time Slack/Discord-style Inter-Agent Group Chat**.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                 WEB DASHBOARD (Flask + JS)                              │
│  Tabs: Multi-Agent Workspace │ Inter-Agent Group Chat │ Agent Chat │ Screener │          │
│        Backtest Lab │ AI Reflections & Reports │ Vector Search │ Trade History          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                     ORCHESTRATOR                                        │
│  Coordinates 7 agents → runs 5 strategy voters → calculates score → generates reasoning  │
│  synthesizes Gemini LLM thesis → logs to MessageBus (with session IDs & telemetry)      │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                             │
    ┌──────────┬──────────┬──────────┬───────┴──┬──────────┬──────────┬──────────┐
    ▼          ▼          ▼          ▼          ▼          ▼          ▼          ▼
┌───────┐ ┌───────┐ ┌─────────┐ ┌──────┐ ┌───────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│Market │ │Techni-│ │Fundamen-│ │ News │ │ Risk  │ │Execution│ │Portfolio│ │Reasoning│
│ Agent │ │ cal   │ │  tal    │ │ Agent│ │ Agent │ │  Agent  │ │  Agent  │ │ Engine  │
└───────┘ └───────┘ └─────────┘ └──────┘ └───────┘ └─────────┘ └─────────┘ └─────────┘
    │          │          │          │          │          │          │          │
    ▼          ▼          ▼          ▼          ▼          ▼          ▼          ▼
Alpaca   Indicators  Finnhub   Finnhub   Market+    Alpaca    Alpaca     Gemini LLM
Market   (RSI,MACD,  (PE,EPS,  News API  Technical  (trades)  (positions) Rationale
Data     EMA,etc.)   Beta)                         + Strategies           Synthesis
```

---

## How the System Works

1. **Analysis Trigger:** The user requests an analysis or the autonomous trading loop runs (every 180 seconds).
2. **Session Telemetry:** The Orchestrator assigns a unique `session_id` and emits session start events to the `MessageBus`.
3. **Data & Technical Collection:** The `MarketAgent` fetches OHLCV price bars and quotes from Alpaca. `TechnicalAgent` computes RSI, MACD, EMA20/50, Bollinger Bands, ATR, and volume trends across timeframes.
4. **Fundamental & News Context:** `FundamentalAgent` and `NewsAgent` query Finnhub profile/news APIs. If API keys are missing, they emit diagnostic warnings and degrade gracefully to neutral.
5. **Risk & Portfolio Evaluation:** `RiskAgent` computes ATR volatility % and RSI extremes. `PortfolioAgent` checks current position sizing and unrealized P&L to avoid churn.
6. **Strategy Ensemble Voting:** 5 independent strategies (`Momentum`, `TrendFollowing`, `MeanReversion`, `Breakout`, `Swing`) evaluate the setup and issue votes (BUY/SELL/HOLD + confidence).
7. **Weighted Execution Score:** `ExecutionAgent` weights agent signals (60%) and strategy consensus (40%), adjusted by risk factors.
8. **Detailed AI Reasoning Synthesis:** `ReasoningEngine` invokes Google Gemini LLM to generate an Executive Summary, Bullish Catalysts, Bearish Threats, and a 6-step mathematical reasoning breakdown.
9. **Interactive Group Chat & Charts:** Full telemetry, API diagnostics, and dialogue monologues stream live into the dashboard's Inter-Agent Group Chat and price action charts.

---

## Folder-by-Folder Breakdown

- **`agents/`** — 7 specialized analysis agents plus Screener and Execution agents.
- **`strategies/`** — 5 rule-based strategy voters (`momentum.py`, `trend_following.py`, `mean_reversion.py`, `breakout.py`, `swing.py`).
- **`indicators/`** — Pure math indicator functions (RSI, MACD, EMA, Bollinger, ATR, Volume, Multi-timeframe).
- **`memory/`** — Persistence layer (`trade_history.py`), LLM reflections (`reflections.py`), TF-IDF vector store (`vector_store.py`), and AI reasoning synthesis (`reasoning.py`).
- **`sizing/`** — Dynamic position sizing algorithms (Volatility targeting, Risk parity, Half Kelly criterion).
- **`optimization/`** — Ensemble strategy weight optimization (`ensemble.py`).
- **`reporting/`** — Summary report builders (`daily_report.py`).
- **`backtesting/`** — Historical simulation engine and report generator (`engine.py`, `report.py`).
- **`templates/`** — Single-page dashboard UI (`index.html`) featuring Chart.js charts, Group Chat workspace, API diagnostic bar, and educational modals.

---

## File-by-File Reference

### Key Entry Points & Core Components

- **`app.py`**: Flask Web Server exposing REST API endpoints for analysis, chart data, diagnostics, inter-agent messages, sessions, backtests, screener, sizing, and reflections.
- **`orchestrator.py`**: Central pub/sub coordinator featuring `MessageBus` with session filtering, `analyze_symbol()` pipeline, and autonomous background loop.
- **`memory/reasoning.py`**: `ReasoningEngine` powered by Gemini LLM that synthesizes structured trade rationale, bullish/bearish thesis, and step-by-step math.
- **`agents/execution_agent.py`**: Aggregates 5 strategy votes and 6 agent outputs into final trade decisions, attaches AI reasoning, and executes paper orders via Alpaca.

---

## API Endpoints Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Renders Dashboard UI |
| `/chat` | POST | Direct natural language chat with an agent |
| `/api/analyze` | POST | Trigger full multi-agent pipeline (`symbol`) |
| `/api/multiframe` | POST | Run multi-timeframe analysis overlay (`symbol`) |
| `/api/chart_data` | POST | Fetch OHLC bars and indicator series for Chart.js |
| `/api/diagnostics` | GET | Live connectivity status for Alpaca, Finnhub, and Gemini APIs |
| `/api/messages` | GET | Poll inter-agent pub/sub log (`since`, `session_id`, `category`, `symbol`) |
| `/api/sessions` | GET | List recorded analysis sessions |
| `/api/account` | GET | Alpaca paper account balance snapshot |
| `/api/positions` | GET | Current open positions and P&L |
| `/api/autonomous/start` | POST | Start background autonomous trading loop |
| `/api/autonomous/stop` | POST | Stop autonomous trading loop |
| `/api/execute` | POST | Manually submit paper order |
| `/api/sizing` | POST | Estimate position size (Vol targeting, Risk parity, Kelly) |
| `/api/screen` | POST | Run market screener for top candidates |
| `/api/backtest` | POST | Run historical backtest simulation |
| `/api/reflection` | POST | Generate Gemini AI reflections on recent trade history |
| `/api/report/daily` | GET | Daily performance summary report |
| `/api/search` | POST | Semantic vector search over trade history |
| `/api/history` | GET | Trade & analysis ledger history |
| `/api/history/stats` | GET | Ledger statistics summary |

---

## Environment Variables

Configure in `.env`:

```env
ALPACA_API_KEY=your_paper_key
ALPACA_SECRET_KEY=your_paper_secret
GEMINI_API_KEY=your_gemini_key

# Optional
FINNHUB_API_KEY=your_finnhub_key

# Auto-trading tuning
AUTO_EXECUTE_CONFIDENCE=0.75
AUTO_TRADE_NOTIONAL=500
DEFAULT_SYMBOL=AAPL
```

---

## How to Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run dashboard
python app.py
# → Open http://127.0.0.1:5000/
```
