"""
fundamental_agent.py

Fetches and analyzes fundamental data for a stock using Finnhub and simple metrics.
"""

from __future__ import annotations

from data.finnhub import FinnhubClient


class FundamentalAgent:
    name = "fundamental_agent"

    def __init__(self) -> None:
        self.finnhub = FinnhubClient()

    def analyze(self, symbol: str) -> dict:
        symbol = symbol.upper()
        result = {"symbol": symbol, "status": "fundamental analysis ready", "data": {}}

        # Try Finnhub company profile
        try:
            profile = self.finnhub.company_profile(symbol)
            if "error" not in profile:
                result["data"]["company"] = {
                    "name": profile.get("name"),
                    "industry": profile.get("finnhubIndustry"),
                    "sector": profile.get("sector"),
                    "market_cap": profile.get("marketCapitalization"),
                    "pe_ratio": profile.get("pe"),
                    "eps": profile.get("eps"),
                    "dividend_yield": profile.get("dividendYield"),
                    "beta": profile.get("beta"),
                    "website": profile.get("weburl"),
                }
        except Exception as e:
            result["data"]["company_error"] = str(e)

        # Simple scoring
        score = 0
        reasons = []
        pe = result["data"].get("company", {}).get("pe_ratio")
        if pe is not None:
            if pe < 15:
                score += 1
                reasons.append("Low P/E suggests value")
            elif pe > 40:
                score -= 1
                reasons.append("High P/E suggests overvaluation")
        beta = result["data"].get("company", {}).get("beta")
        if beta is not None:
            if beta > 1.5:
                reasons.append("High beta - volatile")
            elif beta < 0.8:
                reasons.append("Low beta - defensive")

        result["score"] = score
        result["reasons"] = reasons
        return result
