import pytest

from core.config import PROFILES
from core.models import OutputFormat, RenderMode, Scene
from modules.providers.mock_tts import MockTTS
from modules.scene_segmenter.segmenter import Claim, build_scenes, select_claims
from modules.timeline_assembler.assembler import assemble, scene_audio_durations

P = PROFILES[OutputFormat.INFOGRAPHIC]       # t_min 4, t_max 10, total 60-120


def scenes(n):
    return [Scene(scene_id=i, narration=f"Scene {i}.", claim_ids=[f"C{i}"]) for i in range(n)]


def audio(*secs):
    return {i: s for i, s in enumerate(secs)}


# ------------------------------------------------------------------ happy path
def test_happy_path_places_scenes_back_to_back():
    tl = assemble(scenes(10), audio(*[9.0] * 10), P, t_target=90)
    assert tl.ok and tl.codes == set()
    assert tl.total_s == pytest.approx(90.0) and tl.deviation == pytest.approx(0.0)
    starts = [e.start_s for e in tl.entries]
    assert starts == pytest.approx([9.0 * i for i in range(10)])
    for a, b in zip(tl.entries, tl.entries[1:]):          # no gap, no overlap
        assert b.start_s == pytest.approx(a.start_s + a.duration_s)


def test_entry_keeps_scene_data():
    sc = scenes(10)
    sc[3].render_mode, sc[3].transition_in = RenderMode.PAN, "fade"
    tl = assemble(sc, audio(*[9.0] * 10), P, t_target=90)
    e = tl.entries[3]
    assert (e.scene_id, e.render_mode, e.transition_in, e.claim_ids) == (3, RenderMode.PAN, "fade", ["C3"])


def test_does_not_modify_input_scenes():
    sc = scenes(10)
    assemble(sc, audio(*[9.0] * 10), P, t_target=90)
    assert all(s.start_s == 0.0 and s.duration_s == 0.0 for s in sc)


# ------------------------------------------------------------- scene length rules
def test_short_scene_is_stretched_to_t_min():
    tl = assemble(scenes(10), audio(2.5, *[9.0] * 9), P, t_target=85.5)
    assert tl.entries[0].duration_s == pytest.approx(4.0)
    assert tl.entries[0].audio_duration_s == pytest.approx(2.5)   # the audio itself is unchanged
    assert tl.stretched == [0]


def test_pad_is_added_after_each_narration():
    tl = assemble(scenes(10), audio(*[8.5] * 10), P, t_target=90, pad_s=0.5)
    assert all(e.duration_s == pytest.approx(9.0) for e in tl.entries) and tl.ok


def test_scene_longer_than_t_max_is_reported_not_cut():
    tl = assemble(scenes(10), audio(11.0, *[8.0] * 9), P, t_target=83)
    assert tl.entries[0].duration_s == pytest.approx(11.0)        # never silently truncated
    assert tl.too_long == [0] and "SCENE_TOO_LONG" in tl.codes


def test_exactly_t_min_and_t_max_are_fine():
    tl = assemble(scenes(10), audio(4.0, 10.0, *[8.25] * 8), P, t_target=80)
    assert tl.stretched == [] and tl.too_long == [] and tl.ok


# --------------------------------------------------- S12: total duration 60-120 s
@pytest.mark.parametrize("n, per, ok", [(10, 5.9, False), (10, 6.0, True),      # 59 s / 60 s
                                        (12, 10.0, True), (13, 9.3, False)])    # 120 s / 120.9 s
def test_total_range_boundaries_exact(n, per, ok):
    tl = assemble(scenes(n), audio(*[per] * n), P, t_target=n * per)
    assert ("TOTAL_OUT_OF_RANGE" not in tl.codes) is ok


def test_total_above_120_is_out_of_range():
    tl = assemble(scenes(13), audio(*[10.0] * 13), P, t_target=120)
    assert tl.total_s == pytest.approx(130.0) and "TOTAL_OUT_OF_RANGE" in tl.codes


# ------------------------------------------------------ S13: deviation <= 5 %
def test_deviation_exactly_5_percent_is_accepted():
    tl = assemble(scenes(10), audio(*[9.45] * 10), P, t_target=90)     # 94.5 vs 90
    assert tl.deviation == pytest.approx(0.05) and "DEVIATION_OVER_5PCT" not in tl.codes


def test_deviation_just_over_5_percent_is_rejected():
    tl = assemble(scenes(10), audio(*[9.46] * 10), P, t_target=90)     # 94.6 vs 90
    assert "DEVIATION_OVER_5PCT" in tl.codes and "TOTAL_OUT_OF_RANGE" not in tl.codes


def test_under_target_also_counts():
    tl = assemble(scenes(10), audio(*[8.5] * 10), P, t_target=90)      # 85 vs 90 = 5.6 %
    assert "DEVIATION_OVER_5PCT" in tl.codes


# ------------------------------------------------------------------ bad input
def test_no_scenes():
    tl = assemble([], {}, P, t_target=90)
    assert tl.codes == {"NO_SCENES"} and tl.entries == []


def test_missing_audio_is_a_programming_error():
    with pytest.raises(ValueError, match="scene 2"):
        assemble(scenes(3), {0: 9.0, 1: 9.0}, P, t_target=90)


@pytest.mark.parametrize("bad", [0.0, -1.0])
def test_non_positive_audio_rejected(bad):
    with pytest.raises(ValueError):
        assemble(scenes(2), {0: 9.0, 1: bad}, P, t_target=90)


def test_bad_parameters_rejected():
    with pytest.raises(ValueError):
        assemble(scenes(2), audio(9.0, 9.0), P, t_target=0)
    with pytest.raises(ValueError):
        assemble(scenes(2), audio(9.0, 9.0), P, t_target=90, pad_s=-0.1)


# ------------------------------------- integration: Scene Segmenter -> (mock) TTS -> Timeline
def test_pipeline_slice_with_mock_tts():
    text = "word " * 25                                    # 25 words, about 9 s at 165 wpm
    claims = [Claim(f"C{i}", text.strip(), "science", 0.5, order=i) for i in range(12)]
    sel = select_claims(claims, 90)
    sc, _ = build_scenes(sel)
    tts = MockTTS(true_wpm=165.0, noise_sd=0.0, pause_s=0.0)
    aud = scene_audio_durations(sc, tts)
    tl = assemble(sc, aud, P, t_target=90)
    assert len(tl.entries) == len(sc) > 0
    assert tl.total_s == pytest.approx(sum(e.duration_s for e in tl.entries))
    assert tl.entries[0].start_s == 0.0
    assert [e.scene_id for e in tl.entries] == [s.scene_id for s in sc]
