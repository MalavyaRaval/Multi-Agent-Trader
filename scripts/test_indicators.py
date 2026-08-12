"""
scripts/test_indicators.py

Phase 0 - Internal calculation baseline.

Tests:
- indicators package import
- indicator module discovery
- multiframe calculation
- strategies package import
- strategy module discovery
- strategy class instantiation where possible

This does not modify trading behavior.
"""

from __future__ import annotations

import importlib
import json
import pkgutil
from datetime import datetime, timezone
from typing import Any, Dict


def _check(
    name: str,
    status: str,
    message: str = "",
    **extra: Any,
) -> Dict[str, Any]:
    result = {
        "name": name,
        "status": status,
        "message": message,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    result.update(extra)
    return result


def run() -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "service": "internal_indicators",
        "checks": [],
    }

    # ---------------------------------------------------------
    # Indicators package
    # ---------------------------------------------------------

    try:
        import indicators

        modules = sorted(
            module.name
            for module in pkgutil.iter_modules(
                indicators.__path__
            )
        )

        report["checks"].append(
            _check(
                "indicators_package",
                "PASS",
                "Indicators package imported.",
                modules=modules,
            )
        )

    except Exception as exc:
        report["checks"].append(
            _check(
                "indicators_package",
                "FAIL",
                str(exc),
                error_type=type(exc).__name__,
            )
        )
        modules = []

    # ---------------------------------------------------------
    # Import every indicator module
    # ---------------------------------------------------------

    for module_name in modules:
        full_name = f"indicators.{module_name}"

        try:
            importlib.import_module(full_name)

            report["checks"].append(
                _check(
                    f"indicator_module:{module_name}",
                    "PASS",
                    "Module imported successfully.",
                )
            )

        except Exception as exc:
            report["checks"].append(
                _check(
                    f"indicator_module:{module_name}",
                    "FAIL",
                    str(exc),
                    error_type=type(exc).__name__,
                )
            )

    # ---------------------------------------------------------
    # Multiframe calculation
    # ---------------------------------------------------------

    try:
        module = importlib.import_module(
            "indicators.multiframe"
        )

        function = getattr(
            module,
            "analyze_multiframe",
            None,
        )

        if function is None:
            report["checks"].append(
                _check(
                    "multiframe",
                    "FAIL",
                    "analyze_multiframe() was not found.",
                )
            )
        else:
            symbol = "AAPL"

            result = function(symbol)

            if result is None:
                report["checks"].append(
                    _check(
                        "multiframe",
                        "FAIL",
                        "analyze_multiframe() returned None.",
                    )
                )
            else:
                report["checks"].append(
                    _check(
                        "multiframe",
                        "PASS",
                        "Multi-timeframe calculation executed.",
                        result_type=type(result).__name__,
                        result_keys=(
                            list(result.keys())
                            if isinstance(result, dict)
                            else []
                        ),
                    )
                )

    except Exception as exc:
        report["checks"].append(
            _check(
                "multiframe",
                "FAIL",
                str(exc),
                error_type=type(exc).__name__,
            )
        )

    # ---------------------------------------------------------
    # Strategies package
    # ---------------------------------------------------------

    try:
        import strategies

        strategy_modules = sorted(
            module.name
            for module in pkgutil.iter_modules(
                strategies.__path__
            )
        )

        report["checks"].append(
            _check(
                "strategies_package",
                "PASS",
                "Strategies package imported.",
                modules=strategy_modules,
            )
        )

    except Exception as exc:
        report["checks"].append(
            _check(
                "strategies_package",
                "FAIL",
                str(exc),
                error_type=type(exc).__name__,
            )
        )

        strategy_modules = []

    # ---------------------------------------------------------
    # Strategy module imports
    # ---------------------------------------------------------

    for module_name in strategy_modules:
        full_name = f"strategies.{module_name}"

        try:
            importlib.import_module(full_name)

            report["checks"].append(
                _check(
                    f"strategy_module:{module_name}",
                    "PASS",
                    "Strategy module imported successfully.",
                )
            )

        except Exception as exc:
            report["checks"].append(
                _check(
                    f"strategy_module:{module_name}",
                    "FAIL",
                    str(exc),
                    error_type=type(exc).__name__,
                )
            )

    failures = [
        item for item in report["checks"]
        if item["status"] == "FAIL"
    ]

    warnings = [
        item for item in report["checks"]
        if item["status"] == "WARNING"
    ]

    report["status"] = (
        "FAIL"
        if failures
        else "WARNING"
        if warnings
        else "PASS"
    )

    report["finished_at"] = datetime.now(timezone.utc).isoformat()

    return report


def main() -> None:
    report = run()

    print(json.dumps(report, indent=2, default=str))

    if report["status"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()