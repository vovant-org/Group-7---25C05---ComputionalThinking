"""AI integration: reader (grounding), image service (cache / breaker / folder), composer layout, make_video wiring.
No test touches the network: providers are replaced by fakes."""
import io
import json

import pytest
from PIL import Image

from core.models import Scene
from modules.ai import images as I
from modules.ai import reader as R
from modules.ai.net import AIError
from modules.ai.setup import prepare_ai
from modules.pipeline.sample_claims import get_sample_claims
from modules.video.composer import check_labels, compose_scene, static_frame
from modules.video.make_video import make_video
from modules.video.voice import find_ffmpeg, make_engine, FFmpegMissing
from modules.voice_library.library import builtin_library

REFERENCE = " ".join([
    "Sleep is an active process during which the brain sorts memories and clears waste built up during the day.",
    "The night is split into repeating cycles of light sleep, deep sleep and dream sleep each lasting about ninety minutes.",
    "Going without enough sleep makes it harder to concentrate, remember new facts and react quickly to what happens around you.",
    "Keeping the same bedtime and wake-up time, even on weekends, helps the body clock settle into a steady rhythm.",
    "Bright screens late in the evening can delay sleepiness because light tells the brain that it is still daytime.",
    "A cool dark quiet bedroom makes it easier to fall asleep and to stay asleep through the whole night.",
    "Caffeine taken in the afternoon can stay in the body for many hours and make falling asleep much harder.",
])
SENTENCES = [s.strip() + "." for s in REFERENCE.split(".") if s.strip()]


def scenes_json(claims, extra=()):
    items = [{"claim": c, "facet": "Health", "importance": 0.7, "pattern": "cause_effect",
              "visual": f"a person and a moon, scene {i}"} for i, c in enumerate(claims)]
    items += list(extra)
    return json.dumps({"scenes": items})


class FakeLLM:
    name = "fake-llm"

    def __init__(self, answer=None, exc=None):
        self.answer, self.exc, self.calls = answer, exc, []

    def complete(self, system, user):
        self.calls.append((system, user))
        if self.exc:
            raise self.exc
        return self.answer


def png(color=(120, 160, 220), size=(64, 64)) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", size, color).save(b, "PNG")
    return b.getvalue()


# ------------------------------------------------------------------ reader
def test_reference_claims_are_kept_and_fabricated_ones_are_dropped():
    fake = {"claim": "Sleeping eight hours raises exam scores by 40 percent according to a famous university study.",
            "visual": "students"}
    llm = FakeLLM("```json\n" + scenes_json(SENTENCES, [fake]) + "\n```")      # code fences are tolerated
    res = R.read_input("sleep video", REFERENCE, llm)
    assert res.used_ai and res.grounded and len(res.claims) == len(SENTENCES)
    assert all("40 percent" not in c.text for c in res.claims)
    assert any("not found in the reference" in r for r in res.rejected)
    assert all(R.grounding(c.text, REFERENCE) >= R.GROUND_RATIO for c in res.claims)
    assert set(res.visuals) == {c.claim_id for c in res.claims}
    assert "REFERENCE TEXT" in llm.calls[0][1] and "Never add a fact" in llm.calls[0][0]


def test_topic_only_is_marked_unverified_and_numbers_are_rejected():
    claims = [f"Regular sleep helps the brain and the body to recover well after a long day of work number {w}."
              for w in ("one", "two", "three", "four", "five", "six")]
    llm = FakeLLM(scenes_json(claims, [{"claim": "Adults need 8 hours of sleep every single night to stay healthy and happy.", "visual": "x"}]))
    res = R.read_input("sleep", "", llm)
    assert res.used_ai and not res.grounded and len(res.claims) == 6
    assert any("number" in r for r in res.rejected)
    assert any("NOT verified" in n for n in res.notes)


@pytest.mark.parametrize("llm", [FakeLLM(exc=AIError("offline")), FakeLLM("not json at all"),
                                 FakeLLM(json.dumps({"scenes": [{"claim": "too short", "visual": "x"}]}))])
def test_reader_falls_back_to_the_extractive_baseline(llm):
    res = R.read_input("sleep", REFERENCE, llm)
    assert not res.used_ai and res.reader == "extractive" and res.claims and res.notes
    assert all(R.grounding(c.text, REFERENCE) == 1.0 for c in res.claims)
    assert all(res.visuals[c.claim_id] for c in res.claims)


def test_no_reference_and_no_ai_gives_no_claims():
    res = R.read_input("sleep", "", None)
    assert res.claims == [] and res.notes


# ------------------------------------------------------------------ images
class FakeProvider:
    name, online = "fake-online", True

    def __init__(self, fail=0):
        self.fail, self.calls = fail, 0

    def fetch(self, key, prompt, size, seed):
        self.calls += 1
        if self.fail:
            raise AIError("boom", True)
        return png()


