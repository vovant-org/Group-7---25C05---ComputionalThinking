"""Voice casting: pick the voice, speaking speed and pitch that suit the TOPIC of the input.

Report links: 1.2.2 (input "Voice settings: language, speaking speed"), 5.9.7 (TTS options). The user no longer has
to guess which voice fits: the app reads the question (and the material, when there is some), recognises the kind
of subject and proposes a delivery for it, e.g.

    "Why does sleep matter?"              -> calm      (female, 0.90x, slightly lower pitch)
    "Why do prices keep rising?"          -> serious   (male, 0.95x, lower pitch)
    "How does a rocket reach orbit?"      -> energetic (male, 1.10x, slightly higher pitch)
    "Explain photosynthesis to children"  -> warm      (female, 0.95x, higher pitch)

How: the topic analysis that already drives the visuals (`modules.visual_engine.topic.analyse_topic`: domain and
audience) plus a few cue words for the tone ("crisis", "relax", "exciting", ...). Deterministic, offline, instant:
nothing is sent anywhere, so it can run on every keystroke of the form.

ASSUMPTION (not measured with listeners): the mood table and the voice preferences are our own judgement. The user
can always switch the automatic choice off and pick any voice. Pitch only changes the Edge neural voices; the
offline system voice ignores it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from modules.visual_engine import textmatch as T
from modules.visual_engine.topic import analyse_topic
from modules.voice_library.library import SPEED_MAX, SPEED_MIN, VoiceLibrary, VoiceProfile

PITCH_MIN, PITCH_MAX = -10, 10          # Hz offset sent to edge-tts; small on purpose so a voice stays natural


@dataclass(frozen=True)
class Tone:
    label: str                           # shown in the UI
    speed: float                         # speaking-speed multiplier
    pitch_hz: int                        # edge-tts pitch offset
    gender: Optional[str]                # preferred gender, None = no preference
    prefer: tuple[str, ...]              # preferred voice ids, best first (voices of other languages are skipped)


MOODS: dict[str, Tone] = {
    "calm": Tone("Calm & soothing", 0.90, -2, "female", ("en-sonia", "en-aria", "vi-hoaimy")),
    "warm": Tone("Warm & friendly", 0.95, 3, "female", ("en-jenny", "en-aria", "vi-hoaimy")),
    "serious": Tone("Clear & authoritative", 0.95, -3, "male", ("en-christopher", "en-ryan", "vi-namminh")),
    "energetic": Tone("Bright & energetic", 1.10, 2, "male", ("en-guy", "en-christopher", "vi-namminh")),
    "curious": Tone("Curious & engaging", 1.00, 1, "female", ("en-aria", "en-jenny", "vi-hoaimy")),
    "neutral": Tone("Neutral narrator", 1.00, 0, None, ()),
}

DOMAIN_MOOD = {"sleep": "calm", "nature": "curious", "space": "energetic", "tech": "energetic",
               "economy": "serious", "weather": "serious", "generic": "neutral"}
DOMAIN_LABEL = {"sleep": "sleep & health", "nature": "nature", "space": "space", "tech": "technology",
                "economy": "economy & money", "weather": "weather & climate", "generic": "general knowledge"}

# Cue words that override the domain: the tone of the question matters more than its subject.
_CUES: dict[str, list[str]] = {
    "serious": ["war", "crisis", "disaster", "death", "danger", "risk", "pollution", "poverty", "disease", "pandemic",
                "accident", "law", "history", "chiến tranh", "khủng hoảng", "thảm họa", "tử vong", "nguy hiểm",
                "ô nhiễm", "nghèo", "dịch bệnh", "tai nạn", "pháp luật", "lịch sử", "rủi ro"],
    "calm": ["relax", "calm", "meditation", "stress", "breathing", "mindful", "insomnia", "thư giãn", "bình tĩnh",
             "thiền", "căng thẳng", "hít thở", "mất ngủ"],
    "energetic": ["sport", "football", "game", "exciting", "fast", "speed", "record", "robot", "future", "thể thao",
                  "bóng đá", "trò chơi", "thú vị", "nhanh", "tốc độ", "kỷ lục", "tương lai"],
    "warm": ["friendly", "fun", "story", "family", "kid", "child", "children", "thân thiện", "vui", "câu chuyện",
             "gia đình", "trẻ em", "bé"],
}
_CUE_ORDER = ("serious", "calm", "warm", "energetic")       # first match wins

# Subject words that pin the domain when the visual-engine analysis stays "generic" (e.g. "lạm phát" alone is shared
# by the economy and tech pictures, so the analysis cannot decide). Used for the voice only; the visuals are unchanged.
_DOMAIN_HINTS: dict[str, list[str]] = {
    "economy": ["inflation", "economy", "economic", "stock", "finance", "tax", "unemployment", "lạm phát", "kinh tế",
                "chứng khoán", "tài chính", "thuế", "thất nghiệp", "thị trường", "lam phat", "kinh te"],
    "sleep": ["sleep", "health", "nutrition", "diet", "exercise", "giấc ngủ", "ngủ", "sức khỏe", "dinh dưỡng",
              "tập thể dục", "giac ngu", "suc khoe"],
    "tech": ["ai", "technology", "smartphone", "robot", "công nghệ", "điện thoại", "trí tuệ nhân tạo", "cong nghe"],
    "weather": ["climate", "flood", "storm", "khí hậu", "lũ", "bão", "ngập", "ngap"],
    "nature": ["ecosystem", "biology", "hệ sinh thái", "sinh học", "thiên nhiên"],
    "space": ["universe", "galaxy", "star", "vũ trụ", "thiên hà", "ngôi sao"],
}


_EN_ONLY = frozenset({"ai"})                                 # "ai" means "who" in Vietnamese


def _hint_domain(words: list[str], vn: bool) -> Optional[str]:
    hits = [(i, d) for d, kws in _DOMAIN_HINTS.items()
            if (i := T.find_keywords(words, [k for k in kws if not (vn and k in _EN_ONLY)], vn)) is not None]
    return min(hits)[1] if hits else None


@dataclass(frozen=True)
class VoiceCasting:
    mood: str
    label: str
    voice_id: str
    speed: float
    pitch_hz: int
    domain: str
    audience: str
    reason: str

    @property
    def key(self) -> tuple:
        """Changes only when the proposal changes (the UI re-applies the casting on a new key)."""
        return (self.voice_id, self.mood, self.speed, self.pitch_hz)


def pick_mood(topic: str, texts: list[str] = (), instructions: str = "") -> tuple[str, str, str, str]:
    """(mood, domain, audience, why) for a question, its material and the user's extra instructions."""
    prof = analyse_topic(topic, list(texts))
    words_all = " ".join([topic, instructions] + list(texts))
    vn = T.has_vietnamese_marks(words_all)
    head = T.tokens(" ".join([topic, instructions]))         # cue words count in the question / instructions only
    for mood in _CUE_ORDER:
        if T.find_keywords(head, _CUES[mood], vn) is not None:
            return mood, prof.domain, prof.audience, "the wording of your question"
    if prof.audience == "kids":
        return "warm", prof.domain, prof.audience, "a young audience"
    domain = prof.domain
    if domain == "generic":
        domain = _hint_domain(head, vn) or _hint_domain(T.tokens(words_all), vn) or "generic"
    mood = DOMAIN_MOOD.get(domain, "neutral")
    if prof.audience == "students" and mood == "neutral":
        return "curious", domain, prof.audience, "a student audience"
    return mood, domain, prof.audience, f"this {DOMAIN_LABEL.get(domain, domain)} topic"


