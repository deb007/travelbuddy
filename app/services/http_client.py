from __future__ import annotations

"""Lightweight HTTP client util with retry (T07.02).

Uses stdlib urllib to avoid adding external deps beyond existing httpx (but we keep
this separate and simple). Focus: GET JSON with limited retries.
"""
import json
import time
import urllib.request
import urllib.error
from typing import Any, Dict, Optional


class HttpError(Exception):
    pass


def get_json(
    url: str, *, timeout: float = 5.0, retries: int = 2, backoff: float = 0.5
) -> Dict[str, Any]:
    last_err: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:  # nosec B310
                if resp.status >= 400:
                    raise HttpError(f"HTTP {resp.status} for {url}")
                data = resp.read()
                return json.loads(data.decode("utf-8"))
        except (
            urllib.error.URLError,
            TimeoutError,
            HttpError,
            ValueError,
        ) as e:  # ValueError for JSON decode
            last_err = e
            if attempt == retries:
                break
            time.sleep(backoff * (2**attempt))
    raise HttpError(f"Failed to fetch JSON from {url}: {last_err}")
