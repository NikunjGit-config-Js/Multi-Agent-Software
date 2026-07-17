from __future__ import annotations

import os

from .base import ModelProvider, ProviderError, ProviderResponse
from .http import post_json


class AnthropicProvider(ModelProvider):
    name = "anthropic"

    def __init__(self) -> None:
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1").rstrip("/")
        if not self.api_key:
            raise ProviderError("ANTHROPIC_API_KEY is not configured")

    def complete(
        self,
        *,
        role: str,
        system: str,
        prompt: str,
        json_mode: bool = False,
    ) -> ProviderResponse:
        model = _model_for_role(role)
        if not model:
            raise ProviderError(f"No model configured for role '{role}'")
        if json_mode:
            system += "\nReturn only one valid JSON object with no Markdown fence."
        data = post_json(
            f"{self.base_url}/messages",
            {
                "model": model,
                "max_tokens": 3500,
                "temperature": 0.2,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            },
            {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        try:
            text = "\n".join(
                block.get("text", "")
                for block in data["content"]
                if block.get("type") == "text"
            )
        except (KeyError, TypeError) as exc:
            raise ProviderError("Anthropic response did not contain message content") from exc
        usage = data.get("usage") or {}
        return ProviderResponse(
            text=text,
            model=data.get("model", model),
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
        )


def _model_for_role(role: str) -> str:
    role_key = {
        "ceo": "ORGMIND_CEO_MODEL",
        "reviewer": "ORGMIND_REVIEWER_MODEL",
        "integrator": "ORGMIND_CEO_MODEL",
    }.get(role, "ORGMIND_WORKER_MODEL")
    return os.getenv(role_key, "").strip()

