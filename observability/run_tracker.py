from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


def now_iso() -> str:
    """Current UTC time as a timezone-aware ISO-8601 string. Single source of
    truth so observability, memory, and optimization timestamps stay comparable."""
    return datetime.now(timezone.utc).isoformat()


class RunTracker:
    """Simple JSONL event collector for observability runs."""

    def __init__(self, base_dir: Optional[Union[str, Path]] = None):
        if base_dir is None:
            base_dir = Path(__file__).resolve().parents[1] / "data" / "observability"
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._runs: Dict[str, Dict[str, Any]] = {}
        self._active_run_id: Optional[str] = None

    @staticmethod
    def generate_run_id(symbol: str) -> str:
        now = datetime.now(timezone.utc)
        stamp = now.strftime("%Y%m%d-%H%M%S")
        return f"RUN-{stamp}-{symbol.upper()}"

    def start_run(self, symbol: str, *, run_id: Optional[str] = None) -> Dict[str, Any]:
        symbol = (symbol or "UNKNOWN").upper()
        if run_id is None:
            run_id = self.generate_run_id(symbol)
        started_at = now_iso()
        run = {
            "run_id": run_id,
            "symbol": symbol,
            "started_at": started_at,
            "status": "running",
            "event_count": 0,
            "events": [],
        }
        self._runs[run_id] = run
        self._active_run_id = run_id
        self.emit_event(
            "orchestrator",
            "run_started",
            run_id=run_id,
            symbol=symbol,
            status="running",
            endpoint="analysis_start",
        )
        return dict(run)

    def emit_event(
        self,
        agent: str,
        event: str,
        *,
        run_id: Optional[str] = None,
        symbol: Optional[str] = None,
        status: str = "success",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if run_id is None:
            run_id = self._active_run_id
        if run_id is None:
            run_id = self.start_run(symbol or "UNKNOWN")["run_id"]

        payload = {
            "run_id": run_id,
            "agent": agent,
            "event": event,
            "timestamp": now_iso(),
            "status": status,
            "symbol": (symbol or self._runs.get(run_id, {}).get("symbol") or "").upper(),
        }
        payload.update(kwargs)

        file_path = self.base_dir / f"{run_id}.jsonl"
        with file_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str) + "\n")

        run = self._runs.setdefault(run_id, {"run_id": run_id, "symbol": payload["symbol"], "status": "running", "events": []})
        run.setdefault("event_count", 0)
        run["event_count"] += 1
        run["events"].append(payload)
        run["status"] = status if status in {"running", "error", "warning", "success"} else run.get("status", "running")
        run["updated_at"] = payload["timestamp"]
        return payload

    def summary(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        run_id = run_id or self._active_run_id
        if run_id is None:
            return {"run_id": None, "event_count": 0}

        run = self._runs.get(run_id, {})
        events = run.get("events", [])
        return {
            "run_id": run_id,
            "symbol": run.get("symbol", ""),
            "status": run.get("status", "running"),
            "started_at": run.get("started_at"),
            "event_count": len(events),
            "last_event_at": events[-1].get("timestamp") if events else None,
        }

    def get_events(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        run_id = run_id or self._active_run_id
        if run_id is None:
            return []
        return list(self._runs.get(run_id, {}).get("events", []))
