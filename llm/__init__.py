"""Shared Gemini client + tool-calling loop used by chat-style agents."""
from llm.gemini_client import MODEL_NAME, get_gemini_client, safe_generate, run_tool_loop

__all__ = ["MODEL_NAME", "get_gemini_client", "safe_generate", "run_tool_loop"]
