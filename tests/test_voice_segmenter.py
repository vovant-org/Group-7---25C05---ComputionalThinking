import itertools
import random

import pytest

from evaluation.report_scripts import EXAMPLE_A_SLEEP, EXAMPLE_B_INFLATION
from evaluation.voice_benchmark import make_script
from modules.providers.mock_tts import MockTTS
from modules.voice_segmenter.segmenter import (
    ALGORITHMS, VoiceParams, expected_voice_count, in_band, make_unit, repair_after_tts,
    segment_greedy, segment_voices, split_sentences,
)

ALGOS = list(ALGORITHMS)
P1 = VoiceParams(wpm=60.0)          # 1 word == 1 second: easy hand-made cases


def sents(*seconds):
    return [" ".join([f"s{i}"] + ["w"] * (n - 1)) + "." for i, n in enumerate(seconds)]


# ------------------------------------------------------------ sentence splitter
@pytest.mark.parametrize("text,expected", [
    ("Hello world. This is two.", 2),
    ("Inflation was 3.5% last year. It fell later.", 2),
    ("Làm video về TP.HCM bị ngập. Vì sao ngập? Vì mưa lớn!", 3),
    ("Dr. Smith said it works. Nobody doubted him.", 2),
    ("Wait... what happened? Nothing.", 2),
    ("it costs approx. five dollars. ok", 1),
    ("A line\nbroken over\nlines. Next one.", 2),
    ("No final punctuation", 1),
    ("", 0),
])
def test_split_sentences(text, expected):
    assert len(split_sentences(text)) == expected


# ------------------------------------------------------------------- invariants
@pytest.mark.parametrize("algo", ALGOS)
def test_partition_order_and_max_two_sentences(algo):
    rng = random.Random(3)
    for idx in range(60):
        script = make_script(rng, idx, rng.choice([60, 90, 120]))
        seg = segment_voices(script, algo)
        flat = [s for u in seg.units for s in u.sentences]
        assert flat == script                              # nothing lost, nothing split, same order
        assert all(1 <= len(u.sentences) <= 2 for u in seg.units)


def test_empty_script_and_determinism():
    assert segment_voices([], "F4_dp_share").units == []
    script = make_script(random.Random(1), 0, 90)
    for algo in ALGOS:
        assert segment_voices(script, algo).units == segment_voices(script, algo).units


def test_expected_voice_count_matches_report_table():
    assert expected_voice_count(60) == (5, 6)
    assert expected_voice_count(90) == (8, 9)
    assert expected_voice_count(120) == (10, 12)


# --------------------------------------------------------- DP optimality (oracle)
def groupings(n, k=2):
    """All ways to cut n sentences into consecutive groups of size 1..k."""
    if n == 0:
        yield []
        return
    for size in range(1, min(k, n) + 1):
        for rest in groupings(n - size, k):
            yield [size] + rest


def objective(algo, groups, sentences, p):
    pos, viol, dev, n = 0, 0, 0.0, len(groups)
    for gi, g in enumerate(groups):
        u = make_unit(sentences[pos:pos + g], p.wpm, p.pause_s)
        pos += g
        viol += 0 if in_band(u.est_s, p, gi == n - 1) else 1
        dev += abs(u.est_s - p.v_target)
    return {"F2_dp_deviation": (round(dev, 9),),
            "F3_dp_band": (viol, round(dev, 9)),
            "F4_dp_share": (viol, -n, round(dev, 9))}[algo]


@pytest.mark.parametrize("algo", ["F2_dp_deviation", "F3_dp_band", "F4_dp_share"])
def test_dp_is_optimal_against_brute_force(algo):
    rng = random.Random(5)
    for _ in range(80):
        durations = [rng.randint(3, 14) for _ in range(rng.randint(1, 9))]
        s = sents(*durations)
        seg = segment_voices(s, algo, P1)
        got = objective(algo, [len(u.sentences) for u in seg.units], s, P1)
        best = min(objective(algo, g, s, P1) for g in groupings(len(s)))
        assert got == best


