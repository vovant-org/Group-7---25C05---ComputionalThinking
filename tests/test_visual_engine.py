"""Tests of the Topic-aware Visual Engine (modules/visual_engine): topic analysis, voice sync, object choice,
every object's frames, determinism, quality checks, and the end-to-end video (silent voice: no TTS, no network)."""
import numpy as np
import pytest

from core.models import Scene
from modules.pipeline.sample_claims import get_sample_claims
from modules.video.animation import GROUND_Y, check_animation
from modules.video.composer import Style
from modules.video.make_video import make_video
from modules.video.subtitles import cue_texts
from modules.video.voice import make_engine
from modules.visual_engine import analyse_topic, compose_topic_scenes, textmatch
from modules.visual_engine.engine import compose_topic_scene, select_objects
from modules.visual_engine.kits import POOLS, SUB_TOP, draw_backdrop
from modules.visual_engine.objects import OBJECTS, Ctx
from modules.visual_engine.quality import QualityReport, check_repeats, check_subtitles, object_coverage, run_quality
from modules.visual_engine.sync import appear_time, word_times
from modules.visual_engine.topic import CONCEPT_DOMAINS, DOMAINS, find_concepts, trend_of
from modules.voice_library.library import builtin_library

ST = Style()


def sc(text, i=0, pattern="cause_effect", importance=0.6):
    return Scene(scene_id=i, narration=text, explain_pattern=pattern, importance=importance, facet="science")


# ------------------------------------------------------------------ 1. topic analysis
@pytest.mark.parametrize("topic,claims,domain", [
    ("Why does Ho Chi Minh City flood in heavy rain?", ["High tides push the water level up and drains cannot keep up."], "weather"),
    ("Tại sao thành phố Hồ Chí Minh bị ngập khi mưa lớn?", ["Mưa lớn và triều cường làm nước dâng cao."], "weather"),
    ("Why do prices keep rising?", ["Inflation means prices rise, so money buys less.", "Banks raise interest rates."], "economy"),
    ("How do planets orbit the sun?", ["Planets travel around the sun on paths called orbits."], "space"),
    ("Why do we need sleep?", ["Sleep helps the brain sort memories."], "sleep"),
    ("Tại sao chúng ta cần ngủ?", ["Giấc ngủ giúp não sắp xếp trí nhớ."], "sleep"),
    ("How do plants grow?", ["A seed needs water and sunlight to sprout."], "nature"),
    ("What is the meaning of life", ["It depends."], "generic"),
])
def test_domain_is_chosen_from_the_content(topic, claims, domain):
    assert analyse_topic(topic, claims).domain == domain


def test_every_concept_has_a_known_domain_object_and_pool():
    assert set(CONCEPT_DOMAINS) == set(OBJECTS)
    assert all(d in DOMAINS for doms in CONCEPT_DOMAINS.values() for d in doms)
    assert all(k in OBJECTS for pool in POOLS.values() for k in pool) and set(POOLS) == set(DOMAINS)


def test_vietnamese_diacritics_separate_rain_from_buy_and_folded_text_still_matches():
    assert [k for k, _ in find_concepts("Trời mưa to")] == ["drop"]
    assert find_concepts("Tôi mua rau") == []
    assert [k for k, _ in find_concepts("Giac ngu giup nao sap xep tri nho")] == ["bed", "brain"]


def test_folded_vietnamese_keyword_does_not_hit_english_words():
    assert textmatch.find_keywords(textmatch.tokens("planets travel around the sun"), ["trả"], False) is None
    assert analyse_topic("How do planets orbit the sun?", ["Planets travel around the sun."]).relations[0].verb == "orbits"


def test_trend_and_relations():
    assert trend_of("Prices rise and rise") == 1 and trend_of("Prices fall") == -1 and trend_of("A cat sat") == 0
    assert trend_of("Giá tăng rồi giảm") == 1
    assert analyse_topic("Why do prices rise?", ["Prices rise."]).trend == 1


# ------------------------------------------------------------------ 4. voice-over sync
def test_word_times_are_monotonic_and_fill_the_audio():
    t = word_times("Rain falls, so the river rises. Then streets flood.", 8.0)
    starts = [a for _, a, _ in t]
    assert starts == sorted(starts) and starts[0] == 0.0 and t[-1][2] == pytest.approx(8.0)
    assert all(b > a for _, a, b in t)


def test_punctuation_adds_a_pause():
    t = dict((w, (a, b)) for w, a, b in word_times("aaa bbb. ccc ddd", 4.0))
    assert (t["bbb."][1] - t["bbb."][0]) > (t["ccc"][1] - t["ccc"][0])


