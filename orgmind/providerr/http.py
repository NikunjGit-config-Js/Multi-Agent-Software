from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .base import ProviderError


def post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    *,
    timeout: int = 120,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")[:700]
        raise ProviderError(f"Provider returned HTTP {exc.code}: {raw}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"Could not reach model provider: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ProviderError("Provider returned an invalid JSON response") from exc

