"""Tests of the preview provider WITHOUT network: a fake `edge_tts` module stands in for the real
package. The real service was not reachable while this was written, so these tests pin down OUR
behaviour (caching, partial files, timeout, failure messages), not Microsoft's."""
import asyncio
import sys
import types

import pytest

from modules.providers import edge_tts_provider as tts
from modules.voice_library.library import VoiceProfile, builtin_library

AUDIO = b"ID3-fake-mp3-bytes"
ARIA = builtin_library().get("en-aria")


class FakeEdge(types.ModuleType):
    """Records calls; `behaviour` decides what Communicate.save does."""

    def __init__(self, behaviour="ok", voices=("en-US-AriaNeural", "vi-VN-HoaiMyNeural")):
        super().__init__("edge_tts")
        self.calls: list[tuple] = []
        self.behaviour = behaviour
        self._voices = voices
        outer = self

        class Communicate:
            def __init__(self, text, voice, rate="+0%"):
                self.text, self.voice, self.rate = text, voice, rate

            async def save(self, path):
                outer.calls.append((self.text, self.voice, self.rate))
                if outer.behaviour == "raise":
                    raise ConnectionError("no route to host")
                if outer.behaviour == "slow":
                    await asyncio.sleep(5)
                with open(path, "wb") as f:
                    f.write(b"" if outer.behaviour == "empty" else AUDIO)

        async def list_voices():
            return [{"ShortName": n} for n in outer._voices]

        self.Communicate, self.list_voices = Communicate, list_voices


@pytest.fixture
def fake(monkeypatch):
    mod = FakeEdge()
    monkeypatch.setitem(sys.modules, "edge_tts", mod)
    monkeypatch.setattr(tts, "is_available", lambda: True)
    return mod


# ------------------------------------------------------------------ pure helpers
@pytest.mark.parametrize("speed, expected", [(1.0, "+0%"), (1.1, "+10%"), (0.9, "-10%"), (1.25, "+25%"), (0.75, "-25%")])
def test_rate_string(speed, expected):
    assert tts.rate_string(speed) == expected


@pytest.mark.parametrize("speed", [0.5, 1.5, 0])
def test_rate_string_rejects_speeds_the_library_does_not_allow(speed):
    with pytest.raises(ValueError):
        tts.rate_string(speed)


def test_preview_path_is_deterministic_and_depends_on_voice_text_and_speed(tmp_path):
    a = tts.preview_path(ARIA, "hello", 1.0, tmp_path)
    assert a == tts.preview_path(ARIA, "hello", 1.0, tmp_path)
    assert a.parent == tmp_path and a.suffix == ".mp3" and a.name.startswith("en-aria-")
    others = {tts.preview_path(ARIA, "hello!", 1.0, tmp_path), tts.preview_path(ARIA, "hello", 1.1, tmp_path),
              tts.preview_path(builtin_library().get("en-guy"), "hello", 1.0, tmp_path)}
    assert a not in others and len(others) == 3


def test_is_available_follows_the_installed_package(monkeypatch):
    monkeypatch.setitem(sys.modules, "edge_tts", None)         # None in sys.modules = "not importable"
    assert tts.is_available() is False


# ------------------------------------------------------------------ synthesis
def test_without_the_package_the_error_says_how_to_install(monkeypatch, tmp_path):
    monkeypatch.setattr(tts, "is_available", lambda: False)
    with pytest.raises(tts.TTSUnavailable, match="pip install edge-tts"):
        tts.synthesize_preview(ARIA, out_dir=tmp_path)


def test_preview_writes_the_audio_with_the_right_voice_rate_and_sample_text(fake, tmp_path):
    path = tts.synthesize_preview(ARIA, speed=1.1, out_dir=tmp_path)
    assert path.read_bytes() == AUDIO
    (text, voice, rate), = fake.calls
    assert voice == "en-US-AriaNeural" and rate == "+10%" and text.startswith("Why does the same shopping basket")
    assert [p.name for p in tmp_path.iterdir()] == [path.name]                 # no .part file left behind


def test_vietnamese_voice_reads_the_vietnamese_sample(fake, tmp_path):
    tts.synthesize_preview(builtin_library().get("vi-hoaimy"), out_dir=tmp_path)
    assert fake.calls[0][1] == "vi-VN-HoaiMyNeural" and fake.calls[0][0].startswith("Tại sao")


def test_second_preview_of_the_same_thing_comes_from_the_cache(fake, tmp_path):
    first = tts.synthesize_preview(ARIA, out_dir=tmp_path)
    second = tts.synthesize_preview(ARIA, out_dir=tmp_path)
    assert first == second and len(fake.calls) == 1
    tts.synthesize_preview(ARIA, speed=0.9, out_dir=tmp_path)                    # other speed = new request
    assert len(fake.calls) == 2


