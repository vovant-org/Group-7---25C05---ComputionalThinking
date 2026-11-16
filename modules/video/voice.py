"""Voice-over for the video: speech engines, a recorder that plugs into `run_pipeline(tts=...)`.

`run_pipeline` accepts any callable `tts(sentences) -> seconds`. `VoiceRecorder` is such a callable
that really synthesises the scene narration, caches the audio and returns its REAL duration, so the
Timeline Assembler works on measured audio instead of the simulated MockTTS.

Engines (all write or produce a speech file for a text):
  SilentEngine   no sound, duration from a words-per-minute rule. Offline, deterministic: for tests
                 and for checking the video without audio.
  Pyttsx3Engine  the operating system voice (SAPI5 on Windows). Offline: the text never leaves the PC.
                 Vietnamese works only if a Vietnamese system voice is installed.
  EdgeEngine     Microsoft Edge neural voices via the `edge-tts` package (the voice library's voices).
                 ONLINE: the narration text is sent to a Microsoft service, so it must be switched on
                 explicitly (see make_video `allow_online`).

NOT verified against the live services while this was written (no network in the build environment).
Unit tests cover the recorder with SilentEngine and a fake engine.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Optional, Protocol, Sequence

import numpy as np

from modules.providers import edge_tts_provider as edge
from modules.voice_library.library import VoiceProfile

SAMPLE_RATE = 44100


class FFmpegMissing(RuntimeError):
    pass


class VoiceError(RuntimeError):
    pass


def find_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        raise FFmpegMissing("FFmpeg not found. Install it, or run:  pip install imageio-ffmpeg") from None


# ------------------------------------------------------------------ wav helpers (44.1 kHz, mono, 16 bit)
def write_silence(path: Path, seconds: float) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(np.zeros(int(round(seconds * SAMPLE_RATE)), np.int16).tobytes())


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, SAMPLE_RATE):
            raise VoiceError(f"{path} is not 44.1 kHz mono 16-bit")
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32)


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def write_wav(path: Path, samples: np.ndarray) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(np.clip(samples, -32768, 32767).astype(np.int16).tobytes())


def run_ffmpeg(args: Sequence[str], ffmpeg: Optional[str] = None) -> None:
    cmd = [ffmpeg or find_ffmpeg(), "-y", "-loglevel", "error", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise VoiceError(f"ffmpeg failed: {proc.stderr.strip()[:400]}")


# ------------------------------------------------------------------ engines
class SpeechEngine(Protocol):
    name: str
    normalised: bool            # True: the produced file is already a 44.1 kHz mono 16-bit wav

    def synthesize(self, text: str, dest_stem: Path) -> Path: ...


class SilentEngine:
    """Silence whose length follows words / wpm + a pause (the same rule as MockTTS without noise)."""
    normalised = True

    def __init__(self, wpm: float = 165.0, pause_s: float = 0.3):
        self.wpm, self.pause_s = wpm, pause_s
        self.name = f"silent-{wpm:g}-{pause_s:g}"

    def synthesize(self, text: str, dest_stem: Path) -> Path:
        path = dest_stem.with_suffix(".wav")
        write_silence(path, len(text.split()) * 60.0 / self.wpm + self.pause_s)
        return path


class Pyttsx3Engine:
    """Operating-system voice through `pyttsx3` (offline). `speed` scales the default rate."""
    normalised = False

    def __init__(self, speed: float = 1.0, voice_hint: Optional[str] = None):
        try:
            import pyttsx3
        except ImportError:
            raise VoiceError("pyttsx3 is not installed: pip install pyttsx3") from None
        self._engine = pyttsx3.init()
        self._engine.setProperty("rate", int(self._engine.getProperty("rate") * speed))
        if voice_hint:
            for v in self._engine.getProperty("voices"):
                if voice_hint.lower() in f"{v.id} {v.name}".lower():
                    self._engine.setProperty("voice", v.id)
                    break
        self.name = f"pyttsx3-{speed:g}-{voice_hint or 'default'}"

    def synthesize(self, text: str, dest_stem: Path) -> Path:
        path = dest_stem.with_suffix(".sys.wav")
        self._engine.save_to_file(text, str(path))
        self._engine.runAndWait()
        if not path.exists() or path.stat().st_size == 0:
            raise VoiceError("the system voice produced no audio")
        return path


class EdgeEngine:
    """A voice of the voice library through `edge-tts`. ONLINE: sends the narration text."""
    normalised = False

    def __init__(self, voice: VoiceProfile, speed: float = 1.0):
        self.voice, self.speed = voice, speed
        self.name = f"edge-{voice.engine_voice}-{edge.rate_string(speed)}"

    def synthesize(self, text: str, dest_stem: Path) -> Path:
        mod = edge._require_package()
        path = dest_stem.with_suffix(".mp3")
        rate = edge.rate_string(self.speed)

        async def save():
            await mod.Communicate(text, self.voice.engine_voice, rate=rate).save(str(path))

        edge._run(save)
        if not path.exists() or path.stat().st_size == 0:
            raise edge.TTSUnavailable("the TTS service returned no audio")
        return path


# ------------------------------------------------------------------ recorder
class VoiceRecorder:
    """Callable `tts(sentences) -> seconds` for `run_pipeline`, plus the audio files behind it.

    `tempo` (N3 of the report) makes the narration faster/slower: the returned duration is the raw
    duration divided by tempo and `mix_path` applies the same factor to the audio with FFmpeg."""

    def __init__(self, engine: SpeechEngine, out_dir: Path, ffmpeg: Optional[str] = None):
        self.engine, self.out_dir, self._ffmpeg = engine, Path(out_dir), ffmpeg
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.tempo = 1.0
        self.calls = 0                     # real synthesis calls (cache misses)

    @property
    def ffmpeg(self) -> str:
        if self._ffmpeg is None:
            self._ffmpeg = find_ffmpeg()
        return self._ffmpeg

    @staticmethod
    def text_of(sentences: Sequence[str]) -> str:
        return " ".join(sentences)

    def _stem(self, text: str) -> Path:
        key = hashlib.sha1(f"{self.engine.name}|{text}".encode("utf-8")).hexdigest()[:14]
        return self.out_dir / key

    def raw_path(self, sentences: Sequence[str]) -> Path:
        """Normalised wav (44.1 kHz mono) of the narration; synthesised on first use."""
        text = self.text_of(sentences)
        wav = self._stem(text).with_suffix(".norm.wav")
        if wav.exists() and wav.stat().st_size > 0:
            return wav
        produced = self.engine.synthesize(text, self._stem(text))
        self.calls += 1
        if self.engine.normalised:
            produced.replace(wav)
        else:
            run_ffmpeg(["-i", str(produced), "-ar", str(SAMPLE_RATE), "-ac", "1", "-c:a", "pcm_s16le", str(wav)],
                       self.ffmpeg)
        return wav

    def __call__(self, sentences: tuple[str, ...]) -> float:
        return wav_seconds(self.raw_path(sentences)) / self.tempo

    def mix_path(self, sentences: Sequence[str]) -> Path:
        """The wav to place on the timeline: the raw audio, sped up or down by `tempo`."""
        raw = self.raw_path(sentences)
        if abs(self.tempo - 1.0) < 1e-6:
            return raw
        out = raw.with_name(raw.stem + f".t{self.tempo:.3f}.wav")
        if not out.exists():
            run_ffmpeg(["-i", str(raw), "-filter:a", f"atempo={self.tempo:.4f}", "-ar", str(SAMPLE_RATE),
                        "-ac", "1", "-c:a", "pcm_s16le", str(out)], self.ffmpeg)
        return out


def build_audio_track(entries, recorder: VoiceRecorder, out_wav: Path, total_s: float) -> Path:
    """Place every scene's narration at its start time in one 44.1 kHz mono wav of `total_s` seconds."""
    from modules.voice_segmenter.segmenter import split_sentences
    buf = np.zeros(int(round(total_s * SAMPLE_RATE)) + SAMPLE_RATE, np.float32)
    for e in entries:
        clip = read_wav(recorder.mix_path(tuple(split_sentences(e.narration))))
        a = int(round(e.start_s * SAMPLE_RATE))
        n = min(len(clip), int(round(e.duration_s * SAMPLE_RATE)), len(buf) - a)   # never spill into the next scene
        buf[a:a + n] += clip[:n]
    write_wav(out_wav, buf[: int(round(total_s * SAMPLE_RATE))])
    return out_wav