def test_prompt_forbids_text_in_the_picture():
    p = I.build_prompt("a moon over a bed")
    assert "no text" in p and "no numbers" in p and p.startswith("a moon over a bed.")


def test_service_caches_by_prompt(tmp_path):
    prov = FakeProvider()
    art = I.ArtService(prov, tmp_path)
    assert art.get("AI01", "a moon") is not None and art.get("AI01", "a moon") is not None
    assert prov.calls == 1 and art.summary(2)["from_cache"] == 1


def test_service_stops_asking_after_two_failures_in_a_row(tmp_path):
    prov = FakeProvider(fail=1)
    art = I.ArtService(prov, tmp_path)
    assert [art.get(f"AI0{i}", "a moon") for i in range(4)] == [None] * 4
    assert prov.calls == 2 and len(art.errors) == 4          # scenes 3 and 4 are skipped without waiting


def test_folder_provider_reads_hand_made_pictures(tmp_path):
    (tmp_path / "AI01.png").write_bytes(png())
    art = I.ArtService(I.FolderImages(tmp_path), tmp_path / "cache")
    assert art.get("AI01", "x") is not None and art.get("AI02", "x") is None
    assert art.summary(2)["scenes_with_image"] == 1 and not (tmp_path / "cache").exists()


def test_export_kit_lists_every_claim(tmp_path):
    claims = get_sample_claims("sleep")[:3]
    md = I.export_kit(claims, {c.claim_id: "a moon" for c in claims}, tmp_path / "kit")
    text = md.read_text(encoding="utf-8")
    assert all(c.claim_id in text for c in claims) and "no text" in text
    assert len(json.loads((tmp_path / "kit" / "prompts.json").read_text(encoding="utf-8"))) == 3


def test_pollinations_waits_between_requests_and_rejects_non_images(monkeypatch):
    now, slept = [0.0], []
    prov = I.PollinationsImage(min_interval_s=16, sleep=lambda s: (slept.append(s), now.__setitem__(0, now[0] + s)),
                               clock=lambda: now[0])
    answers = iter([b"<html>busy</html>", png()])
    monkeypatch.setattr(I, "http_request", lambda url, **kw: next(answers))
    assert prov.fetch("k", "a moon", (64, 64), 1)                   # first answer is not a picture -> retried
    assert slept and slept[0] == pytest.approx(16)


def test_consent_is_required_for_online_options():
    with pytest.raises(AIError, match="online"):
        prepare_ai("sleep", REFERENCE, [], read_kind="pollinations", allow_online=False)
    with pytest.raises(AIError, match="online"):
        prepare_ai("sleep", REFERENCE, [], image_kind="pollinations", allow_online=False)
    plan = prepare_ai("sleep", "", get_sample_claims("sleep"), image_kind="folder", folder=".")   # offline: no consent needed
    assert plan.art is not None and plan.visuals


# ------------------------------------------------------------------ composer
def _scene():
    c = get_sample_claims("sleep")[0]
    return Scene(scene_id=0, narration=c.text, facet=c.facet, claim_ids=[c.claim_id]), c.text


def test_ai_visual_layout_keeps_text_from_the_claim():
    sc, text = _scene()
    art = Image.new("RGB", (900, 700), (90, 140, 200))
    cs = compose_scene(sc, text, index=0, total=3, art=art)
    assert cs.layout == "ai_visual" and cs.has_art and len(cs.elements) == 2
    assert check_labels(cs) == [] and cs.min_font_used >= 26
    frame = static_frame(cs)
    assert frame.shape == (720, 1280, 3)
    assert abs(int(frame[300, 200, 2]) - 200) < 40                 # the picture is on the left
    plain = compose_scene(sc, text, index=0, total=3)
    assert plain.layout != "ai_visual" and not plain.has_art       # no art -> the old drawn layout, unchanged


# ------------------------------------------------------------------ make_video
def _engine():
    voice = builtin_library().default("en")
    return voice, make_engine("silent", voice, 1.0, False, voice.planning_wpm(1.0))


def test_make_video_uses_ai_pictures_and_degrades_per_scene(tmp_path):
    claims = get_sample_claims("sleep")
    visuals = {c.claim_id: "a moon" for c in claims}
    visuals.pop(claims[1].claim_id)                                  # no description for one claim -> drawn layout
    voice, engine = _engine()
    art = I.ArtService(FakeProvider(), tmp_path)
    res = make_video("Make a 90-second infographic video about sleep", claims, "unused.mp4", engine=engine,
                     voice=voice, render=False, art=art, visuals=visuals)
    assert res.ok, res.error
    layouts = [t["layout"] for t in res.report["timeline"]]
    assert "ai_visual" in layouts and any(l != "ai_visual" for l in layouts)
    assert res.report["ai_images"]["scenes_with_image"] == layouts.count("ai_visual")
    assert res.report["criteria"]["S15"]["pass"]                     # text still comes only from the claims
    assert any("AI pictures" in n for n in res.report["notes"])


