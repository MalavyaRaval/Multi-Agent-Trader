import json
from pathlib import Path

from observability.run_tracker import RunTracker


def test_run_tracker_creates_run_id_and_records_event(tmp_path):
    tracker = RunTracker(base_dir=tmp_path)

    run = tracker.start_run("AAPL")

    assert run["run_id"].startswith("RUN-")
    assert run["symbol"] == "AAPL"
    assert run["status"] == "running"

    event = tracker.emit_event(
        "MarketAgent",
        "api_call",
        provider="alpaca",
        endpoint="historical_bars",
        symbol="AAPL",
        status="success",
        duration_ms=241,
        records=250,
        feed="iex",
    )

    assert event["run_id"] == run["run_id"]
    assert event["event"] == "api_call"

    artifact = tmp_path / f"{run['run_id']}.jsonl"
    assert artifact.exists()
    lines = artifact.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 2

    payload = json.loads(lines[0])
    assert payload["run_id"] == run["run_id"]

    summary = tracker.summary()
    assert summary["run_id"] == run["run_id"]
    assert summary["event_count"] >= 1


def test_api_call_inspector_returns_trace_events(tmp_path):
    """Uses an isolated RunTracker (tmp_path) instead of the orchestrator's
    real one -- the original version of this test wrote directly into the
    repo's data/observability/ directory on every run."""
    from app import app

    orchestrator = __import__("app", fromlist=["orchestrator"]).orchestrator
    original_tracker = orchestrator.run_tracker
    orchestrator.run_tracker = RunTracker(base_dir=tmp_path)
    try:
        with app.test_client() as client:
            with app.app_context():
                run_id = "RUN-TEST-API-INSPECTOR"
                orchestrator.run_tracker.start_run("AAPL", run_id=run_id)
                orchestrator.run_tracker.emit_event(
                    "MarketAgent",
                    "api_call",
                    run_id=run_id,
                    provider="alpaca",
                    endpoint="historical_bars",
                    symbol="AAPL",
                    status="success",
                    duration_ms=241,
                    records=250,
                    feed="iex",
                )
                orchestrator.run_tracker.emit_event(
                    "FinnhubAgent",
                    "api_call",
                    run_id=run_id,
                    provider="finnhub",
                    endpoint="quote",
                    symbol="AAPL",
                    status="success",
                    duration_ms=320,
                    records=1,
                )

                response = client.get(f"/api/api_calls?run_id={run_id}")
                assert response.status_code == 200
                payload = response.get_json()
                assert payload["run_id"] == run_id
                assert payload["count"] >= 2
                assert any(call["provider"] == "alpaca" for call in payload["calls"])
                assert any(call["endpoint"] == "historical_bars" for call in payload["calls"])
    finally:
        orchestrator.run_tracker = original_tracker
