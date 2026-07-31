from __future__ import annotations

import os

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from config import ALPACA_API_KEY, ALPACA_SECRET_KEY


class AlpacaData:
    def __init__(self) -> None:
        self.client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)

    def get_latest_quote(self, symbol: str) -> dict:
        req = StockLatestQuoteRequest(symbol_or_symbols=[symbol.upper()])
        quote = self.client.get_stock_latest_quote(req)[symbol.upper()]
        return {"bid": quote.bid_price, "ask": quote.ask_price}
