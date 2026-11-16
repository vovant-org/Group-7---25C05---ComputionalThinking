"""Font lookup. The infographic text is drawn by code, so we need a font with Vietnamese diacritics.

Search order: env STORYFRAME_FONT / STORYFRAME_FONT_BOLD, then common Windows, Linux and macOS fonts.
Segoe UI, Arial, Tahoma, DejaVu Sans and Noto Sans all cover Vietnamese. If nothing is found Pillow's
built-in font is used and diacritics may be missing: `font_report()` tells the caller.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from PIL import ImageFont

_WIN = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
_REGULAR = [_WIN / "segoeui.ttf", _WIN / "arial.ttf", _WIN / "tahoma.ttf", _WIN / "calibri.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"), Path("/Library/Fonts/Arial.ttf")]
_BOLD = [_WIN / "segoeuib.ttf", _WIN / "arialbd.ttf", _WIN / "tahomabd.ttf", _WIN / "calibrib.ttf",
         Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
         Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
         Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
         Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"), Path("/Library/Fonts/Arial Bold.ttf")]


def _find(env_name: str, candidates: list[Path]) -> Optional[str]:
    env = os.environ.get(env_name)
    if env and Path(env).exists():
        return env
    for p in candidates:
        if p.exists():
            return str(p)
    return None


@lru_cache(maxsize=None)
def font_path(bold: bool = False) -> Optional[str]:
    path = _find("STORYFRAME_FONT_BOLD" if bold else "STORYFRAME_FONT", _BOLD if bold else _REGULAR)
    return path or (font_path(False) if bold else None)


@lru_cache(maxsize=256)
def get_font(size: int, bold: bool = False):
    path = font_path(bold)
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)       # no diacritics guaranteed (Pillow >= 10.1)


def font_report() -> str:
    reg, bold = font_path(False), font_path(True)
    if reg is None:
        return "no TrueType font found: set STORYFRAME_FONT to a font with Vietnamese support"
    return f"regular={reg}, bold={bold}"
