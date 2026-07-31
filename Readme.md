# Paper Trading Multi-Agent Platform

This project is now organized as a single, structured Python application with:

- a web dashboard powered by Flask
- a trading agent for paper trading
- a market data collector agent
- a modular folder structure for agents, data, indicators, memory, and strategies

## Project structure

```text
.
├── agents/
├── data/
├── indicators/
├── memory/
├── strategies/
├── templates/
├── app.py
├── config.py
├── main.py
├── market_data_agent.py
├── requirements.txt
├── trading_agent.py
└── Readme.md
```

## What is included

- Trading agent: [trading_agent.py](trading_agent.py)
- Market data agent: [market_data_agent.py](market_data_agent.py)
- Web dashboard: [app.py](app.py) with template support in [templates](templates)
- Modular AI trader scaffold: [main.py](main.py)

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
FINNHUB_API_KEY=optional
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

## Notes

- The trading and market data agents use Alpaca paper trading.
- The web UI lets you communicate with the agents from the browser.
- The modular folders are ready for future expansion into more advanced multi-agent workflows.

## Next steps

You can now extend the project by:

- adding more agents in [agents](agents)
- wiring live technical/fundamental signals
- connecting the dashboard to a richer chat history view
- adding persistence for trades and memory

## Customizing

The tools live in one place near the top of `trading_agent.py` — `TOOL_IMPLS`
and `TOOL_DECLARATIONS`. A few natural next steps if you want them:

- **Limit orders**: add a `limit_price` argument and use alpaca-py's
  `LimitOrderRequest` instead of `MarketOrderRequest` in `_place_order`.
- **Watchlists / recurring checks**: add a `get_watchlist` tool, or wrap
  `get_positions` in a loop that runs on a schedule.
- **Order history**: add a tool around `trading_client.get_orders()`.
- Edit `SYSTEM_INSTRUCTION` to change the agent's tone or add house rules
  (e.g. "never let a single order exceed $1000").

## Troubleshooting

- `Could not connect to Alpaca`: double check you copied the **paper** keys
  (not live) into `.env`, with no extra spaces or quotes.
- `Gemini API error`: check the key at aistudio.google.com/apikey is active,
  and that you have internet access.
- Nothing happens after you answer `y` to a confirmation: check your terminal
  didn't lose focus — it's a normal blocking `input()` prompt.