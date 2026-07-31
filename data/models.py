from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd


@dataclass
class MarketQuote:
    symbol: str
    bid_price: float
    ask_price: float
    bid_size: int
    ask_size: int
    timestamp: datetime


@dataclass
class MarketTrade:
    symbol: str
    price: float
    size: int
    timestamp: datetime


@dataclass
class MarketSnapshot:
    symbol: str
    timeframe: str
    quote: Optional[MarketQuote]
    trade: Optional[MarketTrade]
    bars: pd.DataFrame
    metrics: Optional[Dict[str, Any]] = None
    generated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.generated_at is None:
            self.generated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["bars"] = self.bars.to_dict(orient="records")
        data["generated_at"] = self.generated_at.isoformat() if self.generated_at else None
        return data
