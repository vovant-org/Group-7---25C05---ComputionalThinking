"""ANIMATION from AI pictures (modules/video/ai_animation.py): cut-out, animated scene, retries, the all-or-nothing
fallback (policy A) and make_video wiring. No network: the image provider is a fake."""
import io

import numpy as np
import pytest
from PIL import Image, ImageDraw

from core.models import Scene
from modules.ai import images as I
from modules.ai.net import AIError
from modules.pipeline.sample_claims import get_sample_claims
from modules.video.ai_animation import (MAX_H, MAX_W, collect_pictures, compose_ai_scene, compose_ai_scenes,
                                        make_cutout, subject_mask)
from modules.video.animation import check_animation
from modules.video.composer import Style
from modules.video.make_video import make_video
from modules.video.voice import make_engine
from modules.voice_library.library import builtin_library

ST = Style()


def subject_picture(size=(1024, 1024)) -> Image.Image:
    """A red ring on a plain white background; the centre of the ring is white too."""
    im = Image.new("RGB", size, (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.ellipse((250, 250, 780, 780), fill=(220, 80, 60))
    d.ellipse((430, 430, 600, 600), fill=(255, 255, 255))
    return im


def png(img=None) -> bytes:
    b = io.BytesIO()
    (img or subject_picture((256, 256))).save(b, "PNG")
    return b.getvalue()


class Provider:
    name, online = "fake-online", True

    def __init__(self, fail_calls=0, always=False):
        self.fail_calls, self.always, self.calls = fail_calls, always, 0

    def fetch(self, key, prompt, size, seed):
        self.calls += 1
        if self.always or self.calls <= self.fail_calls:
            raise AIError("boom", True)
        return png()


def scene(i=0, pattern="cause_effect", importance=0.5):
    return Scene(scene_id=i, narration="Some narration.", explain_pattern=pattern, importance=importance,
                 facet="science", claim_ids=[f"C{i}"])


# ------------------------------------------------------------------ cut-out
def test_plain_background_is_removed_but_white_inside_the_subject_stays():
    m = subject_mask(subject_picture())
    assert m is not None
    assert m.getpixel((3, 3)) == 0                       # background
    assert m.getpixel((300, 512)) > 200                  # the ring
    assert m.getpixel((512, 512)) > 200                  # white hole inside the ring is not connected to the border


def test_cutout_is_a_transparent_sprite_that_fits_the_stage_and_keeps_the_colour():
    c = make_cutout(subject_picture())
    assert c.cut and c.sprite.mode == "RGBA" and c.sprite.width <= MAX_W and c.sprite.height <= MAX_H
    assert c.sprite.getpixel((1, 1))[3] == 0
    r, g, b = c.tone
    assert r > g and r > b                               # the subject is red


def test_picture_without_a_plain_background_is_kept_whole_as_a_card():
    noise = Image.fromarray(np.random.default_rng(1).integers(0, 255, (300, 400, 3), dtype=np.uint8))
    c = make_cutout(noise)
    assert not c.cut and c.note and c.sprite.width <= MAX_W and c.sprite.height <= MAX_H


def test_a_flat_single_colour_picture_does_not_break_the_cutout():
    assert not make_cutout(Image.new("RGB", (200, 200), (120, 160, 220))).cut


# ------------------------------------------------------------------ the scene
@pytest.mark.parametrize("index", [0, 1, 4, 11])
@pytest.mark.parametrize("pattern", ["cause_effect", "trend", "something_else"])
def test_ai_scene_moves_and_leaves_the_subtitle_band_free(index, pattern):
    cs = compose_ai_scene(scene(index, pattern, 0.9), "claim", subject_picture(), ST, index, 12)
    assert check_animation(cs, ST) == []
    assert cs.layout == "cutout:ai_picture" and cs.plan.prop == "ai_picture" and cs.labels == []


def test_ai_scene_frames_are_deterministic_and_the_subject_enters_from_its_side():
    a = compose_ai_scene(scene(1), "c", subject_picture(), ST, 1, 6)
    b = compose_ai_scene(scene(1), "c", subject_picture(), ST, 1, 6)
    ra, rb = a.make_renderer(7.0, 7.0, 1, ST), b.make_renderer(7.0, 7.0, 1, ST)
    for t in (0.0, 1.0, 3.5, 6.9):
        assert np.array_equal(ra.frame(t), rb.frame(t))
    pic = next(l for l in a.layers if l.name == "picture")
    assert pic.x(0.0) > pic.x(1.0) and pic.x(1.0) == pytest.approx(640)      # index 1 is mirrored: enters from the right


def test_energy_makes_important_scenes_livelier():
    calm = next(l for l in compose_ai_scene(scene(3, importance=0.5), "c", subject_picture(), ST, 3, 12).layers if l.name == "picture")
    lively = next(l for l in compose_ai_scene(scene(3, importance=0.9), "c", subject_picture(), ST, 3, 12).layers if l.name == "picture")
    amp = lambda l: max(l.y(u / 100) for u in range(30, 100)) - min(l.y(u / 100) for u in range(30, 100))
    assert amp(lively) > amp(calm)


def test_scenes_of_a_video_share_one_look_but_differ_in_tone():
    blue = Image.new("RGB", (512, 512), (255, 255, 255))
    ImageDraw.Draw(blue).ellipse((120, 120, 400, 400), fill=(40, 90, 220))
    comp = compose_ai_scenes([scene(0), scene(1)], {0: subject_picture(), 1: blue}, ST)
    assert not np.array_equal(np.asarray(comp[0].base), np.asarray(comp[1].base))


# ------------------------------------------------------------------ getting the pictures
def scenes_and_visuals(n=4):
    sc = [scene(i) for i in range(n)]
    return sc, {f"C{i}": "a moon" for i in range(n)}


def test_scenes_without_a_picture_are_retried_with_the_circuit_breaker_reopened(tmp_path):
    sc, vis = scenes_and_visuals(4)
    prov = Provider(fail_calls=2)                          # two failures trip the breaker; the retry round must reset it
    art = I.ArtService(prov, tmp_path)
    pics, why = collect_pictures(art, sc, vis)
    assert why == "" and set(pics) == {0, 1, 2, 3}


def test_a_provider_that_never_answers_gives_none_and_a_reason(tmp_path):
    sc, vis = scenes_and_visuals(3)
    pics, why = collect_pictures(I.ArtService(Provider(always=True), tmp_path), sc, vis, rounds=1)
    assert pics is None and "no AI picture" in why and "3 of 3" in why


def test_a_missing_description_means_fallback_without_calling_the_provider(tmp_path):
    sc, vis = scenes_and_visuals(3)
    vis.pop("C1")
    prov = Provider()
    pics, why = collect_pictures(I.ArtService(prov, tmp_path), sc, vis)
    assert pics is None and "[1]" in why and prov.calls == 0


def test_pictures_already_obtained_are_not_requested_again(tmp_path):
    sc, vis = scenes_and_visuals(3)
    prov = Provider(fail_calls=1)
    pics, _ = collect_pictures(I.ArtService(prov, tmp_path), sc, vis)
    assert pics is not None and prov.calls == 4            # 1 failure + 3 pictures, none fetched twice


# ------------------------------------------------------------------ make_video
def _engine():
    voice = builtin_library().default("en")
    return voice, make_engine("silent", voice, 1.0, False, voice.planning_wpm(1.0))


REQUEST = "Make a 90-second animated video about sleep"


def test_animation_uses_ai_pictures_for_every_scene(tmp_path):
    claims = get_sample_claims("sleep")
    voice, engine = _engine()
    art = I.ArtService(Provider(), tmp_path)
    res = make_video(REQUEST, claims, "unused.mp4", engine=engine, voice=voice, render=False, art=art,
                     visuals={c.claim_id: "a moon" for c in claims})
    assert res.ok, res.error
    rep = res.report
    assert all(t["layout"] == "cutout:ai_picture" and t["prop"] == "ai_picture" for t in rep["timeline"])
    assert "visual_engine" not in rep                       # the topic engine is not used in this mode
    assert rep["ai_images"]["scenes_with_image"] == rep["scenes"]
    assert all(rep["criteria"][k]["pass"] for k in ("S11", "S12", "S13", "S15")), rep["criteria"]
    assert any("AI pictures" in n for n in rep["notes"])


def test_one_missing_picture_turns_the_whole_video_into_the_code_drawn_animation(tmp_path):
    """Policy A: never a video that mixes AI pictures and stick figures."""
    claims = get_sample_claims("sleep")
    voice, engine = _engine()
    art = I.ArtService(Provider(always=True), tmp_path)
    res = make_video(REQUEST, claims, "unused.mp4", engine=engine, voice=voice, render=False, art=art,
                     visuals={c.claim_id: "a moon" for c in claims})
    assert res.ok, res.error
    rep = res.report
    assert all(t["layout"] != "cutout:ai_picture" for t in rep["timeline"])
    assert rep["visual_engine"]["domain"] == "sleep"        # the topic-aware engine drew it instead
    assert rep["ai_images"]["scenes_with_image"] == 0
    assert any("AI pictures" in n and "code-drawn" in n for n in rep["notes"])


def test_animation_without_ai_is_unchanged():
    voice, engine = _engine()
    res = make_video(REQUEST, get_sample_claims("sleep"), "unused.mp4", engine=engine, voice=voice, render=False)
    assert res.ok and "ai_images" not in res.report and "visual_engine" in res.report