def test_make_video_without_ai_is_unchanged():
    voice, engine = _engine()
    res = make_video("Make a 90-second infographic video about sleep", get_sample_claims("sleep"), "unused.mp4",
                     engine=engine, voice=voice, render=False)
    assert res.ok and "ai_images" not in res.report
    assert all(t["layout"] != "ai_visual" for t in res.report["timeline"])


def _ffmpeg_ok():
    try:
        find_ffmpeg()
        return True
    except FFmpegMissing:
        return False


@pytest.mark.skipif(not _ffmpeg_ok(), reason="FFmpeg is not installed")
def test_ai_picture_video_is_rendered(tmp_path):
    claims = get_sample_claims("sleep")
    voice, engine = _engine()
    art = I.ArtService(FakeProvider(), tmp_path / "cache")
    out = tmp_path / "ai.mp4"
    res = make_video("Make a 90-second infographic video about sleep", claims, out, engine=engine, voice=voice,
                     fps=6, work_dir=tmp_path / "work", art=art, visuals={c.claim_id: "a moon" for c in claims})
    assert res.ok, res.error
    assert out.stat().st_size > 10_000 and res.report["criteria"]["S12"]["pass"] and res.report["criteria"]["S13"]["pass"]


# ------------------------------------------------------------------ setup + UI validation
def test_prepare_ai_replaces_claims_with_the_checked_ai_claims(monkeypatch):
    import modules.ai.setup as S
    monkeypatch.setattr(S, "make_llm", lambda kind: FakeLLM(scenes_json(SENTENCES)))
    plan = prepare_ai("sleep video", REFERENCE, [], read_kind="pollinations", allow_online=True)
    assert plan.claims and len(plan.claims) == len(SENTENCES) and set(plan.visuals) == {c.claim_id for c in plan.claims}
    assert plan.art is None


def test_ui_allows_topic_only_when_ai_reads_and_says_it_is_unverified():
    from ui.adapters import has_blocking, validate_inputs
    kw = dict(topic="Why do we sleep?", instructions="", reference="", source="text", claims_text=[],
              voice_language="en", ffmpeg_ok=True)
    assert has_blocking(validate_inputs(**kw))                                         # without AI: still blocked
    msgs = validate_inputs(**kw, ai_reads=True, ai_online_needed=True, ai_online_ok=True)
    assert not has_blocking(msgs) and any("NOT verified" in m["text"] for m in msgs)
    assert has_blocking(validate_inputs(**kw, ai_reads=True, ai_online_needed=True, ai_online_ok=False))


