"""Deterministic TTS SIMULATOR used until a real provider is measured (to-do items 12, 14).

Actual duration = words / true_wpm * (1 + noise) + pause per sentence. The noise depends only
on the sentence text, so re-synthesising the same text gives the same duration (like a TTS with
a fixed seed). It is NOT a measurement of any real voice: replace it with FFprobe durations of
real audio before quoting S19 in the report.
"""
from __future__ import annotations

import random


class MockTTS:
    def __init__(self, true_wpm: float, noise_sd: float = 0.06, pause_s: float = 0.3, seed: int = 0):
        self.true_wpm, self.noise_sd, self.pause_s, self.seed = true_wpm, noise_sd, pause_s, seed

    def __call__(self, sentences: tuple[str, ...]) -> float:
        total = 0.0
        for s in sentences:
            noise = random.Random(f"{self.seed}|{s}").gauss(0.0, self.noise_sd)
            total += len(s.split()) * 60.0 / self.true_wpm * (1.0 + noise) + self.pause_s
        return total
