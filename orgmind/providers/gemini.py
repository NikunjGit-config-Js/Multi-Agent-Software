from __future__ import annotations

import os
import urllib.parse

from .base import ModelProvider, ProviderError, ProviderResponse
from .http import post_json


class GeminiProvider(ModelProvider):
    """Gemini Developer API adapter using only Python's standard library."""

    name = "gemini"

    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model = os.getenv("ORGMIND_GEMINI_MODEL", "gemini-2.5-flash").strip()
        self.base_url = os.getenv(
            "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
        ).rstrip("/")
        if not self.api_key:
            raise ProviderError("GEMINI_API_KEY is not configured")
        if not self.model:
            raise ProviderError("ORGMIND_GEMINI_MODEL is empty")

    def complete(
        self,
        *,
        role: str,
        system: str,
        prompt: str,
        json_mode: bool = False,
    ) -> ProviderResponse:
        del role  # One stable model is used for all roles in the first Gemini release.
        generation_config: dict[str, object] = {
            "temperature": 0.2,
            "maxOutputTokens": 8192,
        }
        if json_mode:
            generation_config["responseMimeType"] = "application/json"

        safe_model = urllib.parse.quote(self.model, safe="-_.")
        data = post_json(
            f"{self.base_url}/models/{safe_model}:generateContent",
            {
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": generation_config,
            },
            {"x-goog-api-key": self.api_key},
        )
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "\n".join(part.get("text", "") for part in parts if part.get("text"))
        except (KeyError, IndexError, TypeError) as exc:
            block_reason = (data.get("promptFeedback") or {}).get("blockReason")
            suffix = f" ({block_reason})" if block_reason else ""
            raise ProviderError(f"Gemini returned no text content{suffix}") from exc
        if not text.strip():
            raise ProviderError("Gemini returned an empty response")

        usage = data.get("usageMetadata") or {}
        return ProviderResponse(
            text=text,
            model=self.model,
            input_tokens=int(usage.get("promptTokenCount", 0)),
            output_tokens=int(usage.get("candidatesTokenCount", 0)),
        )
