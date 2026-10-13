"""NeMo Guardrails custom configuration and provider registration."""

from __future__ import annotations

import os
from langchain_openai import ChatOpenAI
from nemoguardrails.llm.providers import register_llm_provider

from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, _IS_VERTEX


class CustomChatOpenAI(ChatOpenAI):
    """ChatOpenAI customized for Gemini (Vertex AI / Google AI Studio) OpenAI-compatible endpoints."""

    def __init__(self, **kwargs):
        if _IS_VERTEX:
            kwargs.setdefault("api_key", "vertex-header-auth")
            kwargs.setdefault("base_url", OPENAI_BASE_URL)
            default_headers = kwargs.get("default_headers") or {}
            default_headers["x-goog-api-key"] = OPENAI_API_KEY
            kwargs["default_headers"] = default_headers
        else:
            if OPENAI_API_KEY:
                kwargs.setdefault("api_key", OPENAI_API_KEY)
            if OPENAI_BASE_URL:
                kwargs.setdefault("base_url", OPENAI_BASE_URL)
        super().__init__(**kwargs)

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        if "max_tokens" in payload and payload["max_tokens"] is not None and payload["max_tokens"] < 16:
            payload["max_tokens"] = 16
        return payload

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        import asyncio
        for attempt in range(5):
            try:
                return await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
            except Exception as e:
                err_str = str(e).lower()
                if ("429" in err_str or "resource_exhausted" in err_str or "quota" in err_str) and attempt < 4:
                    wait_time = 35.0
                    print(f"\n[RateLimit 429] Waiting {wait_time}s before retry {attempt + 1}/4...")
                    await asyncio.sleep(wait_time)
                else:
                    raise

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        import time
        for attempt in range(5):
            try:
                return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
            except Exception as e:
                err_str = str(e).lower()
                if ("429" in err_str or "resource_exhausted" in err_str or "quota" in err_str) and attempt < 4:
                    wait_time = 35.0
                    print(f"\n[RateLimit 429] Waiting {wait_time}s before retry {attempt + 1}/4...")
                    time.sleep(wait_time)
                else:
                    raise


def init(app):
    """Called by NeMo LLMRails during initialization."""
    if hasattr(app, "config") and hasattr(app.config, "models"):
        for m in app.config.models:
            if getattr(m, "type", None) == "main":
                m.model = OPENAI_MODEL

    register_llm_provider("openai", CustomChatOpenAI)
