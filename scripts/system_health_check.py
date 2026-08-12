"""
scripts/system_health_check.py

Phase 0 master system-health runner.

Runs:
    test_alpaca_data
    test_finnhub
    test_gemini
    test_indicators
    test_pipeline

Writes:
    data/system_health_latest.json

Usage:

    python scripts/system_health_check.py

or:

    python -m scripts.system_health_check
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

# Allow execution with:
# python scripts/system_health_check.py
ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts import test_alpaca_data
from scripts import test_finnhub
from scripts import test_gemini
from scripts import test_indicators
from scripts import test_pipeline


OUTPUT_FILE = ROOT_DIR / "data" / "system_health_latest.json"


def run_test(module) -> Dict[str, Any]:
    started = datetime.now(timezone.utc)

    try:
        result = module.run()

        if not isinstance(result, dict):
            return {
                "status": "FAIL",
                "error": "Test module returned a non-dictionary result.",
            }

        result["started_at"] = result.get(
            "started_at",
            started.isoformat(),
        )

        return result

    except Exception as exc:
        return {
            "status": "FAIL",
            "error": str(exc),
            "error_type": type(exc).__name__,
            "started_at": started.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }


def _count_checks(section: Dict[str, Any]) -> Dict[str, int]:
    checks = section.get("checks", [])

    return {
        "pass": sum(
            1 for check in checks
            if check.get("status") == "PASS"
        ),
        "warning": sum(
            1 for check in checks
            if check.get("status") == "WARNING"
        ),
        "fail": sum(
            1 for check in checks
            if check.get("status") == "FAIL"
        ),
    }


def build_report() -> Dict[str, Any]:
    started_at = datetime.now(timezone.utc)

    sections = {
        "alpaca": run_test(test_alpaca_data),
        "finnhub": run_test(test_finnhub),
        "gemini": run_test(test_gemini),
        "indicators": run_test(test_indicators),
        "pipeline": run_test(test_pipeline),
    }

    summary = {
        "services": len(sections),
        "pass": 0,
        "warning": 0,
        "fail": 0,
        "checks": 0,
    }

    for section in sections.values():
        counts = _count_checks(section)

        summary["pass"] += counts["pass"]
        summary["warning"] += counts["warning"]
        summary["fail"] += counts["fail"]

        summary["checks"] += sum(counts.values())

    if summary["fail"] > 0:
        overall_status = "FAIL"
    elif summary["warning"] > 0:
        overall_status = "WARNING"
    else:
        overall_status = "PASS"

    report = {
        "phase": "phase_0_baseline_audit",
        "generated_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall_status,
        "symbol": test_alpaca_data.SYMBOL,
        "summary": summary,
        "services": sections,
    }

    return report


def save_report(report: Dict[str, Any]) -> None:
    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_file = OUTPUT_FILE.with_suffix(".tmp")

    temp_file.write_text(
        json.dumps(
            report,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    temp_file.replace(OUTPUT_FILE)


def print_summary(report: Dict[str, Any]) -> None:
    print()
    print("=" * 70)
    print("SYSTEM HEALTH — PHASE 0 BASELINE")
    print("=" * 70)

    for name, result in report["services"].items():
        status = result.get("status", "UNKNOWN")

        icon = {
            "PASS": "🟢",
            "WARNING": "🟡",
            "FAIL": "🔴",
        }.get(status, "⚪")

        print(
            f"{name:<18} {icon} {status}"
        )

    print("-" * 70)

    summary = report["summary"]

    print(
        f"Checks: {summary['checks']} | "
        f"PASS: {summary['pass']} | "
        f"WARNING: {summary['warning']} | "
        f"FAIL: {summary['fail']}"
    )

    print(
        f"Overall: {report['overall_status']}"
    )

    print()
    print(
        f"Report written to:\n{OUTPUT_FILE}"
    )

    print("=" * 70)
    print()


def main() -> None:
    report = build_report()

    save_report(report)
    print_summary(report)

    print(
        json.dumps(
            report,
            indent=2,
            default=str,
        )
    )

    if report["overall_status"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()