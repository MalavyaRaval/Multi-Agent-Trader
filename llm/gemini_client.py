"""
llm/gemini_client.py

Single source of truth for constructing the Gemini client and for the
Gemini "interactions" tool-calling loop. Previously this client-construction
snippet and the tool-calling loop were each copy-pasted across
trading_agent.py, market_data_agent.py, memory/reasoning.py, and
memory/reflections.py.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from google import genai

from config import GEMINI_API_KEY

MODEL_NAME = "gemini-3.1-flash-lite"
DEFAULT_MAX_TOOL_ROUNDS = 8

logger = logging.getLogger(__name__)


def get_gemini_client() -> Optional[genai.Client]:
    """Return a Gemini client, or None if GEMINI_API_KEY is not configured.

    Not cached: constructing a client is cheap local setup (no network I/O),
    and caching a None result would keep every caller stuck on "unconfigured"
    even after a key becomes available later in the process's lifetime.
    """
    if not GEMINI_API_KEY:
        return None
    try:
        return genai.Client(api_key=GEMINI_API_KEY)
    except Exception as exc:
        logger.warning("Could not initialize Gemini client: %s", exc)
        return None


def safe_generate(client: Optional[genai.Client], prompt: str, model: str = MODEL_NAME) -> Optional[str]:
    """Call Gemini's generate_content and return the response text, or None on any failure.

    Callers that need to fall back to a generic message on None still get one exception
    logged here, so a real failure (bad key, quota, network) is diagnosable in server
    logs even though the caller only sees None, not the exception.
    """
    if client is None:
        return None
    try:
        response = client.models.generate_content(model=model, contents=prompt)
        text = response.text if response else None
        return text.strip() if text else None
    except Exception as exc:
        logger.warning("Gemini generate_content failed: %s", exc)
        return None


def run_tool_loop(
    client: Optional[genai.Client],
    user_text: str,
    previous_interaction_id: Optional[str],
    *,
    tool_impls: Dict[str, Callable[..., Any]],
    tool_declarations: List[Dict[str, Any]],
    system_instruction: str,
    model_name: str = MODEL_NAME,
    max_rounds: int = DEFAULT_MAX_TOOL_ROUNDS,
    is_error: Callable[[Any], bool] = lambda result: isinstance(result, dict) and bool(
        result.get("error") or result.get("status") == "error"
    ),
    not_configured_message: str = "(Gemini API key not configured.)",
) -> Tuple[str, Optional[str]]:
    """
    Run one turn of a Gemini "interactions" tool-calling conversation, dispatching
    any requested function calls through tool_impls and feeding results back until
    Gemini returns final text (or max_rounds is hit).

    Returns (response_text, interaction_id) so the caller can keep the conversation
    going on the next turn.
    """
    if client is None:
        return not_configured_message, previous_interaction_id

    kwargs = dict(
        model=model_name,
        input=user_text,
        tools=tool_declarations,
        system_instruction=system_instruction,
    )
    if previous_interaction_id:
        kwargs["previous_interaction_id"] = previous_interaction_id

    try:
        interaction = client.interactions.create(**kwargs)
    except Exception as e:
        return f"(Gemini API error: {e})", previous_interaction_id

    for _ in range(max_rounds):
        fn_calls = [s for s in interaction.steps if s.type == "function_call"]
        if not fn_calls:
            break

        results_input = []
        for step in fn_calls:
            fn = tool_impls.get(step.name)
            if fn is None:
                result, had_error = {"error": f"Unknown tool '{step.name}'"}, True
            else:
                try:
                    result = fn(**step.arguments)
                    had_error = is_error(result)
                except Exception as e:
                    result, had_error = {"error": str(e)}, True

            results_input.append(
                {
                    "type": "function_result",
                    "name": step.name,
                    "call_id": step.id,
                    "result": [{"type": "text", "text": json.dumps(result)}],
                    "is_error": had_error,
                }
            )

        try:
            interaction = client.interactions.create(
                model=model_name,
                input=results_input,
                tools=tool_declarations,
                system_instruction=system_instruction,
                previous_interaction_id=interaction.id,
            )
        except Exception as e:
            return f"(Gemini API error while sending tool result: {e})", interaction.id

    return (interaction.output_text or "(no response text)"), interaction.id
