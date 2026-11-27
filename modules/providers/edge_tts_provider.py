"""Optional voice PREVIEW through the free `edge-tts` package (report 5.9.7, option G1/G4 for drafts).

Purpose: let a user hear a voice before choosing it. This module is NOT needed to run the
pipeline: without `edge-tts` (or without internet) every function raises `TTSUnavailable` with a
clear message and the rest of the app keeps working.

Two sources of preview audio, in this order:
  1. BUNDLED samples `assets/voice_previews/<voice_id>.mp3` (normal speed only). One teammate with
     internet runs `python -m modules.voice_library.cli --make-previews` and commits them, after which
     every machine can listen offline, without `edge-tts`.
  2. LIVE synthesis through `edge-tts` (any speed), cached in `outputs/voice_previews/`.

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

import shutil

from core.config import OUTPUT_DIR, PROJECT_ROOT
from modules.voice_library.library import ENGINE_EDGE, SAMPLE_TEXT, VoiceLibrary, VoiceProfile, check_speed

PREVIEW_DIR = OUTPUT_DIR / "voice_previews"      # git-ignored cache of live previews
BUNDLED_DIR = PROJECT_ROOT / "assets" / "voice_previews"   # committed samples, one per voice
RETRY_ATTEMPTS = 5                               # the online service / the network fail at random: try again
RETRY_PAUSE_S = 2.0                              # wait 2 s, 4 s, 6 s ... between attempts
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


def pitch_string(pitch_hz: int = 0) -> str:
    """edge-tts pitch offset: 0 -> '+0Hz', -3 -> '-3Hz' (chosen by modules/voice_library/casting.py)."""
    return f"{int(pitch_hz):+d}Hz"


def tts_options(speed: float = 1.0, pitch_hz: int = 0) -> dict:
    """Keyword arguments for edge_tts.Communicate. `pitch` is only passed when it changes the voice."""
    opts = {"rate": rate_string(speed)}
    if int(pitch_hz):
        opts["pitch"] = pitch_string(pitch_hz)
    return opts


def preview_path(voice: VoiceProfile, text: str, speed: float = 1.0, out_dir: Optional[Path] = None,
                 pitch_hz: int = 0) -> Path:
    """Deterministic cache file name: the same voice, text, speed and pitch always map to the same file."""
    key = f"{voice.engine_voice}|{rate_string(speed)}|{text}" + (f"|{pitch_string(pitch_hz)}" if int(pitch_hz) else "")
    return Path(out_dir or PREVIEW_DIR) / f"{voice.voice_id}-{hashlib.sha1(key.encode('utf-8')).hexdigest()[:10]}.mp3"


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
        hint = (" Try  pip install -U edge-tts  (Microsoft changes the service, old versions stop working)."
                if type(exc).__name__ in ("NoAudioReceived", "WebSocketError", "UnexpectedResponse") else "")
        raise TTSUnavailable(f"TTS request failed ({type(exc).__name__}: {exc}). Check the internet connection.{hint}") from exc
    return box["value"]


def run_with_retry(make_coro, attempts: Optional[int] = None, pause_s: Optional[float] = None):
    """`_run`, repeated a few times: the online service (or the network, e.g. a DNS hiccup) sometimes fails at random."""
    import time
    attempts = RETRY_ATTEMPTS if attempts is None else attempts
    pause_s = RETRY_PAUSE_S if pause_s is None else pause_s
    for i in range(attempts):
        try:
            return _run(make_coro)
        except TTSUnavailable:
            if i == attempts - 1:
                raise
            time.sleep(pause_s * (i + 1))


def synthesize_preview(voice: VoiceProfile, speed: float = 1.0, text: Optional[str] = None,
                       out_dir: Optional[Path] = None, pitch_hz: int = 0) -> Path:
    """Audio file (mp3) of `voice` reading a sample sentence. Cached: a repeat call is free."""
    if voice.engine != ENGINE_EDGE:
        raise ValueError(f"voice {voice.voice_id} uses engine {voice.engine!r}, not {ENGINE_EDGE!r}")
    text = text if text is not None else SAMPLE_TEXT[voice.language]
    path = preview_path(voice, text, speed, out_dir, pitch_hz)
    if path.exists() and path.stat().st_size > 0:
        return path
    edge_tts = _require_package()
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(".part")

    async def save():
        await edge_tts.Communicate(text, voice.engine_voice, **tts_options(speed, pitch_hz)).save(str(part))

    try:
        run_with_retry(save)
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


# ------------------------------------------------------------------ bundled samples and the single entry point
def bundled_path(voice: VoiceProfile, bundled_dir: Optional[Path] = None) -> Path:
    return Path(bundled_dir or BUNDLED_DIR) / f"{voice.voice_id}.mp3"


def has_bundled(voice: VoiceProfile, bundled_dir: Optional[Path] = None) -> bool:
    p = bundled_path(voice, bundled_dir)
    return p.exists() and p.stat().st_size > 0


def can_preview(voice: VoiceProfile, speed: float = 1.0, bundled_dir: Optional[Path] = None, pitch_hz: int = 0) -> bool:
    """True when `get_preview` has a chance: a bundled sample at normal speed and pitch, or the live engine."""
    return (speed == 1.0 and not int(pitch_hz) and has_bundled(voice, bundled_dir)) or (voice.engine == ENGINE_EDGE and is_available())


def get_preview(voice: VoiceProfile, speed: float = 1.0, bundled_dir: Optional[Path] = None,
                out_dir: Optional[Path] = None, pitch_hz: int = 0) -> Path:
    """Audio file to play for `voice`: the bundled sample at normal speed and pitch, otherwise live synthesis.
    Raises TTSUnavailable when neither is possible."""
    check_speed(speed)
    if speed == 1.0 and not int(pitch_hz) and has_bundled(voice, bundled_dir):
        return bundled_path(voice, bundled_dir)
    return synthesize_preview(voice, speed, out_dir=out_dir, pitch_hz=pitch_hz)


def make_bundled_previews(lib: VoiceLibrary, bundled_dir: Optional[Path] = None, force: bool = False,
                          out_dir: Optional[Path] = None) -> list[Path]:
    """Create (or, with force, refresh) the committed sample of every edge-tts voice. Needs internet.
    Returns the files written; voices that already have a sample are skipped unless `force`."""
    written = []
    Path(bundled_dir or BUNDLED_DIR).mkdir(parents=True, exist_ok=True)
    for v in lib:
        if v.engine != ENGINE_EDGE or (has_bundled(v, bundled_dir) and not force):
            continue
        target = bundled_path(v, bundled_dir)
        shutil.copyfile(synthesize_preview(v, 1.0, out_dir=out_dir), target)
        written.append(target)
    return written
