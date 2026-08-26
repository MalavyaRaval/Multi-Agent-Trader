"""
scripts/_health_check_common.py

Shared helpers for the Phase 0 baseline health-check scripts
(test_alpaca_data.py, test_finnhub.py, test_gemini.py, test_indicators.py,
test_pipeline.py, system_health_check.py). Each of those scripts used to
define its own copy of the check-result builder, the FAIL/WARNING/PASS
status rollup, the CLI entry point, and (in some files) a perf_counter-based
timing wrapper.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any, Callable, Dict, List, Tuple

from observability.run_tracker import now_iso


def make_check(name: str, status: str, message: str = "", **extra: Any) -> Dict[str, Any]:
    """Build one health-check result entry: {name, status, message, checked_at, ...extra}."""
    result = {
        "name": name,
        "status": status,
        "message": message,
        "checked_at": now_iso(),
    }
    result.update(extra)
    return result


def timed(func: Callable[[], Any]) -> Tuple[Any, float, Any]:
    """Call func(), returning (value, latency_ms, error). error is None on success."""
    started = time.perf_counter()
    try:
        value = func()
        return value, (time.perf_counter() - started) * 1000, None
    except Exception as exc:
        return None, (time.perf_counter() - started) * 1000, exc


def status_from_counts(fail_count: int, warning_count: int) -> str:
    """The shared FAIL > WARNING > PASS priority rule."""
    if fail_count > 0:
        return "FAIL"
    if warning_count > 0:
        return "WARNING"
    return "PASS"


def finalize_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """Roll up report["checks"] into report["status"] and stamp report["finished_at"]."""
    checks: List[Dict[str, Any]] = report.get("checks", [])
    fail_count = sum(1 for c in checks if c.get("status") == "FAIL")
    warning_count = sum(1 for c in checks if c.get("status") == "WARNING")
    report["status"] = status_from_counts(fail_count, warning_count)
    report["finished_at"] = now_iso()
    return report


def run_health_check_cli(run_func: Callable[[], Dict[str, Any]]) -> None:
    """Standard CLI entry point: run the check, print the JSON report, exit 1 on FAIL."""
    # Some terminals (notably the default Windows console) use a legacy encoding
    # that can't represent characters a check message might contain; degrade to
    # '?' instead of crashing the whole health check on a print() call.
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass

    report = run_func()
    print(json.dumps(report, indent=2, default=str))
    if report.get("status") == "FAIL":
        raise SystemExit(1)
