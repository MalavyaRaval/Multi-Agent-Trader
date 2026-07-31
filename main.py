from __future__ import annotations

import json
from agents.market_agent import MarketAgent
from agents.technical_agent import TechnicalAgent
from agents.fundamental_agent import FundamentalAgent
from agents.news_agent import NewsAgent
from agents.risk_agent import RiskAgent
from agents.execution_agent import ExecutionAgent
from agents.portfolio_agent import PortfolioAgent
from config import DEFAULT_SYMBOL


def main() -> None:
    symbol = input("Enter a symbol (default: AAPL): ").strip().upper() or DEFAULT_SYMBOL

    agents = [
        MarketAgent(),
        TechnicalAgent(),
        FundamentalAgent(),
        NewsAgent(),
        RiskAgent(),
        ExecutionAgent(),
        PortfolioAgent(),
    ]

    results = {}
    for agent in agents:
        results[agent.name] = agent.analyze(symbol)

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
