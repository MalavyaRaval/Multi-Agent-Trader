import requests
from config import FINNHUB_API_KEY


class FinnhubClient:
    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or FINNHUB_API_KEY or ""
        self.session = requests.Session()

    def _get(self, endpoint: str, params: dict = None):
        if not self.api_key:
            return {"error": "Finnhub API key not configured"}
        params = params or {}
        params["token"] = self.api_key
        resp = self.session.get(f"{self.BASE_URL}/{endpoint}", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def company_profile(self, symbol: str):
        return self._get("stock/profile2", {"symbol": symbol})

    def basic_financials(self, symbol: str):
        return self._get("stock/metric", {"symbol": symbol, "metric": "all"})

    def news(self, symbol: str, from_date: str, to_date: str):
        return self._get("company-news", {"symbol": symbol, "from": from_date, "to": to_date})

    def quote(self, symbol: str):
        return self._get("quote", {"symbol": symbol})
