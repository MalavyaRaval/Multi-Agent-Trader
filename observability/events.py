from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class EventRecord:
    run_id: str
    agent: str
    event: str
    timestamp: str
    status: str = "success"
    symbol: str = ""
    provider: Optional[str] = None
    endpoint: Optional[str] = None
    duration_ms: Optional[int] = None
    records: Optional[int] = None
    feed: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "EventRecord":
        record = cls(
            run_id=payload.get("run_id", ""),
            agent=payload.get("agent", "unknown"),
            event=payload.get("event", "unknown"),
            timestamp=payload.get("timestamp", datetime.now(timezone.utc).isoformat()),
            status=payload.get("status", "success"),
            symbol=payload.get("symbol", ""),
            provider=payload.get("provider"),
            endpoint=payload.get("endpoint"),
            duration_ms=payload.get("duration_ms"),
            records=payload.get("records"),
            feed=payload.get("feed"),
            details={
                k: v for k, v in payload.items()
                if k not in {
                    "run_id",
                    "agent",
                    "event",
                    "timestamp",
                    "status",
                    "symbol",
                    "provider",
                    "endpoint",
                    "duration_ms",
                    "records",
                    "feed",
                }
            },
        )
        return record

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload.update(self.details)
        return payload
