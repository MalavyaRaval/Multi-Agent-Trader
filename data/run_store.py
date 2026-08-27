"""
data/run_store.py

PHASES_PLAN.md Phase 11 -- Persistent Run History.

SQLite-backed storage for full analyze_symbol() run records, replacing the
bounded in-memory cache Phase 10 used as a stand-in. A fresh connection is
opened per call (sqlite3 connections are cheap for a local file and this
avoids any cross-thread sharing concerns -- the autonomous loop writes from
a background thread while the Flask app reads from request threads).

Tables (per the plan's list; "api_calls" is a queryable subset of `events`
rather than a separate table, since every API call is already an event):
    runs            one row per run: identity, timing, final decision summary
    events          one row per observability event (market data fetch,
                    agent lifecycle, data-quality check, ...)
    agent_results   one row per agent stage per run, full result as JSON
    strategy_votes  one row per strategy vote per run
    decisions       one row per run: the execution decision, as real columns
                    (not just JSON) so later phases can run real SQL queries
                    over it (Phase 25 Agent Performance, Phase 26 Calibration)
    orders          one row per auto-trade attempt
    errors          one row per stage that reported an error
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import DATA_DIR

DEFAULT_DB_PATH = str(DATA_DIR / "trading_system.db")

_HTTP_STATUS_RE = re.compile(r"\b(\d{3})\b")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    status TEXT,
    started_at TEXT,
    completed_at TEXT,
    action TEXT,
    confidence REAL,
    raw_score REAL,
    reason TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    agent TEXT,
    event TEXT,
    timestamp TEXT,
    status TEXT,
    payload_json TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_events_run_id ON events(run_id);

CREATE TABLE IF NOT EXISTS agent_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    result_json TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_agent_results_run_id ON agent_results(run_id);

CREATE TABLE IF NOT EXISTS strategy_votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    strategy TEXT,
    decision TEXT,
    confidence REAL,
    raw_score REAL,
    reason TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_strategy_votes_run_id ON strategy_votes(run_id);

CREATE TABLE IF NOT EXISTS decisions (
    run_id TEXT PRIMARY KEY,
    symbol TEXT,
    action TEXT,
    confidence REAL,
    combined_score REAL,
    buy_threshold REAL,
    sell_threshold REAL,
    decision_status TEXT,
    hold_reason TEXT,
    reason TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    order_id TEXT,
    symbol TEXT,
    side TEXT,
    qty REAL,
    notional REAL,
    status TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_orders_run_id ON orders(run_id);

CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    symbol TEXT,
    stage TEXT,
    agent TEXT,
    provider TEXT,
    error_type TEXT,
    status_code INTEGER,
    message TEXT,
    timestamp TEXT,
    retry_count INTEGER,
    recovered INTEGER,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_errors_run_id ON errors(run_id);
"""

# PHASES_PLAN.md Phase 12 -- best-effort classification of a stage's raw error
# text into (agent class name, upstream provider) so the errors table carries
# more than an opaque string, without requiring every agent to be rewritten
# to pass structured error objects.
_STAGE_AGENT = {
    "market": "MarketAgent",
    "technical": "TechnicalAgent",
    "fundamental": "FundamentalAgent",
    "news": "NewsAgent",
    "risk": "RiskAgent",
    "portfolio": "PortfolioAgent",
    "execution": "ExecutionAgent",
}
_STAGE_PROVIDER = {
    "market": "Alpaca",
    "technical": "Alpaca",
    "risk": "Alpaca",
    "portfolio": "Alpaca",
    "fundamental": "Finnhub",
    "news": "Finnhub",
    "execution": "Alpaca",
}


def _classify_error(stage: str, message: str) -> Dict[str, Any]:
    """Best-effort error_type/status_code extraction from a plain-text error
    message. Returns None for fields that can't be derived from text alone
    (retry_count/recovered need instrumentation this doesn't have access to)."""
    text = message or ""
    status_code = None
    for match in _HTTP_STATUS_RE.finditer(text):
        code = int(match.group(1))
        if 100 <= code <= 599:
            status_code = code
            break

    lowered = text.lower()
    if status_code == 429 or "rate limit" in lowered:
        error_type = "RateLimitError"
    elif status_code in (401, 403) or "unauthorized" in lowered or "forbidden" in lowered:
        error_type = "AuthenticationError"
    elif "timeout" in lowered or "timed out" in lowered:
        error_type = "TimeoutError"
    elif status_code and status_code >= 500:
        error_type = "ServerError"
    elif status_code and status_code >= 400:
        error_type = "HTTPError"
    elif "not initialized" in lowered or "not configured" in lowered:
        error_type = "NotConfiguredError"
    else:
        error_type = "UnknownError"

    return {
        "agent": _STAGE_AGENT.get(stage, stage),
        "provider": _STAGE_PROVIDER.get(stage),
        "error_type": error_type,
        "status_code": status_code,
    }


