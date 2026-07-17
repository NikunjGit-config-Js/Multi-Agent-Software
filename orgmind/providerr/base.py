from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class ProviderError(RuntimeError):
    """A safe, user-presentable provider failure."""


@dataclass(slots=True)
class ProviderResponse:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0


class ModelProvider(ABC):
    name = "base"

    @abstractmethod
    def complete(
        self,
        *,
        role: str,
        system: str,
        prompt: str,
        json_mode: bool = False,
    ) -> ProviderResponse:
        raise NotImplementedError


def extract_json(text: str) -> dict[str, Any]:
    """Parse a model JSON response while tolerating fenced output."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError("Expected a JSON object")
        return value
    except (json.JSONDecodeError, ValueError):
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            value = json.loads(text[start : end + 1])
            if isinstance(value, dict):
                return value
        raise ProviderError("The model did not return the required JSON object")

