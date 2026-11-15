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
