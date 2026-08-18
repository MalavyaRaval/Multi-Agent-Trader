from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List


class MetricsCollector:
    @staticmethod
    def summarize_events(events: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        entries = list(events)
        counters = Counter(event.get("event", "unknown") for event in entries)
        return {
            "event_count": len(entries),
            "event_types": dict(sorted(counters.items())),
            "success_count": sum(1 for item in entries if item.get("status") == "success"),
            "error_count": sum(1 for item in entries if item.get("status") == "error"),
        }

    @staticmethod
    def summarize_run(run_id: str, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        summary = MetricsCollector.summarize_events(events)
        summary["run_id"] = run_id
        return summary
