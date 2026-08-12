"""
scripts/test_gemini.py

Phase 0 - Gemini baseline health check.

Tests:
- API key presence
- client initialization
- model availability
- simple generation request
- response latency
- timeout behavior

This test performs one small generation request.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict

from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = os.getenv(
    "GEMINI_HEALTH_MODEL",
    "gemini-2.5-flash",
)

PROMPT = "Reply with exactly: GEMINI_HEALTH_OK"


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
        "service": "gemini",
        "model": MODEL_NAME,
        "checks": [],
    }

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        report["checks"].append(
            _check(
                "credentials",
                "FAIL",
                "GEMINI_API_KEY is missing.",
            )
        )
        report["status"] = "FAIL"
        return report

    report["checks"].append(
        _check(
            "credentials",
            "PASS",
            "GEMINI_API_KEY is present.",
        )
    )

    try:
        from google import genai

        client = genai.Client(api_key=api_key)

        report["checks"].append(
            _check(
                "client_initialization",
                "PASS",
                "Google Gen AI client initialized.",
            )
        )

    except Exception as exc:
        report["checks"].append(
            _check(
                "client_initialization",
                "FAIL",
                str(exc),
                error_type=type(exc).__name__,
            )
        )

        report["status"] = "FAIL"
        return report

    # ---------------------------------------------------------
    # Model availability
    # ---------------------------------------------------------

    try:
        started = time.perf_counter()

        models = list(client.models.list())

        latency_ms = (time.perf_counter() - started) * 1000

        model_names = [
            getattr(model, "name", "")
            for model in models
        ]

        requested_model = (
            MODEL_NAME
            if MODEL_NAME.startswith("models/")
            else f"models/{MODEL_NAME}"
        )

        available = (
            requested_model in model_names
            or MODEL_NAME in model_names
            or any(
                name.endswith(f"/{MODEL_NAME}")
                for name in model_names
            )
        )

        if available:
            report["checks"].append(
                _check(
                    "model_availability",
                    "PASS",
                    f"Model {MODEL_NAME} is available.",
                    latency_ms=latency_ms,
                    models_returned=len(models),
                )
            )
        else:
            report["checks"].append(
                _check(
                    "model_availability",
                    "WARNING",
                    f"Model {MODEL_NAME} was not found in the returned model list.",
                    latency_ms=latency_ms,
                    models_returned=len(models),
                )
            )

    except Exception as exc:
        report["checks"].append(
            _check(
                "model_availability",
                "WARNING",
                f"Could not enumerate models: {exc}",
                error_type=type(exc).__name__,
            )
        )

    # ---------------------------------------------------------
    # Simple request
    # ---------------------------------------------------------

    try:
        started = time.perf_counter()

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=PROMPT,
        )

        latency_ms = (time.perf_counter() - started) * 1000

        response_text = getattr(response, "text", None)

        if not response_text:
            report["checks"].append(
                _check(
                    "simple_request",
                    "FAIL",
                    "Gemini returned an empty response.",
                    latency_ms=latency_ms,
                )
            )
        else:
            report["checks"].append(
                _check(
                    "simple_request",
                    "PASS",
                    "Gemini generation request succeeded.",
                    latency_ms=latency_ms,
                    response_preview=response_text[:100],
                )
            )

            report["checks"].append(
                _check(
                    "response_latency",
                    "PASS",
                    f"Gemini response received in {latency_ms:.0f} ms.",
                    latency_ms=latency_ms,
                )
            )

    except Exception as exc:
        report["checks"].append(
            _check(
                "simple_request",
                "FAIL",
                str(exc),
                error_type=type(exc).__name__,
            )
        )

    # ---------------------------------------------------------
    # Timeout handling
    #
    # We do NOT intentionally make a failing request here.
    # The test records whether the installed SDK exposes a
    # configurable HTTP timeout.
    # ---------------------------------------------------------

    timeout_supported = False

    try:
        from google.genai import types

        timeout_supported = hasattr(
            types,
            "HttpOptions",
        )
    except Exception:
        pass

    report["checks"].append(
        _check(
            "timeout_handling",
            "PASS" if timeout_supported else "WARNING",
            (
                "Installed Gemini SDK exposes HttpOptions "
                "for HTTP timeout configuration."
                if timeout_supported
                else
                "Could not verify SDK timeout configuration."
            ),
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