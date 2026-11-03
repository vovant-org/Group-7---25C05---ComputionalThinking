"""Turn real TTS audio into measurements (report to-do items 12 and 14).

Step 1  python -m evaluation.measure_tts --make-manifest
        -> evaluation/data/tts_manifest.csv  (the 18 narration voices of report 5.8; ADD more rows)
Step 2  synthesize every row with the TTS under test; save the audio as
        <audio-dir>/<text_id>.wav (or .mp3/.m4a/.ogg/.flac; needs ffprobe on PATH for non-wav)
Step 3  python -m evaluation.measure_tts --audio-dir audio
        -> evaluation/data/tts_measurements.csv  (words, sentences, real duration)
Step 4  python -m evaluation.fit_tts_model   (fits wpm, pause and noise)

Use only public text (e.g. the report's examples). Never send private data to an online TTS.
"""
from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import wave
from pathlib import Path

from core.config import DATA_DIR
from evaluation.report_scripts import EXAMPLE_A_SLEEP, EXAMPLE_B_INFLATION
from modules.voice_segmenter.segmenter import split_sentences

MANIFEST = DATA_DIR / "tts_manifest.csv"
MEASUREMENTS = DATA_DIR / "tts_measurements.csv"
AUDIO_EXT = (".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac")


def make_manifest(path: Path = MANIFEST, language: str = "en", voice: str = "TODO_voice_name") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [(f"A{i}", language, voice, t) for i, t in enumerate(EXAMPLE_A_SLEEP, 1)]
    rows += [(f"B{i}", language, voice, t) for i, t in enumerate(EXAMPLE_B_INFLATION, 1)]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["text_id", "language", "voice", "text"])
        w.writerows(rows)
    return path


def audio_duration(path: Path) -> float:
    if path.suffix.lower() == ".wav":
        with wave.open(str(path), "rb") as w:
            return w.getnframes() / float(w.getframerate())
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe not found: install FFmpeg or export the audio as .wav")
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def measure(manifest: Path, audio_dir: Path, out_csv: Path = MEASUREMENTS) -> list[dict]:
    rows, missing = [], []
    with open(manifest, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            file = next((audio_dir / f"{r['text_id']}{e}" for e in AUDIO_EXT
                         if (audio_dir / f"{r['text_id']}{e}").exists()), None)
            if file is None:
                missing.append(r["text_id"])
                continue
            rows.append({"text_id": r["text_id"], "language": r["language"], "voice": r["voice"],
                         "n_sentences": len(split_sentences(r["text"])),
                         "n_words": len(r["text"].split()),
                         "duration_s": round(audio_duration(file), 3)})
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["text_id", "language", "voice", "n_sentences", "n_words", "duration_s"])
        w.writeheader()
        w.writerows(rows)
    if missing:
        print("No audio found for:", ", ".join(missing))
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--make-manifest", action="store_true")
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--audio-dir", type=Path, default=Path("audio"))
    a = ap.parse_args()
    if a.make_manifest:
        print("written:", make_manifest(a.manifest))
    else:
        rows = measure(a.manifest, a.audio_dir)
        print(f"{len(rows)} measurements -> {MEASUREMENTS}")
