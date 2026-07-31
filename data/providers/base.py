from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import pandas as pd


class MarketDataProvider(ABC):
    @abstractmethod
    def latest_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def latest_trade(self, symbol: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def historical_bars(self, symbol: str, timeframe: str, days: int) -> pd.DataFrame:
        pass

    @abstractmethod
    def snapshot(self, symbol: str, timeframe: str, days: int) -> Dict[str, Any]:
        pass

    @abstractmethod
    def snapshot_multi_timeframe(self, symbol: str, intervals: List[str], days: int) -> Dict[str, Dict[str, Any]]:
        pass
