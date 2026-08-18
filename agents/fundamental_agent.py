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
        result = {
            "symbol": symbol,
            "status": "data_unavailable",
            "source": "Finnhub",
            "data_available": False,
            "data_quality": "unavailable",
            "data": {},
            "industry": None,
            "pe": None,
            "eps": None,
            "beta": None,
            "score": None,
            "reasons": [],
            "error": None,
        }

        try:
            profile = self.finnhub.company_profile(symbol)
            if isinstance(profile, dict) and profile.get("error"):
                result["status"] = "error"
                result["error"] = str(profile.get("error"))
                return result

            metrics = self.finnhub.basic_financials(symbol)
            if isinstance(metrics, dict) and metrics.get("error"):
                result["error"] = str(metrics.get("error"))
                metrics = {}

            metric_map = metrics.get("metric", {}) if isinstance(metrics, dict) else {}

            if profile:
                result["data_available"] = True
                result["data_quality"] = "partial"
                result["data"]["company"] = {
                    "name": profile.get("name"),
                    "industry": profile.get("finnhubIndustry") or profile.get("industry"),
                    "sector": profile.get("sector"),
                    "market_cap": profile.get("marketCapitalization"),
                    "pe_ratio": profile.get("pe"),
                    "eps": profile.get("eps"),
                    "dividend_yield": profile.get("dividendYield"),
                    "beta": profile.get("beta"),
                    "website": profile.get("weburl"),
                }
                result["industry"] = result["data"]["company"].get("industry")

            pe = None
            eps = None
            beta = None
            if isinstance(profile, dict):
                pe = profile.get("pe")
                eps = profile.get("eps")
                beta = profile.get("beta")
            if pe is None:
                pe = metric_map.get("peBasicExclExtraTTM")
            if eps is None:
                eps = metric_map.get("epsBasicExclExtraTTM") or metric_map.get("epsTTM")
            if beta is None:
                beta = metric_map.get("beta")

            result["pe"] = pe
            result["eps"] = eps
            result["beta"] = beta

            if not profile and not metric_map:
                result["status"] = "error"
                return result

            if (pe is None and eps is None and beta is None):
                result["status"] = "partial"
                result["data_quality"] = "partial"
            else:
                result["status"] = "ok"
                result["data_quality"] = "complete"
        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)
            return result

        if result["status"] == "error":
            return result

        score = None
        reasons = []
        if pe is not None or beta is not None:
            score = 0
            if pe is not None:
                if pe < 15:
                    score += 1
                    reasons.append("Low P/E suggests value")
                elif pe > 40:
                    score -= 1
                    reasons.append("High P/E suggests overvaluation")
            if beta is not None:
                if beta > 1.5:
                    reasons.append("High beta - volatile")
                elif beta < 0.8:
                    reasons.append("Low beta - defensive")

        result["score"] = score
        result["reasons"] = reasons
        return result
