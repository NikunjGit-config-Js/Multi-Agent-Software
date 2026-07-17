from __future__ import annotations

import os

from .anthropic import AnthropicProvider
from .base import ModelProvider, ProviderError
from .demo import DemoProvider
from .openai_compatible import OpenAICompatibleProvider


def build_provider(name: str) -> ModelProvider:
    if name == "demo":
        return DemoProvider()
    if name == "openai":
        return OpenAICompatibleProvider()
    if name == "anthropic":
        return AnthropicProvider()
    raise ProviderError(f"Unsupported provider: {name}")


def provider_readiness() -> dict[str, dict[str, object]]:
    return {
        "demo": {"ready": True, "label": "Demo workforce", "detail": "No API key required"},
        "openai": {
            "ready": bool(os.getenv("OPENAI_API_KEY", "").strip()),
            "label": "OpenAI-compatible",
            "detail": "Ready" if os.getenv("OPENAI_API_KEY", "").strip() else "Key not configured",
        },
        "anthropic": {
            "ready": bool(os.getenv("ANTHROPIC_API_KEY", "").strip()),
            "label": "Anthropic",
            "detail": "Ready" if os.getenv("ANTHROPIC_API_KEY", "").strip() else "Key not configured",
        },
    }

