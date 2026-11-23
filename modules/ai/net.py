"""Tiny HTTP helper on the standard library (no new dependency)."""
from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional


class AIError(RuntimeError):
    """A provider could not answer. `retryable` is True for rate limits and temporary server errors."""

    def __init__(self, message: str, retryable: bool = False, retry_after: float = 0.0, content_filtered: bool = False):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after            # seconds the server asked us to wait (0 = unknown)
        self.content_filtered = content_filtered  # the provider's safety filter refused THIS prompt (the provider itself is fine)


def http_request(url: str, *, data: Optional[bytes] = None, headers: Optional[dict] = None,
                 timeout: float = 90.0) -> bytes:
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read(600).decode("utf-8", "replace")
        except Exception:
            pass
        wait = re.search(r"retry after (\d+)\s*s", body, re.I)
        header = exc.headers.get("Retry-After") if exc.headers else None
        retry_after = float(wait.group(1)) if wait else (float(header) if header and header.isdigit() else 0.0)
        # Pollinations answers 402 FREE_LIMIT ("1 image every 45 seconds per IP") when you are too fast: wait and retry
        retry = exc.code in (408, 425, 429) or exc.code >= 500 or (exc.code == 402 and "FREE_LIMIT" in body)
        hint = " (rate limit: wait a little or register a free key)" if exc.code == 429 else ""
        raise AIError(f"HTTP {exc.code} from {urllib.parse.urlsplit(url).netloc}{hint} {body}".strip(), retry, retry_after,
                       content_filtered=("NSFW" in body.upper() or '"code":8007' in body)) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AIError(f"cannot reach {urllib.parse.urlsplit(url).netloc}: {getattr(exc, 'reason', exc)}", True) from exc
