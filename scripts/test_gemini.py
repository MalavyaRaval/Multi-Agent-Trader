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

import os
from typing import Any, Dict

from dotenv import load_dotenv

from scripts._health_check_common import finalize_report, make_check as _check, run_health_check_cli, timed

load_dotenv()

MODEL_NAME = os.getenv(
    "GEMINI_HEALTH_MODEL",
    "gemini-2.5-flash",
)

PROMPT = "Reply with exactly: GEMINI_HEALTH_OK"


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
        return finalize_report(report)

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

        return finalize_report(report)

    # ---------------------------------------------------------
    # Model availability
    # ---------------------------------------------------------

    models, latency_ms, error = timed(lambda: list(client.models.list()))

    if error is not None:
        report["checks"].append(
            _check(
                "model_availability",
                "WARNING",
                f"Could not enumerate models: {error}",
                error_type=type(error).__name__,
            )
        )
    else:
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

    # ---------------------------------------------------------
    # Simple request
    # ---------------------------------------------------------

    response, latency_ms, error = timed(
        lambda: client.models.generate_content(model=MODEL_NAME, contents=PROMPT)
    )

    if error is not None:
        report["checks"].append(
            _check(
                "simple_request",
                "FAIL",
                str(error),
                error_type=type(error).__name__,
            )
        )
    else:
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

    return finalize_report(report)


def main() -> None:
    run_health_check_cli(run)


if __name__ == "__main__":
    main()