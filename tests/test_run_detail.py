"""
Tests for PHASES_PLAN.md Phase 10 -- Run Detail Page (now backed by Phase 11's
RunStore). Each Orchestrator gets its own temp-file RunStore so tests don't
read/write the real data/trading_system.db.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from data.run_store import RunStore
from observability.run_tracker import RunTracker
from orchestrator import Orchestrator


def _isolated_orchestrator(tmpdir):
    o = Orchestrator()
    o.run_store = RunStore(db_path=str(Path(tmpdir) / "test.db"))
    o.run_tracker = RunTracker(base_dir=tmpdir)
    return o


def _fake_result(run_id="RUN-TEST-AAPL", symbol="AAPL", action="buy"):
    return {
        "run_id": run_id,
        "session_id": run_id,
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
                "strategy_votes": [{"strategy": "momentum", "decision": "buy", "confidence": 0.7, "reason": "strong"}],
                "decision_explanation": {"action": action, "agent_reasons": ["RSI oversold"]},
                "score_breakdown": {"combined_score": 0.5},
                "detailed_reasoning": {"executive_summary": "Looks good"},
            },
        },
        "auto_trade": None,
        "messages": [{"from": "orchestrator", "message": "hello"}],
        "observability": {"run_id": run_id, "event_count": 3},
    }


def test_get_run_detail_returns_none_for_unknown_run():
    with tempfile.TemporaryDirectory() as tmp:
        o = _isolated_orchestrator(tmp)
        assert o.get_run_detail("RUN-DOES-NOT-EXIST") is None


def test_cache_and_retrieve_run_result():
    with tempfile.TemporaryDirectory() as tmp:
        o = _isolated_orchestrator(tmp)
        result = _fake_result()
        o.run_store.save_run(result, events=[])

        detail = o.get_run_detail("RUN-TEST-AAPL")
        assert detail is not None
        assert detail["overview"]["run_id"] == "RUN-TEST-AAPL"
        assert detail["overview"]["symbol"] == "AAPL"
        assert detail["overview"]["status"] == "completed"


def test_run_detail_has_all_14_sections():
    with tempfile.TemporaryDirectory() as tmp:
        o = _isolated_orchestrator(tmp)
        result = _fake_result()
        o.run_store.save_run(result, events=[])
        detail = o.get_run_detail("RUN-TEST-AAPL")

        for key in (
            "overview", "api_calls", "market_data", "technical_analysis",
            "fundamentals", "news", "risk", "portfolio", "strategies",
            "execution", "order", "errors", "timing", "decision_trace",
        ):
            assert key in detail


def test_run_detail_strategies_and_decision_trace():
    with tempfile.TemporaryDirectory() as tmp:
        o = _isolated_orchestrator(tmp)
        result = _fake_result()
        o.run_store.save_run(result, events=[])
        detail = o.get_run_detail("RUN-TEST-AAPL")

        assert detail["strategies"][0]["strategy"] == "momentum"
        assert detail["execution"]["action"] == "buy"
        assert detail["decision_trace"]["score_breakdown"]["combined_score"] == 0.5


def test_run_detail_detects_errors():
    with tempfile.TemporaryDirectory() as tmp:
        o = _isolated_orchestrator(tmp)
        result = _fake_result()
        result["analyses"]["news"] = {"status": "error", "error": "Finnhub down"}
        o.run_store.save_run(result, events=[])
        detail = o.get_run_detail("RUN-TEST-AAPL")

        assert len(detail["errors"]) == 1
        assert detail["errors"][0]["stage"] == "news"
        assert detail["errors"][0]["message"] == "Finnhub down"
        assert detail["errors"][0]["agent"] == "NewsAgent"
        assert detail["errors"][0]["provider"] == "Finnhub"


def test_list_recent_runs():
    with tempfile.TemporaryDirectory() as tmp:
        o = _isolated_orchestrator(tmp)
        for i in range(3):
            result = _fake_result(run_id=f"RUN-{i}", action="hold" if i else "buy")
            result["started_at"] = f"2026-08-27T00:0{i}:00+00:00"
            o.run_store.save_run(result, events=[])

        runs = o.list_recent_runs(limit=10)
        assert len(runs) == 3
        assert runs[0]["run_id"] == "RUN-2"  # newest first


def test_analyze_symbol_persists_run(monkeypatch):
    """The real analyze_symbol() path should persist its own result too."""
    with tempfile.TemporaryDirectory() as tmp:
        o = _isolated_orchestrator(tmp)
        result = o.analyze_symbol("AAPL")
        run_id = result["run_id"]

        detail = o.get_run_detail(run_id)
        assert detail is not None
        assert detail["overview"]["symbol"] == "AAPL"


# ---------------------------------------------------------------------------
# Flask route smoke tests (use the app's real orchestrator singleton, but
# with its run_store/run_tracker swapped for isolated temp-dir instances so
# these smoke tests don't pollute the real data/trading_system.db or write
# real .jsonl trace files under data/observability/).
# ---------------------------------------------------------------------------

def test_api_run_detail_404_for_unknown_run():
    import app as app_module
    client = app_module.app.test_client()
    resp = client.get("/api/run/RUN-DOES-NOT-EXIST-12345")
    assert resp.status_code == 404


def test_api_runs_list_endpoint():
    import app as app_module
    client = app_module.app.test_client()
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    assert "runs" in resp.get_json()


def test_run_detail_page_renders_not_found():
    import app as app_module
    client = app_module.app.test_client()
    resp = client.get("/run/RUN-DOES-NOT-EXIST-12345")
    assert resp.status_code == 200
    assert b"Run not found" in resp.data


def test_run_detail_page_renders_real_run(tmp_path):
    import app as app_module

    orchestrator = app_module.orchestrator
    original_run_store = orchestrator.run_store
    original_run_tracker = orchestrator.run_tracker
    orchestrator.run_store = RunStore(db_path=str(tmp_path / "test.db"))
    orchestrator.run_tracker = RunTracker(base_dir=tmp_path)
    try:
        result = orchestrator.analyze_symbol("AAPL")
        client = app_module.app.test_client()
        resp = client.get(f"/run/{result['run_id']}")
        assert resp.status_code == 200
        assert b"Overview" in resp.data
        assert b"Decision Trace" in resp.data
    finally:
        orchestrator.run_store = original_run_store
        orchestrator.run_tracker = original_run_tracker
