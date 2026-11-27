"""Free image providers + the service that gives make_video one picture per scene.

PollinationsImage  online, no key (anonymous tier: 1 image per 45 s per IP, so 16 scenes take about 12 minutes; a free key removes the wait).
FolderImages       offline: pictures you made by hand on a free web tool (Google Flow, ImageFX, Gemini app, ...)
                   saved as <claim_id>.png in a folder. `export_kit` writes the prompts to paste there.
ArtService         disk cache (same prompt -> no new request), rate limit, and a circuit breaker: after two
                   failures in a row the remaining scenes fall back to the drawn infographic instead of waiting.

Prompts always ask for NO text in the picture: words and numbers on screen are drawn by code (S15).
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import os
import time
import urllib.parse
from pathlib import Path
from typing import Callable, Optional, Protocol

from PIL import Image

from modules.ai.net import AIError, http_request

STYLE = ("clean flat vector infographic illustration, plain white background, ONE centered subject with a wide "
         "empty margin on all sides (nothing touching the edges), limited palette of 3 to 4 soft pastel colors, "
         "simple bold shapes, no clutter, any tag, sign, dial or paper is plain and completely blank")
NEGATIVE = "no text, no letters, no numbers, no captions, no watermark, no logo"
IMAGE_CHOICES = ("off", "pollinations", "cloudflare", "folder")


# FLUX (the free Cloudflare model) ignores "no text" and prints the words of the prompt onto tags, dials and papers
# ("PRICE", "$550", "interest rate", "Tax"). Words and numbers on screen must come from code (S15), so objects that
# carry writing are swapped for objects that do not, and every digit / currency sign is dropped, BEFORE the request.
_SWAPS = [
    (r"\bprice[- ]?(?:tags?|labels?|stickers?)\b", "stack of coins"),
    (r"\b(?:dollar|euro|pound|dong)\s+signs?\b|\bcurrency\s+symbols?\b", "coin"),
    (r"\binterest[- ]rate\s+(?:dials?|gauges?|knobs?|meters?)\b", "round dial with tick marks only"),
    (r"\binterest[- ]rates?\b", "round dial"),
    (r"\b(?:tax|bank)\s+(?:forms?|documents?|papers?|bills?|returns?|statements?)\b", "coin purse"),
]
_DROP = re.compile(
    r"\b(?:receipts?|invoices?|contracts?|documents?|reports?|newspapers?|books?|posters?|banners?|signs?|signboards?|"
    r"billboards?|calendars?|labels?|captions?|barcodes?|qr codes?|screens?|monitors?|spreadsheets?|checklists?|"
    r"certificates?|tickets?|banknotes?|papers?|sheets? of paper|price|prices|tax|taxes|percent|percentage)\b", re.I)


def sanitize_visual(visual: str) -> str:
    """Remove what makes an image model draw writing: text-bearing objects, price/tax words, digits, currency signs."""
    t = " ".join(str(visual).split())
    for pat, repl in _SWAPS:
        t = re.sub(pat, repl, t, flags=re.I)
    t = _DROP.sub("", t)
    t = re.sub(r"\ban (round dial)", r"a \1", t, flags=re.I)
    t = re.sub(r"[0-9$%\u20ac\u00a3\u20ab\u00a5#@]+", "", t)
    t = re.sub(r"\s+([,.;:])", r"\1", t)
    t = re.sub(r"(?:,\s*){2,}", ", ", t)
    t = re.sub(r"\b(?:a|an|the|and|with|of|or)\s*(?=[,.;:]|$)", "", t, flags=re.I)
    t = " ".join(t.split()).strip(" ,;:")
    return t if len(t) >= 8 else "a simple abstract scene"


def build_prompt(visual: str) -> str:
    return f"{sanitize_visual(visual).rstrip('.')}. {STYLE}. {NEGATIVE}."


class ImageProvider(Protocol):
    name: str
    online: bool

    def fetch(self, key: str, prompt: str, size: tuple[int, int], seed: int) -> Optional[bytes]: ...


class PollinationsImage:
    name = "pollinations-image"
    online = True

    def __init__(self, model: str = "flux", min_interval_s: float = 46.0, retries: int = 3, timeout: float = 120.0,
                 api_key: Optional[str] = None,
                 base_url: str = "https://image.pollinations.ai/prompt/",
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic):
        self.model, self.min_interval, self.retries, self.timeout, self.base = model, min_interval_s, retries, timeout, base_url
        self._sleep, self._clock, self._last = sleep, clock, None
        # anonymous tier: 1 image per 45 s per IP (HTTP 402 FREE_LIMIT). A free "pollen" key from enter.pollinations.ai lifts it.
        self.api_key = api_key if api_key is not None else os.environ.get("POLLINATIONS_API_KEY", "")
        if self.api_key:
            self.min_interval = 0.0

    def fetch(self, key: str, prompt: str, size: tuple[int, int], seed: int) -> Optional[bytes]:
        url = (f"{self.base}{urllib.parse.quote(prompt, safe='')}?width={size[0]}&height={size[1]}"
               f"&seed={seed}&model={self.model}&nologo=true")
        last: Optional[AIError] = None
        for attempt in range(self.retries + 1):
            if self._last is not None:                          # stay under the anonymous rate limit
                wait = self.min_interval - (self._clock() - self._last)
                if wait > 0:
                    self._sleep(wait)
            self._last = self._clock()
            try:
                data = http_request(url, timeout=self.timeout,
                                    headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else None)
                Image.open(io.BytesIO(data)).verify()           # an error page is not a picture
                return data
            except AIError as exc:
                last = exc
                if not exc.retryable:
                    break
                if exc.retry_after and attempt < self.retries:      # the server told us how long to wait
                    self._sleep(exc.retry_after + 1.0)
            except Exception as exc:                            # not an image
                last = AIError(f"the answer is not a picture: {exc}", True)
        raise last or AIError("image request failed")


class CloudflareImage:
    """Cloudflare Workers AI (FLUX.1 schnell by default). Free plan: 10,000 neurons per day, no card.
    Needs CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN (token with Workers AI permission).
    CLOUDFLARE_IMAGE_MODEL overrides the model (for example another FLUX model of the Workers AI catalogue)."""
    name = "cloudflare-image"
    online = True

    def __init__(self, account_id: Optional[str] = None, token: Optional[str] = None, model: Optional[str] = None,
                 steps: int = 4, retries: int = 2, timeout: float = 120.0,
                 sleep: Callable[[float], None] = time.sleep):
        self.account = (account_id or os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")).strip()
        self.token = (token or os.environ.get("CLOUDFLARE_API_TOKEN", "")).strip()
        self.model = model or os.environ.get("CLOUDFLARE_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell")
        self.steps, self.retries, self.timeout, self._sleep = steps, retries, timeout, sleep
        if not self.account or not self.token:
            raise AIError("set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN (free account at dash.cloudflare.com)")

    def fetch(self, key: str, prompt: str, size: tuple[int, int], seed: int) -> Optional[bytes]:
        url = f"https://api.cloudflare.com/client/v4/accounts/{self.account}/ai/run/{self.model}"
        body = json.dumps({"prompt": prompt, "steps": self.steps}).encode("utf-8")      # flux-1-schnell rejects "seed" (HTTP 400)
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        last: Optional[AIError] = None
        softened = False
        for attempt in range(self.retries + 1):
            try:
                raw = http_request(url, data=body, headers=headers, timeout=self.timeout)
                if raw[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1", b"\xff\xd8\xff\xdb"):
                    return raw                                           # some models answer with the picture itself
                data = json.loads(raw)
                if not data.get("success", True):
                    raise AIError(f"Cloudflare: {str(data.get('errors'))[:200]}")
                img = base64.b64decode(data["result"]["image"])
                Image.open(io.BytesIO(img)).verify()
                return img
            except AIError as exc:
                last = exc
                if exc.content_filtered and not softened:         # false positive of the safety filter: say it more safely, once
                    softened = True
                    safe = "Safe for all ages, family-friendly, no people, no bodies, symbolic objects only. " + prompt
                    body = json.dumps({"prompt": safe, "steps": self.steps}).encode("utf-8")
                    continue
                if not exc.retryable:
                    break
                self._sleep(exc.retry_after or 5.0 * (attempt + 1))
            except (ValueError, KeyError, TypeError) as exc:
                raise AIError(f"unexpected answer from Cloudflare: {exc}") from exc
        raise last or AIError("image request failed")


class FolderImages:
    name = "folder"
    online = False
    EXT = (".png", ".jpg", ".jpeg", ".webp")

    def __init__(self, folder: Path):
        self.folder = Path(folder)

    def fetch(self, key: str, prompt: str, size: tuple[int, int], seed: int) -> Optional[bytes]:
        for ext in self.EXT:
            p = self.folder / f"{key}{ext}"
            if p.is_file():
                return p.read_bytes()
        return None                                              # not made yet: the scene stays a drawn infographic


def make_image_provider(kind: str, folder: Optional[Path] = None) -> Optional[ImageProvider]:
    if kind == "off":
        return None
    if kind == "pollinations":
        return PollinationsImage()
    if kind == "cloudflare":
        return CloudflareImage()
    if kind == "folder":
        if folder is None:
            raise AIError("the folder provider needs a folder")
        return FolderImages(folder)
    raise AIError(f"unknown image provider {kind!r}; choose one of {', '.join(IMAGE_CHOICES)}")


def export_kit(claims, visuals: dict[str, str], folder: Path, size: tuple[int, int] = (1024, 1024)) -> Path:
    """Write prompts for hand-made pictures (Google Flow / ImageFX / Gemini app). Returns the markdown file."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    rows = [{"claim_id": c.claim_id, "claim": c.text, "prompt": build_prompt(visuals[c.claim_id])}
            for c in claims if c.claim_id in visuals]
    (folder / "prompts.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# Prompt kit (one picture per scene)", "",
          f"Paste each prompt into a free image tool (Google Flow with Nano Banana, ImageFX, Gemini app ...). Square or "
          f"4:3 works best. Save every result in THIS folder as `<claim_id>.png` (for example `{rows[0]['claim_id'] if rows else 'AI01'}.png`), "
          "then run the video with the folder image provider. Scenes without a file stay as the drawn infographic.", ""]
    for r in rows:
        md += [f"## {r['claim_id']}", f"Claim: {r['claim']}", "", "```", r["prompt"], "```", ""]
    path = folder / "prompts.md"
    path.write_text("\n".join(md), encoding="utf-8")
    return path


