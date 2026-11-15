"""Tests of the voice library and the language detector. Expected values come from the rules in the
module docstrings (valid ids, language/locale pairing, speed range, ASSUMED wpm fallback), not
from copying the library's own output."""
import json

import pytest

from core.config import VOICE_WPM
from modules.pipeline.sample_claims import get_sample_claims, pack_language, topic_keys
from modules.voice_library.language import detect_language
from modules.voice_library.library import (BUILTIN_VOICES, LANGUAGES, SAMPLE_TEXT, SPEED_MAX, SPEED_MIN,
                                           UnknownVoiceError, VoiceLibrary, VoiceLibraryError, VoiceProfile,
                                           builtin_library, load_library)


def vp(voice_id="en-test", **kw):
    base = dict(voice_id=voice_id, name="Test", language="en", locale="en-US", gender="female",
                engine="edge-tts", engine_voice="en-US-TestNeural")
    return VoiceProfile(**{**base, **kw})


# ------------------------------------------------------------------ built-in data
def test_builtin_library_offers_english_and_vietnamese():
    lib = builtin_library()
    assert lib.languages() == ["en", "vi"]
    assert len(lib.list("en")) >= 2 and len(lib.list("vi")) >= 2
    assert len({v.voice_id for v in lib}) == len(BUILTIN_VOICES) == len(lib)


def test_each_language_has_both_genders_to_choose_from():
    lib = builtin_library()
    for lang in LANGUAGES:
        assert {v.gender for v in lib.list(lang)} == {"female", "male"}


def test_builtin_engine_voice_names_match_their_locale():
    for v in BUILTIN_VOICES:
        assert v.engine_voice.startswith(v.locale + "-"), v.voice_id


def test_defaults_exist_and_speak_their_language():
    lib = builtin_library()
    for lang in lib.languages():
        assert lib.default(lang).language == lang


def test_no_builtin_voice_claims_a_measured_speaking_rate():
    """The report asks for a measurement (to-do 12/14); until then nothing may pretend to have one."""
    assert all(v.measured_wpm is None and not v.wpm_is_measured for v in BUILTIN_VOICES)


def test_sample_texts_cover_every_language_and_are_in_that_language():
    assert set(SAMPLE_TEXT) == set(LANGUAGES)
    for lang, text in SAMPLE_TEXT.items():
        assert detect_language(text) == lang


# ------------------------------------------------------------------ queries
def test_list_filters_combine():
    lib = builtin_library()
    assert {v.locale for v in lib.list("en")} == {"en-US", "en-GB"}
    assert all(v.gender == "male" and v.language == "vi" for v in lib.list("vi", gender="male"))
    assert [v.voice_id for v in lib.list(locale="en-GB", gender="female")] == ["en-sonia"]
    assert lib.list() == list(lib)


def test_list_rejects_an_unknown_language():
    with pytest.raises(ValueError):
        builtin_library().list("fr")


def test_get_unknown_voice_lists_the_valid_ids():
    with pytest.raises(UnknownVoiceError) as exc:
        builtin_library().get("nope")
    assert "vi-hoaimy" in str(exc.value) and "'nope'" in str(exc.value)


def test_contains():
    lib = builtin_library()
    assert "en-aria" in lib and "nope" not in lib


def test_default_for_a_language_without_voices_is_an_error():
    lib = VoiceLibrary([vp()])
    assert lib.languages() == ["en"]
    with pytest.raises(UnknownVoiceError):
        lib.default("vi")


# ------------------------------------------------------------------ profile validation
@pytest.mark.parametrize("kw", [
    {"voice_id": "Bad Id"}, {"voice_id": "-x"}, {"voice_id": ""},
    {"name": "  "},
    {"language": "fr", "locale": "fr-FR"},
    {"locale": "vi-VN"},                               # locale of another language
    {"gender": "robot"},
    {"engine_voice": ""},
    {"measured_wpm": 0}, {"measured_wpm": -5},
])
def test_invalid_profiles_are_rejected(kw):
    with pytest.raises(VoiceLibraryError):
        vp(**kw)


def test_label_names_the_voice_for_people():
    assert vp(name="Hoài My", language="vi", locale="vi-VN").label == "Hoài My · female · vi-VN"


# ------------------------------------------------------------------ speaking rate
def test_unmeasured_voice_plans_with_the_project_assumption():
    v = vp()
    assert v.base_wpm == VOICE_WPM and v.planning_wpm() == VOICE_WPM


def test_measured_voice_uses_its_own_rate_and_speed_scales_it():
    v = vp(measured_wpm=200.0)
    assert v.wpm_is_measured and v.planning_wpm() == 200.0
    assert v.planning_wpm(1.1) == pytest.approx(220.0)
    assert v.planning_wpm(0.8) == pytest.approx(160.0)


@pytest.mark.parametrize("speed", [SPEED_MIN - 0.01, SPEED_MAX + 0.01, 0, -1])
def test_out_of_range_speed_is_rejected(speed):
    with pytest.raises(ValueError):
        vp().planning_wpm(speed)