def make_engine(kind: str, voice: Optional[VoiceProfile] = None, speed: float = 1.0,
                allow_online: bool = False, planning_wpm: float = 165.0) -> SpeechEngine:
    """kind: "silent" | "system" | "edge" | "auto" (system voice when pyttsx3 exists, else silent).

    Privacy (report R7 / AI tool policy): "edge" sends the narration text to an online service, so it
    is refused unless `allow_online` is set explicitly. "auto" never goes online."""
    if kind == "silent":
        return SilentEngine(wpm=planning_wpm)
    if kind == "system":
        return Pyttsx3Engine(speed, voice_hint=voice.name if voice else None)
    if kind == "edge":
        if not allow_online:
            raise VoiceError("the 'edge' voice sends the narration text to an online service: "
                             "pass allow_online=True (CLI: --allow-online) to confirm")
        if voice is None:
            raise VoiceError("the 'edge' engine needs a voice from the voice library")
        if not edge.is_available():
            raise edge.TTSUnavailable("the 'edge-tts' package is not installed: pip install edge-tts")
        return EdgeEngine(voice, speed)
    if kind == "auto":
        try:
            return make_engine("system", voice, speed)
        except VoiceError:
            return SilentEngine(wpm=planning_wpm)
    raise VoiceError(f"unknown voice engine {kind!r}; choose silent, system, edge or auto")
