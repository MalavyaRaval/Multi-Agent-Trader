from __future__ import annotations

from typing import Any, Dict, Optional

from .run_tracker import RunTracker


class EventLogger:
    def __init__(self, tracker: Optional[RunTracker] = None):
        self.tracker = tracker or RunTracker()

    def log(
        self,
        agent: str,
        event: str,
        *,
        run_id: Optional[str] = None,
        symbol: Optional[str] = None,
        status: str = "success",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self.tracker.emit_event(
            agent,
            event,
            run_id=run_id,
            symbol=symbol,
            status=status,
            **kwargs,
        )