def test_speed_range_boundaries_are_allowed():
    v = vp()
    assert v.planning_wpm(SPEED_MIN) == pytest.approx(VOICE_WPM * SPEED_MIN)
    assert v.planning_wpm(SPEED_MAX) == pytest.approx(VOICE_WPM * SPEED_MAX)


# ------------------------------------------------------------------ construction rules
def test_duplicate_ids_are_rejected():
    with pytest.raises(VoiceLibraryError):
        VoiceLibrary([vp("a-1"), vp("a-1")])


def test_default_must_be_a_voice_of_that_language():
    with pytest.raises(VoiceLibraryError):
        VoiceLibrary([vp("en-a")], {"en": "missing"})
    with pytest.raises(VoiceLibraryError):
        VoiceLibrary([vp("en-a"), vp("vi-a", language="vi", locale="vi-VN", engine_voice="vi-VN-ANeural")],
                     {"en": "vi-a"})


def test_first_voice_of_a_language_is_its_default_when_none_is_given():
    lib = VoiceLibrary([vp("en-b"), vp("en-a")])
    assert lib.default("en").voice_id == "en-b"


def test_extended_replaces_same_id_and_appends_new_ones():
    base = builtin_library()
    measured = VoiceProfile("en-aria", "Aria", "en", "en-US", "female", "edge-tts", "en-US-AriaNeural", measured_wpm=171.0)
    new = vp("en-extra")
    lib = base.extended([measured, new])
    assert lib.get("en-aria").measured_wpm == 171.0
    assert "en-extra" in lib and len(lib) == len(base) + 1
    assert [v.voice_id for v in lib][:len(base)] == [v.voice_id for v in base]     # order is kept
    assert base.get("en-aria").measured_wpm is None                                   # the original is untouched


# ------------------------------------------------------------------ JSON
def write(tmp_path, data):
    f = tmp_path / "voices.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    return f


def test_json_round_trip(tmp_path):
    lib = builtin_library()
    f = tmp_path / "lib.json"
    f.write_text(lib.to_json(), encoding="utf-8")
    voices, defaults = VoiceLibrary.parse_json(f)
    assert voices == list(lib) and defaults == {"en": "en-aria", "vi": "vi-hoaimy"}


def test_load_library_without_a_file_is_the_builtin_one(tmp_path):
    assert list(load_library(tmp_path / "missing.json")) == list(builtin_library())


def test_user_file_can_add_a_voice_and_a_measured_rate(tmp_path):
    f = write(tmp_path, {"voices": [
        {"voice_id": "en-aria", "name": "Aria", "language": "en", "locale": "en-US", "gender": "female",
         "engine_voice": "en-US-AriaNeural", "measured_wpm": 171.3},
        {"voice_id": "vi-extra", "name": "Extra", "language": "vi", "locale": "vi-VN", "gender": "male",
         "engine_voice": "vi-VN-ExtraNeural"}],
        "defaults": {"vi": "vi-extra"}})
    lib = load_library(f)
    assert lib.get("en-aria").planning_wpm() == pytest.approx(171.3)
    assert lib.default("vi").voice_id == "vi-extra" and len(lib) == len(builtin_library()) + 1


@pytest.mark.parametrize("content", [
    "not json", "[]", '{"voices": "x"}', '{"voices": [1]}',
    '{"voices": [{"voice_id": "a-b", "name": "A", "language": "en", "locale": "en-US", "gender": "female",'
    ' "engine_voice": "x", "colour": "red"}]}',                                 # unknown key
    '{"voices": [{"voice_id": "a-b"}]}',                                          # missing fields
    '{"voices": [], "defaults": []}',
])
def test_broken_user_files_raise_instead_of_being_ignored(tmp_path, content):
    f = tmp_path / "bad.json"
    f.write_text(content, encoding="utf-8")
    with pytest.raises(VoiceLibraryError):
        load_library(f)


# ------------------------------------------------------------------ language detector
@pytest.mark.parametrize("text, expected", [
    ("Sleep is an active process during which the brain sorts memories.", "en"),
    ("Giấc ngủ là lúc não sắp xếp ký ức và dọn sạch chất thải tích tụ trong ngày.", "vi"),
    ("Lạm phát là khi giá cả tăng dần theo thời gian.", "vi"),
    ("Prices rose 3.5% at the café last year.", "en"),            # one accented word is not Vietnamese
    ("TP.HCM bị ngập khi mưa lớn.", "vi"),
])
def test_detect_language(text, expected):
    assert detect_language(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "123 456 7.8", "!!! ???"])
def test_detect_language_gives_none_when_there_is_nothing_to_judge(text):
    assert detect_language(text) is None


@pytest.mark.parametrize("key", topic_keys())
def test_every_claim_pack_is_detected_as_its_declared_language(key):
    text = " ".join(c.text for c in get_sample_claims(key))
    assert detect_language(text) == pack_language(key)
