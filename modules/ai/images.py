"""Free image providers + the service that gives make_video one picture per scene.

PollinationsImage  online, no key (anonymous tier: 1 image per 45 s per IP, so 16 scenes take about 12 minutes; a free key removes the wait).
FolderImages       offline: pictures you made by hand on a free web tool (Google Flow, ImageFX, Gemini app, ...)
                   saved as <claim_id>.png in a folder. `export_kit` writes the prompts to paste there.
ArtService         disk cache (same prompt -> no new request), rate limit, and a circuit breaker: after two
                   failures in a row the remaining scenes fall back to the drawn infographic instead of waiting.

Prompts always ask for NO text in the picture: words and numbers on screen are drawn by code (S15).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import time
import urllib.parse
from pathlib import Path
from typing import Callable, Optional, Protocol

from PIL import Image

from modules.ai.net import AIError, http_request

STYLE = ("clean flat vector infographic illustration, soft pastel colors on a plain light background, "
         "simple bold shapes, one clear subject, no clutter")
NEGATIVE = "no text, no letters, no numbers, no captions, no watermark, no logo"
IMAGE_CHOICES = ("off", "pollinations", "folder")


def build_prompt(visual: str) -> str:
    return f"{visual.strip().rstrip('.')}. {STYLE}. {NEGATIVE}."


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

    def summary(self, total: int) -> dict:
        return {"provider": self.provider.name, "online": self.provider.online, "scenes_with_image": len(self.used),
                "scenes_total": total, "from_cache": sum(v == "cache" for v in self.used.values()),
                "errors": list(self.errors)}
