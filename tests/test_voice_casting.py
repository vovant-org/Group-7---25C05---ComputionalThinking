"""Voice casting (voice, speed and pitch follow the topic), unmarked-Vietnamese detection and Edge pitch plumbing."""
import pytest

from modules.providers import edge_tts_provider as edge
from modules.video.voice import EdgeEngine
from modules.voice_library.casting import MOODS, PITCH_MAX, PITCH_MIN, cast_voice, check_pitch, pick_mood
from modules.voice_library.language import detect_language
from modules.voice_library.library import SPEED_MAX, SPEED_MIN, VoiceLibrary, VoiceProfile, builtin_library

LIB = builtin_library()


@pytest.mark.parametrize("lang, topic, mood, voice", [
    ("en", "Why does sleep matter?", "calm", "en-sonia"),
    ("en", "Why do prices keep rising?", "serious", "en-christopher"),
    ("en", "How does a rocket reach orbit?", "energetic", "en-guy"),
    ("en", "Explain photosynthesis to children", "warm", "en-jenny"),
    ("en", "How do birds migrate?", "curious", "en-aria"),
    ("vi", "Tại sao TP.HCM ngập khi mưa lớn?", "serious", "vi-namminh"),
    ("vi", "Giấc ngủ quan trọng thế nào?", "calm", "vi-hoaimy"),
])
def test_the_topic_picks_the_mood_and_a_voice_of_the_right_language(lang, topic, mood, voice):
    c = cast_voice(LIB, lang, topic)
    assert (c.mood, c.voice_id) == (mood, voice)
    assert LIB.get(c.voice_id).language == lang
    assert (c.speed, c.pitch_hz) == (MOODS[mood].speed, MOODS[mood].pitch_hz)
    assert c.reason


def test_cue_words_in_the_question_beat_the_domain():
    assert pick_mood("Why do prices rise? A friendly story for my family")[0] == "warm"
    assert pick_mood("How did the 2008 financial crisis start?")[0] == "serious"
    assert pick_mood("Breathing exercises to relax before bed")[0] == "calm"


def test_an_empty_or_unknown_topic_keeps_the_default_voice():
    for topic in ["", "   ", "What is a cat?"]:
        c = cast_voice(LIB, "en", topic)
        assert c.voice_id == LIB.default("en").voice_id and c.pitch_hz == 0 and c.speed == 1.0


def test_the_material_counts_when_the_question_is_vague():
    c = cast_voice(LIB, "en", "Explain this", ["Inflation means prices rise and money buys fewer goods every year."] * 3)
    assert c.mood == "serious"


def test_casting_stays_inside_the_allowed_ranges_and_handles_unknown_voices():
    lib = VoiceLibrary([VoiceProfile("en-zed", "Zed", "en", "en-AU", "male", engine_voice="en-AU-Zed")])
    for mood_topic in ["Why does sleep matter?", "How does a rocket reach orbit?", "Why do prices keep rising?"]:
        c = cast_voice(lib, "en", mood_topic)
        assert c.voice_id == "en-zed"
        assert SPEED_MIN <= c.speed <= SPEED_MAX and PITCH_MIN <= c.pitch_hz <= PITCH_MAX
    with pytest.raises(ValueError):
        check_pitch(PITCH_MAX + 1)


def test_the_casting_key_changes_only_when_the_proposal_changes():
    a, b = cast_voice(LIB, "en", "Why does sleep matter?"), cast_voice(LIB, "en", "Is sleep important for memory?")
    assert a.key == b.key
    assert a.key != cast_voice(LIB, "en", "How does a rocket reach orbit?").key


# ------------------------------------------------------------------ language: Vietnamese without tone marks
@pytest.mark.parametrize("text, expected", [
    ("tai sao gia ca tang nhanh vay", "vi"),
    ("giac ngu quan trong nhu the nao", "vi"),
    ("Why do prices keep rising so fast?", "en"),
    ("Do you have a ban on the van?", "en"),
    ("Ba", "en"),                                   # too short to call Vietnamese without marks
])
def test_unmarked_vietnamese_is_detected(text, expected):
    assert detect_language(text) == expected


# ------------------------------------------------------------------ Edge pitch
def test_edge_options_pass_pitch_only_when_it_changes_the_voice():
    assert edge.tts_options(1.0, 0) == {"rate": "+0%"}
    assert edge.tts_options(0.9, -3) == {"rate": "-10%", "pitch": "-3Hz"}


def test_engine_name_and_preview_cache_keep_old_ids_at_zero_pitch():
    v = LIB.get("en-aria")
    assert EdgeEngine(v, 1.0).name == "edge-en-US-AriaNeural-+0%"
    assert EdgeEngine(v, 1.0, 2).name == "edge-en-US-AriaNeural-+0%-+2Hz"
    assert edge.preview_path(v, "x") == edge.preview_path(v, "x", pitch_hz=0) != edge.preview_path(v, "x", pitch_hz=2)


def test_a_bundled_sample_is_not_used_for_a_changed_pitch(tmp_path, monkeypatch):
    v = LIB.get("en-aria")
    (tmp_path / "en-aria.mp3").write_bytes(b"x")
    monkeypatch.setattr(edge, "is_available", lambda: False)
    assert edge.can_preview(v, 1.0, tmp_path)
    assert not edge.can_preview(v, 1.0, tmp_path, pitch_hz=2)


@pytest.mark.parametrize("topic, mood", [
    ("Lạm phát hoạt động ra sao?", "serious"),              # the visual analysis alone stays "generic" here
    ("Thị trường chứng khoán vận hành thế nào?", "serious"),
    ("lam phat la gi va tai sao no xay ra", "serious"),      # Vietnamese without tone marks
    ("How does AI work?", "energetic"),
])
def test_subject_hints_fill_in_when_the_topic_analysis_is_generic(topic, mood):
    assert pick_mood(topic)[0] == mood


def test_vietnamese_ai_meaning_who_is_not_read_as_technology():
    assert pick_mood("Ai là người phát minh ra bóng đèn?")[1] != "tech"


@pytest.mark.parametrize("text, lang", [
    ("tai sao gia ca tang nhanh nhu vay", "vi"),
    ("Giấc ngủ quan trọng thế nào", "vi"),
    ("Why do prices keep rising so fast", "en"),
    ("Ban and the cat sat on a mat", "en"),
])
def test_language_detection_also_handles_unmarked_vietnamese(text, lang):
    assert detect_language(text) == lang