class RunStore:
    """Durable, SQLite-backed storage for full run records."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or DEFAULT_DB_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    @contextmanager
    def _connection(self):
        """Open a connection for one transaction, guaranteeing it's closed
        afterward. `sqlite3.Connection` used as a context manager only
        commits/rolls back -- it does NOT close the file handle, which leaks
        connections and (on Windows) blocks deleting the db file."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._lock, self._connection() as conn:
            conn.executescript(_SCHEMA)
            # PHASES_PLAN.md Phase 12 -- migrate an `errors` table created by an
            # earlier version of this store (run_id, stage, error_message only).
            existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(errors)")}
            for column, coltype in (
                ("symbol", "TEXT"), ("agent", "TEXT"), ("provider", "TEXT"),
                ("error_type", "TEXT"), ("status_code", "INTEGER"), ("message", "TEXT"),
                ("timestamp", "TEXT"), ("retry_count", "INTEGER"), ("recovered", "INTEGER"),
            ):
                if column not in existing_cols:
                    conn.execute(f"ALTER TABLE errors ADD COLUMN {column} {coltype}")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_errors_timestamp ON errors(timestamp)")

    def save_run(self, result: Dict[str, Any], events: Optional[List[Dict[str, Any]]] = None) -> None:
        """Persist a full analyze_symbol() result across all tables in one transaction.

        `events` is the RunTracker event list for this run_id (not embedded in
        `result` itself, which only carries a summary) -- pass
        `run_tracker.get_events(run_id)`.
        """
        run_id = result.get("run_id")
        if not run_id:
            return

        analyses = result.get("analyses", {}) or {}
        execution = analyses.get("execution", {}) or {}
        breakdown = execution.get("score_breakdown") or {}
        events = events or []

        with self._lock, self._connection() as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, symbol, status, started_at, completed_at, action, confidence, raw_score, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status=excluded.status, completed_at=excluded.completed_at,
                    action=excluded.action, confidence=excluded.confidence,
                    raw_score=excluded.raw_score, reason=excluded.reason
                """,
                (
                    run_id, result.get("symbol"), result.get("status"),
                    result.get("started_at"), result.get("timestamp"),
                    execution.get("action"), execution.get("confidence"),
                    execution.get("raw_score"), execution.get("reason"),
                ),
            )

            conn.execute("DELETE FROM events WHERE run_id = ?", (run_id,))
            conn.executemany(
                "INSERT INTO events (run_id, agent, event, timestamp, status, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (run_id, e.get("agent"), e.get("event"), e.get("timestamp"), e.get("status"), json.dumps(e, default=str))
                    for e in events
                ],
            )

            conn.execute("DELETE FROM agent_results WHERE run_id = ?", (run_id,))
            conn.executemany(
                "INSERT INTO agent_results (run_id, stage, result_json) VALUES (?, ?, ?)",
                [(run_id, stage, json.dumps(stage_result, default=str)) for stage, stage_result in analyses.items()],
            )

            conn.execute("DELETE FROM strategy_votes WHERE run_id = ?", (run_id,))
            conn.executemany(
                "INSERT INTO strategy_votes (run_id, strategy, decision, confidence, raw_score, reason) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (run_id, v.get("strategy") or v.get("name"), v.get("decision"), v.get("confidence"), v.get("raw_score"), v.get("reason"))
                    for v in execution.get("strategy_votes", [])
                ],
            )

            conn.execute(
                """
                INSERT INTO decisions (run_id, symbol, action, confidence, combined_score, buy_threshold, sell_threshold, decision_status, hold_reason, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    action=excluded.action, confidence=excluded.confidence, combined_score=excluded.combined_score,
                    decision_status=excluded.decision_status, hold_reason=excluded.hold_reason, reason=excluded.reason
                """,
                (
                    run_id, result.get("symbol"), execution.get("action"), execution.get("confidence"),
                    breakdown.get("combined_score"), breakdown.get("buy_threshold"), breakdown.get("sell_threshold"),
                    execution.get("decision_status"), execution.get("hold_reason"), execution.get("reason"),
                ),
            )

            conn.execute("DELETE FROM orders WHERE run_id = ?", (run_id,))
            auto_trade = result.get("auto_trade")
            if auto_trade:
                conn.execute(
                    "INSERT INTO orders (run_id, order_id, symbol, side, qty, notional, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        run_id, auto_trade.get("order_id"), result.get("symbol"), auto_trade.get("side"),
                        auto_trade.get("qty"), auto_trade.get("notional"), auto_trade.get("status"),
                    ),
                )

            conn.execute("DELETE FROM errors WHERE run_id = ?", (run_id,))
            error_rows = []
            for stage, stage_result in analyses.items():
                if not isinstance(stage_result, dict):
                    continue
                message = stage_result.get("error") or stage_result.get("status")
                is_error = stage_result.get("error") or str(stage_result.get("status", "")).lower() == "error"
                if not is_error:
                    continue
                classified = _classify_error(stage, str(message))
                error_rows.append((
                    run_id, result.get("symbol"), stage,
                    classified["agent"], classified["provider"], classified["error_type"], classified["status_code"],
                    message, result.get("timestamp"), None, None,
                ))
            conn.executemany(
                """
                INSERT INTO errors (run_id, symbol, stage, agent, provider, error_type, status_code, message, timestamp, retry_count, recovered)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                error_rows,
            )

    def list_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                "SELECT run_id, symbol, status, started_at, completed_at, action FROM runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_recent_errors(self, limit: int = 50) -> List[Dict[str, Any]]:
        """PHASES_PLAN.md Phase 12 -- global (cross-run) recent-errors feed for
        the dashboard's ERRORS panel, newest first."""
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                """
                SELECT run_id, symbol, stage, agent, provider, error_type, status_code, message, timestamp, retry_count, recovered
                FROM errors ORDER BY timestamp DESC, id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Reconstruct the 14-section run detail dict for one run, or None if not found."""
        with self._lock, self._connection() as conn:
            run_row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if run_row is None:
                return None

            event_rows = conn.execute(
                "SELECT agent, event, timestamp, status, payload_json FROM events WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
            agent_rows = conn.execute(
                "SELECT stage, result_json FROM agent_results WHERE run_id = ?", (run_id,)
            ).fetchall()
            vote_rows = conn.execute(
                "SELECT strategy, decision, confidence, raw_score, reason FROM strategy_votes WHERE run_id = ?", (run_id,)
            ).fetchall()
            decision_row = conn.execute("SELECT * FROM decisions WHERE run_id = ?", (run_id,)).fetchone()
            order_rows = conn.execute("SELECT * FROM orders WHERE run_id = ?", (run_id,)).fetchall()
            error_rows = conn.execute(
                "SELECT stage, agent, provider, error_type, status_code, message, timestamp, retry_count, recovered FROM errors WHERE run_id = ?",
                (run_id,),
            ).fetchall()

        agent_results = {row["stage"]: json.loads(row["result_json"]) for row in agent_rows}
        events = [
            {"agent": r["agent"], "event": r["event"], "timestamp": r["timestamp"], "status": r["status"]}
            for r in event_rows
        ]
        api_calls = [e for e in events if e.get("event") not in ("run_started", "analysis_started", "analysis_completed")]

        execution = dict(agent_results.get("execution", {}))
        decision = dict(decision_row) if decision_row else {}

        return {
            "overview": {
                "run_id": run_row["run_id"],
                "symbol": run_row["symbol"],
                "status": run_row["status"],
                "started_at": run_row["started_at"],
                "completed_at": run_row["completed_at"],
            },
            "api_calls": api_calls,
            "market_data": agent_results.get("market", {}),
            "technical_analysis": agent_results.get("technical", {}),
            "fundamentals": agent_results.get("fundamental", {}),
            "news": agent_results.get("news", {}),
            "risk": agent_results.get("risk", {}),
            "portfolio": agent_results.get("portfolio", {}),
            "strategies": [dict(v) for v in vote_rows],
            "execution": execution,
            "order": [dict(o) for o in order_rows] or None,
            "errors": [dict(e) for e in error_rows],
            "timing": {
                "started_at": run_row["started_at"],
                "completed_at": run_row["completed_at"],
                "event_count": len(events),
            },
            "decision_trace": {
                "decision": decision,
                "decision_explanation": execution.get("decision_explanation"),
                "score_breakdown": execution.get("score_breakdown"),
                "detailed_reasoning": execution.get("detailed_reasoning"),
            },
        }