def test_object_appears_just_before_its_word_and_stays_inside_the_scene():
    assert appear_time(3.0, 8.0, 0) == pytest.approx(2.8)
    assert appear_time(0.0, 8.0, 0) == pytest.approx(0.4) and appear_time(7.9, 8.0, 0) == pytest.approx(7.36)
    assert appear_time(None, 8.0, 1) == pytest.approx(8.0 * 0.22)


def test_scene_sync_log_ties_objects_to_spoken_words():
    prof = analyse_topic("rain", ["Heavy rain falls on the city and the water level rises."])
    ts = compose_topic_scene(sc("Heavy rain falls on the city and the water level rises."), "", prof, ST, 0, 4)
    ts.build_layers(8.0, 7.0, ST)
    by = {s["object"]: s for s in ts.sync_log}
    assert by["drop"]["word"].lower().startswith("rain") and by["drop"]["appear_s"] <= by["drop"]["mention_s"] + 0.45
    assert all(abs(s["appear_s"] - s["mention_s"]) <= 0.5 for s in ts.sync_log if s["mention_s"] is not None)


# ------------------------------------------------------------------ 2. choosing the visual kit
def test_objects_come_from_the_words_of_the_scene_in_order():
    prof = analyse_topic("sleep", ["Sleep helps the brain."])
    ch = select_objects("At night the moon rises and the brain sorts memories.", "", prof, 0, "cause_effect", [])
    assert [c.key for c in ch][:2] == ["moon", "brain"]


def test_planets_bring_their_own_sun_and_one_wide_object_leaves_room():
    prof = analyse_topic("space", ["Planets orbit the sun."])
    ch = [c.key for c in select_objects("The sun holds each planet in its orbit.", "", prof, 0, "cause_effect", [])]
    assert "planet" in ch and "sun" not in ch
    ch = select_objects("A deer walks past a tree near the river and a bird flies over the sea.", "", analyse_topic("nature", ["deer"]), 0,
                        "cause_effect", [])
    assert len(ch) <= 2


def test_scene_without_known_words_is_filled_from_the_domain_pool_not_left_empty():
    prof = analyse_topic("Why do prices rise?", ["Inflation means prices rise."])
    ch = select_objects("Nothing special is said here.", "", prof, 3, "cause_effect", [])
    assert 1 <= len(ch) <= 3 and all(c.key in POOLS["economy"] for c in ch)


def test_no_scene_repeats_the_objects_of_the_previous_scenes():
    prof = analyse_topic("planets", ["Planets orbit the sun."])
    scenes = [sc("The planet moves around the sun.", i) for i in range(8)]
    comp = compose_topic_scenes(scenes, prof, ST)
    sigs = [comp[i].signature for i in range(8)]
    assert all(a != b for a, b in zip(sigs, sigs[1:])) and all(sigs[i] != sigs[i - 2] for i in range(2, 8))


def test_trend_pattern_adds_bars_in_economy():
    prof = analyse_topic("Why do prices rise?", ["Prices rise."])
    ch = [c.key for c in select_objects("A coin buys less today.", "", prof, 0, "trend", [])]
    assert "bars_up" in ch


def test_different_topics_get_different_pictures_for_the_same_scene_shape():
    a = compose_topic_scene(sc("A story is told here."), "", analyse_topic("sleep", ["Sleep helps."]), ST, 1, 8)
    b = compose_topic_scene(sc("A story is told here."), "", analyse_topic("planets", ["Planets orbit."]), ST, 1, 8)
    assert a.domain != b.domain and set(a.objects).isdisjoint(b.objects)
    assert not np.array_equal(np.asarray(a.base), np.asarray(b.base))


# ------------------------------------------------------------------ 3. content-aware motion, frames
@pytest.mark.parametrize("key", sorted(OBJECTS))
def test_every_object_builds_valid_layers_that_move_and_stay_out_of_the_subtitle_band(key):
    from modules.video.animation import AnimatedScene, LayerRenderer
    from modules.video.motion_planner import MotionPlan
    dom = CONCEPT_DOMAINS[key][0]
    base = draw_backdrop(dom, ST, "science", 1, 1, 6, ST.accent("science"))
    ctx = Ctx(x=640, gy=GROUND_Y, u0=0.15, accent=ST.accent("science"), accent2=ST.accent("science", 2),
              partners=(900,) if key == "coin" else (), rain=key == "cloud")
    layers = OBJECTS[key].build(ctx)
    assert layers
    r = LayerRenderer(AnimatedScene(1, MotionPlan(1, "body", "none", key, 1.0, False), base, layers), 8.0, ST)
    first, mid, last = r.frame(0.2), r.frame(4.0), r.frame(7.6)
    assert not np.array_equal(first, last), f"{key} does not appear"
    assert any(not np.array_equal(r.frame(x), last) for x in (1.5, 3.0, 4.5)), f"{key} is a still image"
    band = np.asarray(base)[SUB_TOP:]
    for fr in (first, mid, last):
        assert np.array_equal(fr[SUB_TOP:], band), f"{key} draws into the subtitle band"


