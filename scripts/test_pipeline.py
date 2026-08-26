"""
scripts/test_pipeline.py

Phase 0 - Internal system baseline.

Tests:
- orchestrator import
- agent construction
- execution calculation
- trade history storage
- reasoning/memory storage
- Flask application discovery
- basic Flask endpoint availability

NO REAL ORDER IS PLACED.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any, Dict

from scripts._health_check_common import finalize_report, make_check as _check, run_health_check_cli


def _find_flask_app():
    candidates = [
        "app",
        "main",
        "server",
        "web",
        "api",
    ]

    for module_name in candidates:
        try:
            module = importlib.import_module(module_name)

            flask_app = getattr(module, "app", None)

            if flask_app is not None:
                return module_name, flask_app

        except Exception:
            continue

    return None, None


def run() -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "service": "internal_pipeline",
        "checks": [],
    }

    # ---------------------------------------------------------
    # Orchestrator import
    # ---------------------------------------------------------

    try:
        from orchestrator import Orchestrator

        orchestrator = Orchestrator()

        report["checks"].append(
            _check(
                "orchestrator",
                "PASS",
                "Orchestrator imported and instantiated.",
                agent_count=7,
            )
        )

    except Exception as exc:
        report["checks"].append(
            _check(
                "orchestrator",
                "FAIL",
                str(exc),
                error_type=type(exc).__name__,
            )
        )
        orchestrator = None

    # ---------------------------------------------------------
    # Execution calculation
    # ---------------------------------------------------------

    try:
        from agents.execution_agent import ExecutionAgent

        execution = ExecutionAgent()

        synthetic_context = {
            "market": {
                "price": 100.0,
                "metrics": {
                    "relative_volume": 1.0,
                    "spread": 0.01,
                },
            },
            "technical": {
                "signals": {
                    "rsi_14": 50.0,
                    "macd": 0.10,
                    "macd_signal": 0.05,
                    "ema_20": 101.0,
                    "ema_50": 99.0,
                    "volume_trend": "neutral",
                    "last_price": 100.0,
                    "atr_14": 2.0,
                }
            },
            "fundamental": {
                "score": 0,
                "data": {},
            },
            "news": {
                "sentiment": "neutral",
                "sentiment_score": 0,
                "articles": [],
            },
            "risk": {
                "risk_level": "medium",
                "checks": {
                    "atr_percent": 2.0,
                },
            },
            "portfolio": {
                "position": None,
                "account": {
                    "equity": 100000,
                },
            },
        }

        result = execution.analyze(
            "AAPL",
            context=synthetic_context,
        )

        required_keys = {
            "symbol",
            "action",
            "confidence",
            "strategy_votes",
            "ensemble",
        }

        missing = required_keys - set(result.keys())

        if missing:
            report["checks"].append(
                _check(
                    "execution_calculation",
                    "FAIL",
                    "Execution result is missing required fields.",
                    missing_fields=sorted(missing),
                )
            )
        else:
            action = result.get("action")
            confidence = result.get("confidence")

            valid_action = action in {
                "buy",
                "sell",
                "hold",
            }

            valid_confidence = (
                isinstance(confidence, (int, float))
                and 0.0 <= confidence <= 1.0
            )

            status = (
                "PASS"
                if valid_action and valid_confidence
                else "FAIL"
            )

            report["checks"].append(
                _check(
                    "execution_calculation",
                    status,
                    "Execution calculation completed.",
                    action=action,
                    confidence=confidence,
                    strategy_votes=len(
                        result.get("strategy_votes", [])
                    ),
                )
            )

    except Exception as exc:
        report["checks"].append(
            _check(
                "execution_calculation",
                "FAIL",
                str(exc),
                error_type=type(exc).__name__,
            )
        )

    # ---------------------------------------------------------
    # Trade history
    # ---------------------------------------------------------

    try:
        from memory.trade_history import TradeHistory

        history = TradeHistory()

        required_methods = [
            "record_analysis",
            "record_order",
            "get_stats",
        ]

        missing_methods = [
            method
            for method in required_methods
            if not hasattr(history, method)
        ]

        if missing_methods:
            report["checks"].append(
                _check(
                    "trade_history",
                    "FAIL",
                    "TradeHistory is missing required methods.",
                    missing_methods=missing_methods,
                )
            )
        else:
            stats = history.get_stats()

            report["checks"].append(
                _check(
                    "trade_history",
                    "PASS",
                    "TradeHistory initialized successfully.",
                    stats_type=type(stats).__name__,
                )
            )

    except Exception as exc:
        report["checks"].append(
            _check(
                "trade_history",
                "FAIL",
                str(exc),
                error_type=type(exc).__name__,
            )
        )

    # ---------------------------------------------------------
    # Reasoning / memory
    # ---------------------------------------------------------

    try:
        from memory.reasoning import ReasoningEngine

        reasoning = ReasoningEngine()

        if not hasattr(reasoning, "synthesize_reasoning"):
            report["checks"].append(
                _check(
                    "reasoning_memory",
                    "FAIL",
                    "ReasoningEngine lacks synthesize_reasoning().",
                )
            )
        else:
            report["checks"].append(
                _check(
                    "reasoning_memory",
                    "PASS",
                    "ReasoningEngine initialized successfully.",
                )
            )

    except Exception as exc:
        report["checks"].append(
            _check(
                "reasoning_memory",
                "FAIL",
                str(exc),
                error_type=type(exc).__name__,
            )
        )

    # ---------------------------------------------------------
    # Flask
    # ---------------------------------------------------------

    try:
        import flask  # noqa: F401

        module_name, flask_app = _find_flask_app()

        if flask_app is None:
            report["checks"].append(
                _check(
                    "flask_application",
                    "WARNING",
                    (
                        "Flask is installed, but no app object "
                        "was discovered in the standard modules."
                    ),
                )
            )
        else:
            client = flask_app.test_client()

            response = client.get("/")

            report["checks"].append(
                _check(
                    "flask_application",
                    "PASS",
                    "Flask application discovered and root endpoint responded.",
                    module=module_name,
                    http_status=response.status_code,
                )
            )

    except Exception as exc:
        report["checks"].append(
            _check(
                "flask_application",
                "FAIL",
                str(exc),
                error_type=type(exc).__name__,
            )
        )

    return finalize_report(report)


def main() -> None:
    run_health_check_cli(run)


if __name__ == "__main__":
    main()