def _choose(voices: list[VoiceProfile], tone: Tone, fallback: VoiceProfile) -> VoiceProfile:
    if not voices:
        return fallback

    def score(v: VoiceProfile) -> tuple:
        pref = len(tone.prefer) - tone.prefer.index(v.voice_id) if v.voice_id in tone.prefer else 0
        return (pref, 1 if tone.gender and v.gender == tone.gender else 0, v.voice_id == fallback.voice_id)

    if not tone.prefer and tone.gender is None:
        return fallback
    return max(voices, key=score)


def cast_voice(lib: VoiceLibrary, language: str, topic: str, texts: list[str] = (),
               instructions: str = "") -> VoiceCasting:
    """The proposed voice (of `language`), speed and pitch for this input. Never raises for odd input."""
    mood, domain, audience, why = pick_mood(topic or "", list(texts or ()), instructions or "")
    if not (topic or "").strip() and not any(t.strip() for t in texts or ()):
        mood, why = "neutral", "no topic yet"
    tone = MOODS[mood]
    voice = _choose(lib.list(language=language), tone, lib.default(language))
    speed = round(min(SPEED_MAX, max(SPEED_MIN, tone.speed)), 2)
    pitch = int(min(PITCH_MAX, max(PITCH_MIN, tone.pitch_hz)))
    reason = f"{tone.label} delivery for {why}."
    return VoiceCasting(mood, tone.label, voice.voice_id, speed, pitch, domain, audience, reason)


def check_pitch(pitch_hz: int) -> int:
    if not PITCH_MIN <= int(pitch_hz) <= PITCH_MAX:
        raise ValueError(f"pitch must be between {PITCH_MIN} and {PITCH_MAX} Hz, got {pitch_hz}")
    return int(pitch_hz)