def test_service_failure_becomes_tts_unavailable_and_leaves_no_files(fake, tmp_path):
    fake.behaviour = "raise"
    with pytest.raises(tts.TTSUnavailable, match="internet connection"):
        tts.synthesize_preview(ARIA, out_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_empty_audio_is_an_error_not_a_cached_file(fake, tmp_path):
    fake.behaviour = "empty"
    with pytest.raises(tts.TTSUnavailable, match="no audio"):
        tts.synthesize_preview(ARIA, out_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_slow_service_times_out(fake, tmp_path, monkeypatch):
    monkeypatch.setattr(tts, "TIMEOUT_S", 0.2)
    fake.behaviour = "slow"
    with pytest.raises(tts.TTSUnavailable, match="did not answer"):
        tts.synthesize_preview(ARIA, out_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_works_when_called_from_inside_a_running_event_loop(fake, tmp_path):
    """Streamlit and notebooks may already run a loop in the calling thread."""
    async def caller():
        return tts.synthesize_preview(ARIA, out_dir=tmp_path)
    assert asyncio.run(caller()).read_bytes() == AUDIO


def test_a_voice_of_another_engine_is_refused(fake, tmp_path):
    other = VoiceProfile("x-voice", "X", "en", "en-US", "male", engine="other", engine_voice="x")
    with pytest.raises(ValueError):
        tts.synthesize_preview(other, out_dir=tmp_path)


# ------------------------------------------------------------------ library check
def test_verify_library_reports_voices_the_engine_does_not_know(monkeypatch):
    monkeypatch.setitem(sys.modules, "edge_tts", FakeEdge(voices=("en-US-AriaNeural", "vi-VN-HoaiMyNeural")))
    monkeypatch.setattr(tts, "is_available", lambda: True)
    result = tts.verify_library(builtin_library())
    assert result.ok == ["en-aria", "vi-hoaimy"]
    assert "vi-namminh" in result.missing and "en-guy" in result.missing
    assert set(result.ok) | set(result.missing) == {v.voice_id for v in builtin_library()}


def test_verify_without_the_package_raises_tts_unavailable(monkeypatch):
    monkeypatch.setattr(tts, "is_available", lambda: False)
    with pytest.raises(tts.TTSUnavailable):
        tts.verify_library(builtin_library())


# ------------------------------------------------------------------ bundled samples and get_preview
HOAIMY = builtin_library().get("vi-hoaimy")


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    """Redirect the default folders so nothing is written into the real repo."""
    monkeypatch.setattr(tts, "BUNDLED_DIR", tmp_path / "bundled")
    monkeypatch.setattr(tts, "PREVIEW_DIR", tmp_path / "cache")
    return tmp_path


def put_bundled(voice, data=b"BUNDLED"):
    path = tts.bundled_path(voice)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_bundled_path_is_named_after_the_voice_id(dirs):
    assert tts.bundled_path(ARIA) == dirs / "bundled" / "en-aria.mp3"


def test_has_bundled_needs_a_non_empty_file(dirs):
    assert not tts.has_bundled(ARIA)
    put_bundled(ARIA, b"")
    assert not tts.has_bundled(ARIA)
    put_bundled(ARIA)
    assert tts.has_bundled(ARIA)


def test_bundled_sample_plays_offline_without_the_package(dirs, monkeypatch):
    monkeypatch.setattr(tts, "is_available", lambda: False)
    put_bundled(ARIA)
    assert tts.can_preview(ARIA, 1.0)
    assert tts.get_preview(ARIA, 1.0).read_bytes() == b"BUNDLED"


def test_bundled_sample_is_only_for_normal_speed(dirs, monkeypatch):
    monkeypatch.setattr(tts, "is_available", lambda: False)
    put_bundled(ARIA)
    assert not tts.can_preview(ARIA, 1.1)
    with pytest.raises(tts.TTSUnavailable):
        tts.get_preview(ARIA, 1.1)


def test_other_speeds_use_live_synthesis_when_available(dirs, fake):
    put_bundled(ARIA)
    assert tts.can_preview(ARIA, 1.1)
    assert tts.get_preview(ARIA, 1.1).read_bytes() == AUDIO
    assert fake.calls[0][2] == "+10%"


def test_no_sample_and_no_engine_means_no_preview(dirs, monkeypatch):
    monkeypatch.setattr(tts, "is_available", lambda: False)
    assert not tts.can_preview(HOAIMY, 1.0)
    with pytest.raises(tts.TTSUnavailable, match="pip install edge-tts"):
        tts.get_preview(HOAIMY, 1.0)


def test_bundled_sample_wins_over_live_synthesis_at_normal_speed(dirs, fake):
    put_bundled(ARIA)
    assert tts.get_preview(ARIA, 1.0).read_bytes() == b"BUNDLED" and fake.calls == []


def test_get_preview_rejects_a_speed_outside_the_library_range(dirs, fake):
    with pytest.raises(ValueError):
        tts.get_preview(ARIA, 2.0)


def test_make_bundled_previews_creates_one_sample_per_voice_and_skips_existing(dirs, fake):
    lib = builtin_library()
    put_bundled(ARIA)                                                    # already there: must be kept
    written = tts.make_bundled_previews(lib)
    assert {p.name for p in written} == {f"{v.voice_id}.mp3" for v in lib if v.voice_id != "en-aria"}
    assert all(p.read_bytes() == AUDIO for p in written)
    assert tts.bundled_path(ARIA).read_bytes() == b"BUNDLED"
    assert all(tts.has_bundled(v) for v in lib)
    assert len(fake.calls) == len(lib) - 1                              # one request per missing voice


def test_make_bundled_previews_force_refreshes_everything(dirs, fake):
    lib = builtin_library()
    put_bundled(ARIA)
    assert len(tts.make_bundled_previews(lib, force=True)) == len(lib)
    assert tts.bundled_path(ARIA).read_bytes() == AUDIO


def test_make_bundled_previews_without_the_package_fails_clearly(dirs, monkeypatch):
    monkeypatch.setattr(tts, "is_available", lambda: False)
    with pytest.raises(tts.TTSUnavailable):
        tts.make_bundled_previews(builtin_library())


# ------------------------------------------------------------------ CLI --make-previews
def test_cli_make_previews_writes_the_samples(dirs, fake, capsys):
    from modules.voice_library import cli
    assert cli.main(["--make-previews"]) == 0
    out = capsys.readouterr().out
    assert "wrote 8 sample(s)" in out and "8/8" in out
    assert len(list((dirs / "bundled").glob("*.mp3"))) == 8


def test_cli_make_previews_without_the_package_returns_2(dirs, monkeypatch, capsys):
    from modules.voice_library import cli
    monkeypatch.setattr(tts, "is_available", lambda: False)
    assert cli.main(["--make-previews"]) == 2
    assert "no previews made" in capsys.readouterr().out


# ------------------------------------------------------------------ narration: cleaning and the no-audio fallback
def test_clean_text_removes_invisible_characters_and_keeps_vietnamese_letters():
    import unicodedata
    raw = unicodedata.normalize("NFD", "Hai yếu tố​ thường bổ trợ nhau﻿, “thay vì” đối lập…")
    out = tts.clean_text(raw)
    assert out == 'Hai yếu tố thường bổ trợ nhau, "thay vì" đối lập...'
    assert unicodedata.is_normalized("NFC", out)


def test_split_pieces_cuts_at_punctuation_and_joins_short_pieces():
    s = "Hai yếu tố thường bổ trợ nhau, thay vì đối lập như hai con đường hoàn toàn tách biệt."
    assert tts.split_pieces(s) == ["Hai yếu tố thường bổ trợ nhau,", "thay vì đối lập như hai con đường hoàn toàn tách biệt."]
    assert tts.split_pieces("Ồ, vậy à, hay quá.") == ["Ồ, vậy à, hay quá."]


class NoAudioReceived(Exception):
    pass


def test_save_speech_splits_the_text_when_the_service_sends_no_audio(fake, tmp_path):
    whole = "Hai yếu tố thường bổ trợ nhau, thay vì đối lập như hai con đường hoàn toàn tách biệt."
    original = fake.Communicate.save

    async def save(self, path):
        if self.text == whole:
            fake.calls.append((self.text, self.voice, self.rate))
            raise NoAudioReceived("No audio was received.")
        await original(self, path)

    fake.Communicate.save = save
    out = tts.save_speech(whole, "vi-VN-HoaiMyNeural", tmp_path / "n.mp3")
    assert out.read_bytes() == AUDIO * 2
    texts = [c[0] for c in fake.calls]
    assert texts.count(whole) == tts.RETRY_ATTEMPTS and len(texts) == tts.RETRY_ATTEMPTS + 2
    assert not list(tmp_path.glob("*.part")) and not list(tmp_path.glob("*.tmp"))


def test_save_speech_does_not_split_on_network_errors(fake, tmp_path):
    fake.behaviour = "raise"
    with pytest.raises(tts.TTSUnavailable, match="ConnectionError"):
        tts.save_speech("Một câu, rồi một câu nữa thật dài để đọc.", "vi-VN-HoaiMyNeural", tmp_path / "n.mp3")
    assert len(fake.calls) == tts.RETRY_ATTEMPTS
