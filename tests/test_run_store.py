"""
Tests for PHASES_PLAN.md Phase 11 -- Persistent Run History (data/run_store.py).
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from data.run_store import RunStore, _classify_error


def _store(tmpdir):
    return RunStore(db_path=str(Path(tmpdir) / "test.db"))


def _fake_result(run_id="RUN-STORE-1", symbol="AAPL", action="buy"):
    return {
        "run_id": run_id,
        "symbol": symbol,
        "started_at": "2026-08-27T00:00:00+00:00",
        "timestamp": "2026-08-27T00:00:05+00:00",
        "status": "completed",
        "analyses": {
            "market": {"metrics": {"change_percent": 1.2}},
            "technical": {"status": "ok", "signals": {"rsi_14": 55.0}},
            "fundamental": {"status": "ok", "pe": 20.0},
            "news": {"status": "news analysis ready", "sentiment": "neutral"},
            "risk": {"status": "risk analysis ready", "risk_level": "low"},
            "portfolio": {"status": "portfolio check ready", "position": None},
            "execution": {
                "status": "execution analysis ready",
                "action": action,
                "confidence": 0.8,
                "raw_score": 0.5,
                "reason": "strong signal",
                "decision_status": "NORMAL",
                "hold_reason": None,
                "strategy_votes": [
                    {"strategy": "momentum", "decision": "buy", "confidence": 0.7, "raw_score": 1.0, "reason": "strong"},
                    {"strategy": "trend_following", "decision": "hold", "confidence": 0.1, "raw_score": 0.0, "reason": "flat"},
                ],
                "score_breakdown": {"combined_score": 0.5, "buy_threshold": 0.25, "sell_threshold": -0.25},
                "decision_explanation": {"action": action, "agent_reasons": ["RSI oversold"]},
                "detailed_reasoning": {"executive_summary": "Looks good"},
            },
        },
        "auto_trade": {"order_id": "ORD-1", "side": "buy", "qty": 5.0, "notional": None, "status": "submitted"},
    }


def _fake_events(run_id):
    return [
        {"agent": "orchestrator", "event": "analysis_started", "timestamp": "2026-08-27T00:00:00+00:00", "status": "running"},
        {"agent": "market_agent", "event": "data_quality_check", "timestamp": "2026-08-27T00:00:01+00:00", "status": "success"},
        {"agent": "orchestrator", "event": "analysis_completed", "timestamp": "2026-08-27T00:00:05+00:00", "status": "success"},
    ]


def test_schema_creates_all_tables():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp)
        conn = sqlite3.connect(store.db_path)
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        for expected in ("runs", "events", "agent_results", "strategy_votes", "decisions", "orders", "errors"):
            assert expected in tables


def test_save_and_get_run_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp)
        result = _fake_result()
        store.save_run(result, events=_fake_events(result["run_id"]))

        detail = store.get_run("RUN-STORE-1")
        assert detail is not None
        assert detail["overview"]["run_id"] == "RUN-STORE-1"
        assert detail["overview"]["symbol"] == "AAPL"
        assert detail["execution"]["action"] == "buy"


def test_get_run_returns_none_for_unknown():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp)
        assert store.get_run("RUN-DOES-NOT-EXIST") is None


def test_strategy_votes_persisted():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp)
        result = _fake_result()
        store.save_run(result, events=[])
        detail = store.get_run(result["run_id"])
        assert len(detail["strategies"]) == 2
        names = {v["strategy"] for v in detail["strategies"]}
        assert names == {"momentum", "trend_following"}


def test_orders_persisted():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp)
        result = _fake_result()
        store.save_run(result, events=[])
        detail = store.get_run(result["run_id"])
        assert detail["order"] is not None
        assert detail["order"][0]["order_id"] == "ORD-1"


def test_no_order_when_no_auto_trade():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp)
        result = _fake_result()
        result["auto_trade"] = None
        store.save_run(result, events=[])
        detail = store.get_run(result["run_id"])
        assert detail["order"] is None


def test_errors_persisted():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp)
        result = _fake_result()
        result["analyses"]["news"] = {"status": "error", "error": "Finnhub down"}
        store.save_run(result, events=[])
        detail = store.get_run(result["run_id"])
        assert len(detail["errors"]) == 1
        assert detail["errors"][0]["stage"] == "news"


def test_events_persisted_and_api_calls_filtered():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp)
        result = _fake_result()
        store.save_run(result, events=_fake_events(result["run_id"]))
        detail = store.get_run(result["run_id"])
        # analysis_started / analysis_completed are excluded from api_calls
        assert len(detail["api_calls"]) == 1
        assert detail["api_calls"][0]["event"] == "data_quality_check"
        assert detail["timing"]["event_count"] == 3


def test_save_run_upserts_not_duplicates():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp)
        result = _fake_result()
        store.save_run(result, events=_fake_events(result["run_id"]))
        store.save_run(result, events=_fake_events(result["run_id"]))  # save again

        runs = store.list_runs(limit=10)
        assert len(runs) == 1  # not duplicated

        detail = store.get_run(result["run_id"])
        assert len(detail["strategies"]) == 2  # not doubled


def test_list_runs_ordering_and_limit():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp)
        for i in range(5):
            result = _fake_result(run_id=f"RUN-{i}")
            result["started_at"] = f"2026-08-27T00:0{i}:00+00:00"
            store.save_run(result, events=[])

        runs = store.list_runs(limit=3)
        assert len(runs) == 3
        assert runs[0]["run_id"] == "RUN-4"  # most recent first


def test_missing_run_id_is_noop():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp)
        store.save_run({"symbol": "AAPL"}, events=[])  # no run_id
        assert store.list_runs() == []


# ---------------------------------------------------------------------------
# PHASES_PLAN.md Phase 12 -- Error Tracking
# ---------------------------------------------------------------------------

def test_classify_error_rate_limit():
    result = _classify_error("news", "HTTP 429: Rate limit exceeded")
    assert result["error_type"] == "RateLimitError"
    assert result["status_code"] == 429
    assert result["agent"] == "NewsAgent"
    assert result["provider"] == "Finnhub"


def test_classify_error_auth():
    result = _classify_error("market", "HTTP 401: Unauthorized")
    assert result["error_type"] == "AuthenticationError"
    assert result["status_code"] == 401
    assert result["provider"] == "Alpaca"


def test_classify_error_timeout():
    result = _classify_error("fundamental", "Connection timed out after 30s")
    assert result["error_type"] == "TimeoutError"
    assert result["status_code"] is None


def test_classify_error_not_configured():
    result = _classify_error("portfolio", "Alpaca client not initialized")
    assert result["error_type"] == "NotConfiguredError"


def test_classify_error_unknown_fallback():
    result = _classify_error("risk", "something went sideways")
    assert result["error_type"] == "UnknownError"


def test_errors_table_has_rich_columns():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp)
        result = _fake_result()
        result["analyses"]["news"] = {"status": "error", "error": "HTTP 429: rate limited"}
        store.save_run(result, events=[])

        detail = store.get_run(result["run_id"])
        err = detail["errors"][0]
        assert err["agent"] == "NewsAgent"
        assert err["provider"] == "Finnhub"
        assert err["error_type"] == "RateLimitError"
        assert err["status_code"] == 429
        assert err["message"] == "HTTP 429: rate limited"


def test_list_recent_errors_across_runs():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp)
        for i in range(3):
            result = _fake_result(run_id=f"RUN-ERR-{i}")
            result["started_at"] = f"2026-08-27T00:0{i}:00+00:00"
            result["timestamp"] = f"2026-08-27T00:0{i}:05+00:00"
            result["analyses"]["news"] = {"status": "error", "error": f"failure {i}"}
            store.save_run(result, events=[])

        errors = store.list_recent_errors(limit=10)
        assert len(errors) == 3
        assert errors[0]["run_id"] == "RUN-ERR-2"  # newest first


def test_errors_table_migration_from_old_schema():
    """A store created by a pre-Phase-12 version (run_id, stage, error_message
    only) should gain the new columns on next init, without losing old rows."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "old.db")
        conn = sqlite3.connect(db_path)
        try:
            # Phase 11's actual `runs` schema (unchanged by Phase 12) -- only
            # `errors` gained new columns, so simulate that realistically.
            conn.execute(
                """
                CREATE TABLE runs (
                    run_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, status TEXT,
                    started_at TEXT, completed_at TEXT, action TEXT,
                    confidence REAL, raw_score REAL, reason TEXT
                )
                """
            )
            conn.execute(
                "CREATE TABLE errors (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, stage TEXT, error_message TEXT)"
            )
            conn.execute("INSERT INTO errors (run_id, stage, error_message) VALUES ('RUN-OLD', 'news', 'legacy error')")
            conn.commit()
        finally:
            conn.close()

        store = RunStore(db_path=db_path)  # triggers migration in _init_schema

        conn = sqlite3.connect(db_path)
        try:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(errors)")}
        finally:
            conn.close()
        for expected in ("symbol", "agent", "provider", "error_type", "status_code", "message", "timestamp", "retry_count", "recovered"):
            assert expected in cols

        # New writes work fine post-migration.
        result = _fake_result(run_id="RUN-NEW")
        result["analyses"]["news"] = {"status": "error", "error": "fresh error"}
        store.save_run(result, events=[])
        errors = store.list_recent_errors(limit=10)
        assert any(e["run_id"] == "RUN-NEW" and e["message"] == "fresh error" for e in errors)