# ------------------------------------------------- documented counter-example
def test_f2_and_f3_lose_to_greedy_on_3_11_3_11_and_f4_fixes_it():
    """Sum-of-deviation (F2) and violation-count (F3) both prefer two 14 s voices (0 in band);
    greedy has 2 of 4 voices in band; F4 breaks the tie towards more in-band voices."""
    s = sents(3, 11, 3, 11)

    def n_in_band(algo):
        units = segment_voices(s, algo, P1).units
        return sum(in_band(u.est_s, P1, i == len(units) - 1) for i, u in enumerate(units))
    assert n_in_band("F1_greedy") == 2
    assert n_in_band("F2_dp_deviation") == 0
    assert n_in_band("F3_dp_band") == 0
    assert n_in_band("F4_dp_share") == 2


def test_report_pseudocode_of_f1_can_emit_a_three_sentence_voice():
    """Report 5.7 merges a short tail (which may hold 2 sentences) into a 1-sentence voice."""
    s = sents(10, 3, 3)
    faithful = segment_greedy(s, P1, faithful=True).units
    fixed = segment_greedy(s, P1).units
    assert [len(u.sentences) for u in faithful] == [3]
    assert [len(u.sentences) for u in fixed] == [1, 2]


def test_long_single_sentence_is_flagged_for_shortening():
    seg = segment_voices(sents(20, 6, 5), "F3_dp_band", P1)
    assert 0 in seg.needs_shorten and all(len(u.sentences) >= 1 for u in seg.units)


# -------------------------------------------------------------------- repair
class FakeTTS:
    def __init__(self, table):
        self.table, self.calls = table, []

    def __call__(self, sentences):
        self.calls.append(sentences)
        return self.table[sentences]


def test_repair_splits_a_voice_that_is_too_long_and_caches_unchanged_voices():
    s = sents(6, 6, 6, 5)
    units = [make_unit(s[0:2], 60.0), make_unit(s[2:4], 60.0)]
    tts = FakeTTS({tuple(s[0:2]): 15.0, tuple(s[2:4]): 11.0, (s[0],): 7.5, (s[1],): 7.5})
    res = repair_after_tts(units, tts, P1)
    assert [len(u.sentences) for u in res.units] == [1, 1, 2]
    assert res.synth_calls == 4                      # 2 initial + 2 new singles; voice 2 not re-synthesised
    assert tts.calls.count(tuple(s[2:4])) == 1


def test_repair_merges_two_short_voices_and_stops_after_max_rounds():
    s = sents(4, 5, 11)
    units = [make_unit((s[0],), 60.0), make_unit((s[1],), 60.0), make_unit((s[2],), 60.0)]
    tts = FakeTTS({(s[0],): 4.0, (s[1],): 5.0, (s[2],): 11.0, tuple(s[0:2]): 9.5})
    res = repair_after_tts(units, tts, P1, max_rounds=2)
    assert [len(u.sentences) for u in res.units] == [2, 1] and res.rounds <= 2


def test_mock_tts_is_deterministic_and_longer_with_more_words():
    tts = MockTTS(true_wpm=165, seed=1)
    a, b = ("one two three four five.",), ("one two three four five six seven eight nine ten.",)
    assert tts(a) == tts(a) and tts(b) > tts(a)


# ----------------------------------------------- the report's own worked examples
def test_report_examples_contain_voices_with_three_sentences():
    """Report 4(f) says 1-2 sentences per voice, but three of the 18 example voices have 3."""
    three = [(name, i + 1) for name, ex in (("A", EXAMPLE_A_SLEEP), ("B", EXAMPLE_B_INFLATION))
             for i, v in enumerate(ex) if len(split_sentences(v)) > 2]
    assert three == [("A", 1), ("B", 4), ("B", 6)]
