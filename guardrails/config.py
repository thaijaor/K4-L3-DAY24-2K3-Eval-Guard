"""NeMo Guardrails custom configuration and provider registration."""

from __future__ import annotations

import os
from langchain_openai import ChatOpenAI
from nemoguardrails.llm.providers import register_llm_provider

from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, _IS_VERTEX


class VertexChatOpenAI(ChatOpenAI):
    """ChatOpenAI customized for Vertex AI OpenAI-compatible endpoint with x-goog-api-key header."""

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


def init(app):
    """Called by NeMo LLMRails during initialization."""
    if hasattr(app, "config") and hasattr(app.config, "models"):
        for m in app.config.models:
            if getattr(m, "type", None) == "main":
                m.model = OPENAI_MODEL

    if _IS_VERTEX:
        register_llm_provider("openai", VertexChatOpenAI)
