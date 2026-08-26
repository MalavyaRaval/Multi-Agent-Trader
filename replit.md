# Paper Trading Multi-Agent Platform

A Flask-based paper-trading research dashboard with multi-agent orchestration for technical, fundamental, news, risk, and portfolio analysis. Strategies vote on buy/sell/hold decisions; trades are executed via Alpaca paper trading.

## How to run

```bash
python app.py
```

The dashboard is served at port 5000. The workflow "Start application" runs it automatically.

## Environment secrets required

| Secret | Purpose |
|---|---|
| `ALPACA_API_KEY` | Alpaca paper trading key |
| `ALPACA_SECRET_KEY` | Alpaca paper trading secret |
| `GEMINI_API_KEY` | Google Gemini AI (agents) |
| `FINNHUB_API_KEY` | Finnhub news/fundamentals |

## Stack

- **Python / Flask** — web dashboard and REST API
- **alpaca-py** — paper trade execution
- **google-genai** — Gemini AI agent integration
- **pandas / numpy** — indicator and backtest calculations
- **gunicorn** — production WSGI server

## Key endpoints

- `GET /` — main dashboard
- `POST /api/analyze` — full multi-agent symbol analysis
- `POST /api/backtest` — run a backtest
- `POST /api/screen` — screen watchlist candidates
- `GET /api/history` — trade/analysis history
- `POST /api/autonomous/start` — start autonomous trading loop
- `POST /api/autonomous/stop` — stop autonomous trading loop

## User preferences

- Keep paper-trading mode by default (safe, no real money at risk)
