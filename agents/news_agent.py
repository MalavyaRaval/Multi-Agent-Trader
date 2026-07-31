"""
news_agent.py

Fetches news and estimates sentiment for a stock using Finnhub news API.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import requests

from config import FINNHUB_API_KEY


class NewsAgent:
    name = "news_agent"

    def __init__(self) -> None:
        self.api_key = FINNHUB_API_KEY
        self.base_url = "https://finnhub.io/api/v1"

    def analyze(self, symbol: str) -> dict:
        symbol = symbol.upper()
        result = {"symbol": symbol, "status": "news analysis ready", "articles": [], "sentiment": "neutral"}

        if not self.api_key:
            result["status"] = "news analysis skipped (no API key)"
            return result

        try:
            end = datetime.utcnow()
            start = end - timedelta(days=7)
            url = (
                f"{self.base_url}/company-news"
                f"?symbol={symbol}&from={start.strftime('%Y-%m-%d')}&to={end.strftime('%Y-%m-%d')}"
                f"&token={self.api_key}"
            )
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            articles = resp.json()

            if not isinstance(articles, list):
                result["status"] = "news analysis error (unexpected response)"
                return result

            # Keep top 5 articles
            top = articles[:5]
            result["articles"] = [
                {
                    "headline": a.get("headline", ""),
                    "source": a.get("source", ""),
                    "datetime": a.get("datetime"),
                    "url": a.get("url", ""),
                    "summary": a.get("summary", "")[:200],
                }
                for a in top
            ]

            # Very simple keyword-based sentiment
            sentiment_score = 0
            positive_words = ["beat", "strong", "growth", "rise", "rally", "gain", "bull", "upgrade", "outperform"]
            negative_words = ["miss", "weak", "drop", "fall", "crash", "bear", "downgrade", "underperform", "loss"]
            for a in top:
                text = f"{a.get('headline', '')} {a.get('summary', '')}".lower()
                for w in positive_words:
                    sentiment_score += text.count(w)
                for w in negative_words:
                    sentiment_score -= text.count(w)

            if sentiment_score > 1:
                result["sentiment"] = "positive"
            elif sentiment_score < -1:
                result["sentiment"] = "negative"
            else:
                result["sentiment"] = "neutral"
            result["sentiment_score"] = sentiment_score

        except Exception as e:
            result["status"] = f"news analysis error: {e}"

        return result
