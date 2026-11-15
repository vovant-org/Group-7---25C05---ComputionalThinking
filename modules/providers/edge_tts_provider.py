"""Optional voice PREVIEW through the free `edge-tts` package (report 5.9.7, option G1/G4 for drafts).

Purpose: let a user hear a voice before choosing it. This module is NOT needed to run the
pipeline: without `edge-tts` (or without internet) every function raises `TTSUnavailable` with a
clear message and the rest of the app keeps working.

Privacy (report R7, AI tool policy): `edge-tts` sends the text to an online Microsoft service.
Previews therefore use only the fixed public sample sentences of `voice_library.SAMPLE_TEXT`;
the UI never sends user-typed text here.

Not verified against the live service while this was written (no network in the build
environment); the unit tests use a fake `edge_tts` module. Run
`python -m modules.voice_library.cli --check` once on a machine with internet.
"""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.config import OUTPUT_DIR
from modules.voice_library.library import ENGINE_EDGE, SAMPLE_TEXT, VoiceLibrary, VoiceProfile, check_speed

PREVIEW_DIR = OUTPUT_DIR / "voice_previews"      # git-ignored cache of preview audio
TIMEOUT_S = 25.0                                 # report R7: a timeout, then a clear failure


class TTSUnavailable(RuntimeError):
    """The TTS engine cannot be used right now (package missing, offline, service error)."""


@dataclass(frozen=True)
class VerifyResult:
    ok: list[str]            # voice_ids found on the engine
    missing: list[str]       # voice_ids the engine does not list


def is_available() -> bool:
    return importlib.util.find_spec("edge_tts") is not None


def rate_string(speed: float) -> str:
    """edge-tts speaking rate: 1.0 -> '+0%', 1.1 -> '+10%', 0.9 -> '-10%'."""
    return f"{round((check_speed(speed) - 1.0) * 100):+d}%"


def preview_path(voice: VoiceProfile, text: str, speed: float = 1.0, out_dir: Path = PREVIEW_DIR) -> Path:
    """Deterministic cache file name: the same voice, text and speed always map to the same file."""
    key = f"{voice.engine_voice}|{rate_string(speed)}|{text}"
    return Path(out_dir) / f"{voice.voice_id}-{hashlib.sha1(key.encode('utf-8')).hexdigest()[:10]}.mp3"


def _require_package():
    if not is_available():
        raise TTSUnavailable("the 'edge-tts' package is not installed: run  pip install edge-tts")
    import edge_tts
    return edge_tts


def _run(make_coro):
    """Run a coroutine to completion in a worker thread with its own event loop. Streamlit (and
    notebooks) may already own a loop in the calling thread, so asyncio.run() is not safe there."""
    box: dict = {}

    def worker():
        try:
            box["value"] = asyncio.run(asyncio.wait_for(make_coro(), TIMEOUT_S))
        except BaseException as exc:             # reported to the caller below
            box["error"] = exc

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join()
    if "error" in box:
        exc = box["error"]
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
            raise TTSUnavailable(f"the TTS service did not answer within {TIMEOUT_S:.0f} s") from exc
        raise TTSUnavailable(f"TTS request failed ({type(exc).__name__}: {exc}). Check the internet connection.") from exc
    return box["value"]


def synthesize_preview(voice: VoiceProfile, speed: float = 1.0, text: Optional[str] = None,
                       out_dir: Path = PREVIEW_DIR) -> Path:
    """Audio file (mp3) of `voice` reading a sample sentence. Cached: a repeat call is free."""
    if voice.engine != ENGINE_EDGE:
        raise ValueError(f"voice {voice.voice_id} uses engine {voice.engine!r}, not {ENGINE_EDGE!r}")
    text = text if text is not None else SAMPLE_TEXT[voice.language]
    path = preview_path(voice, text, speed, out_dir)
    if path.exists() and path.stat().st_size > 0:
        return path
    edge_tts = _require_package()
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(".part")

    async def save():
        await edge_tts.Communicate(text, voice.engine_voice, rate=rate_string(speed)).save(str(part))

    try:
        _run(save)
        if not part.exists() or part.stat().st_size == 0:
            raise TTSUnavailable("the TTS service returned no audio")
        part.replace(path)                       # only a complete file ever gets the final name
    finally:
        part.unlink(missing_ok=True)
    return path


def list_engine_voices() -> set[str]:
    """Short names of every voice the engine offers (e.g. 'vi-VN-HoaiMyNeural')."""
    edge_tts = _require_package()

    async def fetch():
        return await edge_tts.list_voices()

    return {v["ShortName"] for v in _run(fetch)}


def verify_library(lib: VoiceLibrary) -> VerifyResult:
    """Which library voices exist on the engine. Only edge-tts voices are checked."""
    available = list_engine_voices()
    mine = [v for v in lib if v.engine == ENGINE_EDGE]
    return VerifyResult(ok=[v.voice_id for v in mine if v.engine_voice in available],
                        missing=[v.voice_id for v in mine if v.engine_voice not in available])
