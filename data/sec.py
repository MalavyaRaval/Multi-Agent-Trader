from __future__ import annotations


class SECClient:
    def get_financials(self, symbol: str) -> dict:
        return {"symbol": symbol, "status": "SEC data placeholder"}