def test_claim_count_follows_the_duration_and_a_short_answer_is_retried():
    assert R.claims_for_duration(90) == 14 and R.claims_for_duration(60) == 9 and R.claims_for_duration(120) == 18
    claims = [f"Regular sleep helps the brain and the body to recover well after a long day of work number {w}."
              for w in ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve")]

    class Twice(FakeLLM):
        def complete(self, system, user):
            self.calls.append((system, user))
            return scenes_json(claims[:6] if len(self.calls) == 1 else claims)
    llm = Twice()
    res = R.read_input("sleep", "", llm, n_scenes=14)
    assert len(llm.calls) == 2 and len(res.claims) == 12
    assert "never fewer than 13" in llm.calls[0][0]


def test_pollinations_402_free_limit_waits_the_time_the_server_asks(monkeypatch):
    import urllib.error
    from modules.ai import net
    body = b'{"status":402,"error":{"code":"FREE_LIMIT","message":"Free limit reached: 1 image every 45 seconds per IP. Retry after 30s"}}'

    class Resp:
        def read(self, n=-1):
            return body

        def close(self):
            pass
    err = urllib.error.HTTPError("https://image.pollinations.ai/x", 402, "Payment Required", {}, Resp())
    monkeypatch.setattr(net.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(err))
    with pytest.raises(AIError) as e:
        net.http_request("https://image.pollinations.ai/x")
    assert e.value.retryable and e.value.retry_after == 30

    slept, calls = [], []
    def fake(url, **kw):
        calls.append(kw.get("headers"))
        if len(calls) == 1:
            raise AIError("HTTP 402 FREE_LIMIT", True, 30)
        return png()
    monkeypatch.setattr(I, "http_request", fake)
    prov = I.PollinationsImage(api_key="", sleep=slept.append, clock=lambda: 0.0)
    assert prov.fetch("k", "a moon", (64, 64), 1) and 31.0 in slept           # waited 30 s + 1, then succeeded


def test_pollinations_key_removes_the_wait_and_is_sent(monkeypatch):
    sent = []
    monkeypatch.setattr(I, "http_request", lambda url, **kw: (sent.append(kw.get("headers")), png())[1])
    slept = []
    prov = I.PollinationsImage(api_key="sk_test", sleep=slept.append, clock=lambda: 0.0)
    prov.fetch("a", "x", (64, 64), 1); prov.fetch("b", "y", (64, 64), 1)
    assert slept == [] and sent[0] == {"Authorization": "Bearer sk_test"}


def test_cloudflare_provider_sends_token_and_decodes_the_base64_picture(monkeypatch):
    import base64
    seen = {}

    def fake(url, data=None, headers=None, timeout=0):
        seen.update(url=url, body=json.loads(data), headers=headers)
        return json.dumps({"success": True, "result": {"image": base64.b64encode(png()).decode()}}).encode()
    monkeypatch.setattr(I, "http_request", fake)
    prov = I.CloudflareImage(account_id="acc123", token="tok", sleep=lambda s: None)
    assert Image.open(io.BytesIO(prov.fetch("AI01", "a moon", (64, 64), 5))).size == (64, 64)
    assert seen["url"].endswith("/accounts/acc123/ai/run/@cf/black-forest-labs/flux-1-schnell")
    assert seen["headers"]["Authorization"] == "Bearer tok" and seen["body"]["prompt"] == "a moon"
    assert set(seen["body"]) == {"prompt", "steps"}                  # Cloudflare answered 400 to an extra "seed" field


def test_cloudflare_needs_credentials_and_needs_consent(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    with pytest.raises(AIError, match="CLOUDFLARE_ACCOUNT_ID"):
        I.make_image_provider("cloudflare")
    with pytest.raises(AIError, match="online"):
        prepare_ai("sleep", REFERENCE, [], image_kind="cloudflare", allow_online=False)


def test_reader_retries_a_busy_provider_before_giving_up(monkeypatch):
    waits = []
    monkeypatch.setattr(R, "SLEEP", waits.append)

    class Busy(FakeLLM):
        def complete(self, system, user):
            self.calls.append(1)
            if len(self.calls) <= 2:
                raise AIError("HTTP 503 high demand", True)
            return scenes_json(SENTENCES)
    llm = Busy()
    res = R.read_input("sleep video", REFERENCE, llm, n_scenes=8)
    assert res.used_ai and len(llm.calls) == 3 and waits == [4.0, 10.0]
    never = FakeLLM(exc=AIError("HTTP 503", True))
    assert not R.read_input("sleep", REFERENCE, never).used_ai and len(never.calls) == 4     # 1 try + 3 retries, then the baseline


def test_content_filter_gets_one_softer_prompt_and_does_not_trip_the_breaker(monkeypatch):
    import base64
    sent = []

    def fake(url, data=None, headers=None, timeout=0):
        prompt = json.loads(data)["prompt"]
        sent.append(prompt)
        if "family-friendly" not in prompt:
            raise AIError("HTTP 400 NSFW", False, 0, content_filtered=True)
        return json.dumps({"success": True, "result": {"image": base64.b64encode(png()).decode()}}).encode()
    monkeypatch.setattr(I, "http_request", fake)
    prov = I.CloudflareImage(account_id="a", token="t", sleep=lambda s: None)
    assert prov.fetch("k", "a bed at night", (64, 64), 1) and len(sent) == 2

    class AlwaysFiltered:
        name, online = "filtered", True

        def fetch(self, *a):
            raise AIError("NSFW", False, 0, content_filtered=True)
    art = I.ArtService(AlwaysFiltered(), "unused")
    assert [art.get(f"AI0{i}", "x") for i in range(4)] == [None] * 4
    assert all("skipped" not in e for e in art.errors)                # every scene was still tried


def test_auto_reader_falls_back_from_a_busy_gemini_to_pollinations(monkeypatch):
    from modules.ai import llm as L
    busy, ok = FakeLLM(exc=AIError("HTTP 503", True)), FakeLLM(scenes_json(SENTENCES))
    ok.name = "pollinations-text"
    chain = L.FallbackLLM([busy, ok])
    res = R.read_input("sleep video", REFERENCE, chain, n_scenes=8)
    assert res.used_ai and len(busy.calls) == 1 and len(ok.calls) == 1 and res.reader == "auto(pollinations-text)"
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert [p.name for p in L.make_llm("auto").providers] == ["pollinations-text"]       # no key: Pollinations only
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    assert [p.name for p in L.make_llm("auto").providers] == ["gemini-text", "pollinations-text"]