class ArtService:
    """`get(key, visual)` -> PIL image or None. Never raises."""

    MAX_FAILS_IN_A_ROW = 2

    def __init__(self, provider: ImageProvider, cache_dir: Path, size: tuple[int, int] = (1024, 1024)):
        self.provider, self.cache_dir, self.size = provider, Path(cache_dir), size
        self.used: dict[str, str] = {}               # key -> "cache" | provider name
        self.errors: list[str] = []
        self._fails = 0

    def _path(self, prompt: str, seed: int) -> Path:
        h = hashlib.sha1(f"{self.provider.name}|{prompt}|{self.size}|{seed}".encode()).hexdigest()[:16]
        return self.cache_dir / f"{h}.png"

    def get(self, key: str, visual: str, seed: int = 7) -> Optional[Image.Image]:
        prompt = build_prompt(visual)
        cached = self._path(prompt, seed)
        try:
            if self.provider.online and cached.is_file():
                self.used[key] = "cache"
                return Image.open(cached).convert("RGB")
            if self.provider.online and self._fails >= self.MAX_FAILS_IN_A_ROW:
                self.errors.append(f"{key}: skipped (provider failed twice in a row)")
                return None
            data = self.provider.fetch(key, prompt, self.size, seed)
        except AIError as exc:
            if not exc.content_filtered:                 # a refused prompt is not a broken provider: do not trip the breaker
                self._fails += 1
            self.errors.append(f"{key}: {exc}")
            return None
        if data is None:
            self.errors.append(f"{key}: no picture available")
            return None
        try:
            img = Image.open(io.BytesIO(data)).convert("RGB")
        except Exception as exc:
            self._fails += 1
            self.errors.append(f"{key}: unreadable picture ({exc})")
            return None
        self._fails = 0
        if self.provider.online:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            img.save(cached)
        self.used[key] = self.provider.name
        return img

    def reset_failures(self) -> None:
        """Re-open the circuit breaker (used before a second attempt at the scenes that still have no picture)."""
        self._fails = 0

    def summary(self, total: int) -> dict:
        return {"provider": self.provider.name, "online": self.provider.online, "scenes_with_image": len(self.used),
                "scenes_total": total, "from_cache": sum(v == "cache" for v in self.used.values()),
                "errors": list(self.errors)}
