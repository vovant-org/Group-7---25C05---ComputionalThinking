import csv
import math
import struct
import wave

from evaluation.fit_tts_model import fit
from evaluation.measure_tts import make_manifest, measure
from modules.providers.mock_tts import MockTTS


def write_silence(path, seconds, rate=8000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<h", 0) * int(seconds * rate))


def test_fit_recovers_wpm_and_pause_from_simulated_tts():
    tts = MockTTS(true_wpm=150, noise_sd=0.0, pause_s=0.4)
    rows = []
    for i, (words, sents) in enumerate([(w, s) for w in (9, 14, 20, 27, 33, 40) for s in (1, 2, 3)]):
        per = max(1, words // sents)
        sentences = tuple(" ".join([f"x{i}_{j}"] + ["w"] * (per - 1)) + "." for j in range(sents))
        rows.append({"n_words": per * sents, "n_sentences": sents, "duration_s": tts(sentences)})
    res = fit(rows)
    assert math.isclose(res["wpm"], 150, rel_tol=1e-6) and math.isclose(res["pause_s"], 0.4, rel_tol=1e-6)
    assert res["r2"] > 0.999999 and res["noise_sd"] < 1e-9


def test_fit_estimates_noise_level():
    tts = MockTTS(true_wpm=170, noise_sd=0.06, pause_s=0.3, seed=2)
    rows = []
    for i in range(200):
        n = 6 + (i * 7) % 30
        sentences = tuple(" ".join([f"y{i}_{j}"] + ["w"] * (n - 1)) + "." for j in range(1 + i % 2))
        rows.append({"n_words": n * len(sentences), "n_sentences": len(sentences), "duration_s": tts(sentences)})
    res = fit(rows)
    assert abs(res["wpm"] - 170) < 4 and abs(res["pause_s"] - 0.3) < 0.15 and 0.03 < res["noise_sd"] < 0.09


def test_manifest_and_measurement_round_trip(tmp_path):
    manifest = make_manifest(tmp_path / "m.csv")
    rows = list(csv.DictReader(open(manifest, encoding="utf-8")))
    assert len(rows) == 18 and rows[0]["text_id"] == "A1"
    audio = tmp_path / "audio"
    audio.mkdir()
    write_silence(audio / "A1.wav", 10.5)
    write_silence(audio / "B4.wav", 11.25)
    out = measure(manifest, audio, tmp_path / "out.csv")
    assert {r["text_id"] for r in out} == {"A1", "B4"}
    a1 = next(r for r in out if r["text_id"] == "A1")
    assert a1["n_sentences"] == 3 and a1["n_words"] == 29 and abs(a1["duration_s"] - 10.5) < 0.01
