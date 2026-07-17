from __future__ import annotations

import os

from .base import ModelProvider, ProviderError, ProviderResponse
from .http import post_json


class OpenAICompatibleProvider(ModelProvider):
    name = "openai"

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        if not self.api_key:
            raise ProviderError("OPENAI_API_KEY is not configured")

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
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        data = post_json(
            f"{self.base_url}/chat/completions",
            payload,
            {"Authorization": f"Bearer {self.api_key}"},
        )
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("OpenAI-compatible response did not contain message content") from exc
        usage = data.get("usage") or {}
        return ProviderResponse(
            text=text,
            model=data.get("model", model),
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
        )


def _model_for_role(role: str) -> str:
    role_key = {
        "ceo": "ORGMIND_CEO_MODEL",
        "reviewer": "ORGMIND_REVIEWER_MODEL",
        "integrator": "ORGMIND_CEO_MODEL",
    }.get(role, "ORGMIND_WORKER_MODEL")
    return os.getenv(role_key, "").strip()