def test_motion_follows_content_animal_walks_plant_grows_planet_orbits_coins_circulate():
    def pos(layer, u):
        return layer.x(u), layer.y(u)
    c = Ctx(x=640, gy=GROUND_Y, u0=0.1, accent=ST.accent("a"), accent2=ST.accent("a", 2))
    body = next(l for l in OBJECTS["animal"].build(c) if l.name == "body")
    assert pos(body, 0.9)[0] - pos(body, 0.2)[0] > 300                              # walks across the stage
    tree = OBJECTS["tree"].build(c)[0]
    assert tree.scale(0.2) < 0.5 < 0.9 < tree.scale(0.7)                           # grows
    planet = next(l for l in OBJECTS["planet"].build(c) if l.name == "outer")
    xs = [planet.x(u / 20) for u in range(3, 20)]
    assert max(xs) - min(xs) > 400 and len({round(planet.y(u / 20)) for u in range(3, 20)}) > 5   # goes round
    coins = [l for l in OBJECTS["coin"].build(Ctx(**{**c.__dict__, "partners": (900.0,)})) if l.name.startswith("flow")]
    assert len(coins) == 3 and max(l.x(u / 20) for l in coins for u in range(3, 20)) > 800    # reaches its partner
    water = OBJECTS["flood"].build(c)[0]
    assert water.sy(0.15) < 0.2 and water.sy(0.8) == pytest.approx(1.0)               # water rises


def test_trend_direction_flips_the_motion():
    up = OBJECTS["bars_up"].build(Ctx(x=640, gy=GROUND_Y, u0=0.1, accent=(1, 1, 1), accent2=(2, 2, 2), trend=1))
    down = OBJECTS["bars_up"].build(Ctx(x=640, gy=GROUND_Y, u0=0.1, accent=(1, 1, 1), accent2=(2, 2, 2), trend=-1))
    assert next(l for l in up if l.name == "arrow").rot(0.9) == 0.0 and next(l for l in down if l.name == "arrow").rot(0.9) == 180.0


def test_same_input_gives_the_same_frames():
    prof = analyse_topic("sleep", ["Sleep helps the brain at night."])
    a = compose_topic_scene(sc("At night sleep helps the brain."), "", prof, ST, 2, 6)
    b = compose_topic_scene(sc("At night sleep helps the brain."), "", prof, ST, 2, 6)
    fa, fb = a.make_renderer(8.0, 7.0, 2, ST).frame(5.0), b.make_renderer(8.0, 7.0, 2, ST).frame(5.0)
    assert np.array_equal(fa, fb)


@pytest.mark.parametrize("domain", DOMAINS)
def test_backdrops_never_touch_the_subtitle_band_and_differ_between_scenes(domain):
    a = np.asarray(draw_backdrop(domain, ST, "science", 1, 0, 6, (200, 0, 0)))
    b = np.asarray(draw_backdrop(domain, ST, "science", 2, 1, 6, (200, 0, 0)))
    assert a.shape == (720, 1280, 3)
    if domain != "generic":
        assert not np.array_equal(a, b) or domain == "tech"
    assert np.array_equal(a[SUB_TOP:, :, :][:, :, 0].std(axis=1) >= 0, np.ones(720 - SUB_TOP, dtype=bool))


def test_check_animation_accepts_engine_scenes():
    prof = analyse_topic("flood", ["Rain makes the water level rise in the city."])
    ts = compose_topic_scene(sc("Rain makes the water level rise in the city."), "", prof, ST, 0, 6)
    assert check_animation(ts, ST) == []


# ------------------------------------------------------------------ 5. quality checks
def test_coverage_is_high_for_objects_and_low_for_an_empty_scene():
    prof = analyse_topic("sleep", ["Sleep helps the brain."])
    ts = compose_topic_scene(sc("The brain sorts memories during sleep."), "", prof, ST, 0, 6)
    assert object_coverage(ts, 8.0, 7.0, ST) > 0.004
    ts.choices = []
    ts._built.clear()
    assert object_coverage(ts, 8.0, 7.0, ST) == 0.0


