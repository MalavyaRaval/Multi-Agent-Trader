"""
Tests for PHASES_PLAN.md Phase 9 -- Autonomous Loop Monitor.
"""

from __future__ import annotations

import time

from orchestrator import Orchestrator


def test_initial_status_is_stopped():
    o = Orchestrator()
    status = o.get_autonomous_status()
    assert status["status"] == "stopped"
    assert status["runs_today"] == 0
    assert status["recent_runs"] == []


def test_classify_stage_status():
    classify = Orchestrator._classify_stage_status
    assert classify({"status": "ok"}) == "PASS"
    assert classify({"status": "execution analysis ready"}) == "PASS"
    assert classify({"status": "error"}) == "ERROR"
    assert classify({"status": "risk_error"}) == "ERROR"
    assert classify({"status": "news analysis skipped (no API key)"}) == "WARNING"
    assert classify({"status": "insufficient_data"}) == "WARNING"
    assert classify({}) == "UNKNOWN"
    assert classify(None) == "UNKNOWN"
    assert classify("not a dict") == "UNKNOWN"


def test_record_autonomous_run_updates_counters():
    o = Orchestrator()

    result = {
        "analyses": {
            "market": {"status": "ok"},
            "technical": {"status": "ok"},
            "fundamental": {"status": "ok"},
            "news": {"status": "ok"},
            "risk": {"status": "ok"},
            "portfolio": {"status": "ok"},
            "execution": {"status": "execution analysis ready", "action": "buy"},
        }
    }
    o._record_autonomous_run("RUN-1", "AAPL", 3.7, result)

    status = o.get_autonomous_status()
    assert status["runs_today"] == 1
    assert status["successful"] == 1
    assert status["warnings"] == 0
    assert status["errors"] == 0
    assert status["buy_count"] == 1
    assert status["sell_count"] == 0
    assert status["hold_count"] == 0
    assert status["last_run_at"] is not None
    assert len(status["recent_runs"]) == 1
    assert status["recent_runs"][0]["status"] == "SUCCESS"
    assert status["recent_runs"][0]["symbol"] == "AAPL"
    assert status["recent_runs"][0]["duration_seconds"] == 3.7


def test_record_autonomous_run_detects_warning():
    o = Orchestrator()
    result = {
        "analyses": {
            "market": {"status": "ok"},
            "technical": {"status": "ok"},
            "fundamental": {"status": "ok"},
            "news": {"status": "news analysis skipped (no API key)"},
            "risk": {"status": "ok"},
            "portfolio": {"status": "ok"},
            "execution": {"status": "execution analysis ready", "action": "hold"},
        }
    }
    o._record_autonomous_run("RUN-2", "AAPL", 2.0, result)

    status = o.get_autonomous_status()
    assert status["warnings"] == 1
    assert status["successful"] == 0
    assert "News: news analysis skipped (no API key)" in status["recent_runs"][0]["warnings"]


def test_record_autonomous_run_detects_error():
    o = Orchestrator()
    result = {
        "analyses": {
            "market": {"status": "error"},
            "technical": {"status": "error"},
            "fundamental": {"status": "ok"},
            "news": {"status": "ok"},
            "risk": {"status": "ok"},
            "portfolio": {"status": "ok"},
            "execution": {"status": "insufficient_data", "action": "hold"},
        }
    }
    o._record_autonomous_run("RUN-3", "AAPL", 1.0, result)

    status = o.get_autonomous_status()
    assert status["errors"] == 1
    assert status["hold_count"] == 1


def test_recent_runs_capped_at_50():
    o = Orchestrator()
    result = {"analyses": {"execution": {"status": "ok", "action": "hold"}}}
    for i in range(60):
        o._record_autonomous_run(f"RUN-{i}", "AAPL", 1.0, result)

    status = o.get_autonomous_status()
    assert len(status["recent_runs"]) == 50
    assert status["runs_today"] == 60  # counter keeps counting even past the capped list


def test_start_and_stop_autonomous_lifecycle(monkeypatch):
    o = Orchestrator()

    def fake_analyze(symbol, auto_execute=False):
        return {
            "run_id": f"RUN-{symbol}",
            "analyses": {"execution": {"status": "execution analysis ready", "action": "hold"}},
        }

    monkeypatch.setattr(o, "analyze_symbol", fake_analyze)

    o.start_autonomous(["AAPL"], interval_seconds=2)
    try:
        for _ in range(50):
            if o.get_autonomous_status()["runs_today"] >= 1:
                break
            time.sleep(0.1)

        status = o.get_autonomous_status()
        assert status["status"] == "running"
        assert status["symbols"] == ["AAPL"]
        assert status["interval_seconds"] == 2
        assert status["runs_today"] >= 1
        assert status["successful"] >= 1
    finally:
        o.stop_autonomous()

    status = o.get_autonomous_status()
    assert status["status"] == "stopped"
    assert status["next_run_at"] is None