def test_repeat_check_flags_identical_neighbours():
    prof = analyse_topic("planets", ["Planets orbit."])
    one = compose_topic_scene(sc("The planet orbits.", 0), "", prof, ST, 0, 4)
    two = compose_topic_scene(sc("The planet orbits.", 1), "", prof, ST, 1, 4)            # no history passed: same objects
    rep = QualityReport()
    check_repeats([one, two], rep)
    assert not rep.checks["repeated_visuals"]["pass"] and "same objects" in rep.problems[0]


def _entry(text, start=0.0, dur=8.0):
    from core.models import TimelineEntry
    return TimelineEntry(scene_id=0, start_s=start, duration_s=dur, audio_duration_s=dur - 0.5, narration=text)


def test_subtitle_check_passes_clean_cues():
    rep = QualityReport()
    check_subtitles([_entry("Rain falls on the city, so water cannot soak into the soil. The drains are full."),
                     _entry("Tides push the river up.", start=8.0)], rep)
    assert rep.checks["subtitles"]["pass"], rep.problems


def test_long_sentence_subtitles_keep_the_connector_word():
    """Regression: the connector at the cut ('so') used to vanish from the subtitles."""
    text = "Heavy rain falls on a city where most of the ground is covered by concrete, so water cannot soak into the soil."
    norm = lambda s: s.replace(",", "").replace(".", "").lower().split()
    assert norm(" ".join(cue_texts(text))) == norm(text)


# ------------------------------------------------------------------ end to end
def _engine():
    voice = builtin_library().default("en")
    return voice, make_engine("silent", voice, 1.0, False, voice.planning_wpm(1.0))


def test_make_video_reports_topic_and_quality_for_animation():
    voice, eng = _engine()
    res = make_video("Make a 90-second animated video about sleep", get_sample_claims("sleep"), "unused.mp4", engine=eng,
                     voice=voice, render=False)
    assert res.ok, res.error
    ve = res.report["visual_engine"]
    assert ve["domain"] == "sleep" and ve["quality"]["ok"], ve["quality"]["problems"]
    assert {"empty_scenes", "repeated_visuals", "sync", "subtitles", "audio", "duration"} <= set(ve["quality"]["checks"])
    assert all(t["prop"] and t["layout"].startswith("cutout:") for t in res.report["timeline"])
    assert res.report["timeline"][0]["pose"] == "wave"                                 # the hook still waves


def test_inflation_video_looks_different_from_sleep_video():
    voice, eng = _engine()
    a = make_video("Make a 90-second animated video about sleep", get_sample_claims("sleep"), "u.mp4", engine=eng, voice=voice, render=False)
    b = make_video("Make a 90-second animated video about inflation", get_sample_claims("inflation"), "u.mp4", engine=eng, voice=voice, render=False)
    oa = {o for s in a.report["visual_engine"]["scenes"] for o in s["objects"]}
    ob = {o for s in b.report["visual_engine"]["scenes"] for o in s["objects"]}
    assert b.report["visual_engine"]["domain"] == "economy" and oa != ob and len(ob & {"coin", "bank", "tag", "bars_up", "basket"}) >= 3


def test_visual_engine_can_be_switched_off():
    voice, eng = _engine()
    res = make_video("Make a 90-second animated video about sleep", get_sample_claims("sleep"), "u.mp4", engine=eng, voice=voice,
                     render=False, visual_engine=False)
    assert res.ok and "visual_engine" not in res.report


def test_run_quality_on_a_real_timeline():
    voice, eng = _engine()
    res = make_video("Make a 90-second animated video about sleep", get_sample_claims("sleep"), "u.mp4", engine=eng, voice=voice, render=False)
    assert res.pipeline.timeline is not None


def test_relax_repeat_breaks_a_repeat_when_every_fresh_object_was_just_used(monkeypatch):
    """Four scenes name the same two objects; the tech pool has no other free, non-wide object in the last two scenes."""
    from modules.visual_engine import engine as E
    prof = analyse_topic("computers", ["A computer sends data over the network."])
    scenes = [sc("The computer sends data.", i) for i in range(4)]

    def sigs(relax):
        monkeypatch.setattr(E, "RELAX_REPEAT", relax)
        comp = compose_topic_scenes(scenes, prof, ST)
        return [comp[i].signature for i in range(4)]
    off, on = sigs(False), sigs(True)
    assert all(a != b for a, b in zip(on, on[1:]))
    assert len(set(on)) >= len(set(off))
