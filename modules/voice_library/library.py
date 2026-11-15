"""Voice library: the voices a user can pick for the voice-over (English and Vietnamese).

Report links: 1.2.2 (input "Voice settings: language, speaking speed"), 4(e) ProviderAdapter
(`synthesize_voice(text, lang, wpm)`), 5.9.7 (TTS options G1-G4) and to-do items 12/14
(measure the real speaking rate).

A VoiceProfile describes ONE voice: who it is (name, language, gender) and how to call it
(engine + engine_voice). The pipeline only needs `planning_wpm`, the speaking rate it should plan
with. ASSUMPTION: until a voice has been measured (`measured_wpm`, from
`python -m evaluation.fit_tts_model`) every voice falls back to `core.config.VOICE_WPM`. The library
never invents a speaking rate.

The built-in list is plain data. Teams add or replace voices without touching code by putting a
JSON file at `data/voice_library.json` (see `docs/voice-library.md`).
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional

from core.config import DATA_DIR, VOICE_WPM

LANGUAGES = {"en": "English", "vi": "Tiếng Việt"}
GENDERS = ("female", "male")
ENGINE_EDGE = "edge-tts"
SPEED_MIN, SPEED_MAX = 0.75, 1.25            # speaking-speed multiplier the user may choose
USER_LIBRARY_FILE = DATA_DIR / "voice_library.json"

# Public sentences used to audition a voice (the report's own examples); never user text.
SAMPLE_TEXT = {
    "en": "Why does the same shopping basket cost more every year? That steady rise in prices has a name: inflation.",
    "vi": "Tại sao cùng một giỏ hàng mà mỗi năm lại đắt hơn? Sự tăng giá đều đặn đó có một cái tên: lạm phát.",
}

_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class VoiceLibraryError(ValueError):
    """The library or one of its voices is malformed."""


class UnknownVoiceError(KeyError):
    """No voice with that id (the message lists the valid ids)."""

    def __str__(self) -> str:                  # KeyError would print the message with extra quotes
        return str(self.args[0]) if self.args else ""


@dataclass(frozen=True)
class VoiceProfile:
    voice_id: str                  # our own stable slug, e.g. "vi-hoaimy"; never changes with the engine
    name: str                      # display name
    language: str                  # "en" | "vi"
    locale: str                    # "en-US", "en-GB", "vi-VN"
    gender: str                    # "female" | "male"
    engine: str = ENGINE_EDGE
    engine_voice: str = ""         # the engine's own voice name, e.g. "vi-VN-HoaiMyNeural"
    measured_wpm: Optional[float] = None   # None = not measured yet (to-do 12/14)
    notes: str = ""

    def __post_init__(self) -> None:
        if not _ID.match(self.voice_id):
            raise VoiceLibraryError(f"voice_id {self.voice_id!r} must be a lowercase slug (a-z, 0-9, '-')")
        if not self.name.strip():
            raise VoiceLibraryError(f"{self.voice_id}: name is empty")
        if self.language not in LANGUAGES:
            raise VoiceLibraryError(f"{self.voice_id}: language {self.language!r} not in {sorted(LANGUAGES)}")
        if not self.locale.startswith(self.language + "-"):
            raise VoiceLibraryError(f"{self.voice_id}: locale {self.locale!r} does not match language {self.language!r}")
        if self.gender not in GENDERS:
            raise VoiceLibraryError(f"{self.voice_id}: gender {self.gender!r} not in {GENDERS}")
        if not self.engine_voice.strip():
            raise VoiceLibraryError(f"{self.voice_id}: engine_voice is empty")
        if self.measured_wpm is not None and not self.measured_wpm > 0:
            raise VoiceLibraryError(f"{self.voice_id}: measured_wpm must be > 0, got {self.measured_wpm}")

    @property
    def label(self) -> str:
        return f"{self.name} · {self.gender} · {self.locale}"

    @property
    def base_wpm(self) -> float:
        """Measured speaking rate when we have one, otherwise the project-wide assumption."""
        return self.measured_wpm if self.measured_wpm is not None else VOICE_WPM

    @property
    def wpm_is_measured(self) -> bool:
        return self.measured_wpm is not None

    def planning_wpm(self, speed: float = 1.0) -> float:
        """Words per minute the planner should assume at this speaking speed (1.0 = normal)."""
        check_speed(speed)
        return self.base_wpm * speed


def check_speed(speed: float) -> float:
    if not SPEED_MIN <= speed <= SPEED_MAX:
        raise ValueError(f"speaking speed must be between {SPEED_MIN} and {SPEED_MAX}, got {speed}")
    return speed


# ASSUMPTION: engine voice names are the Microsoft Edge neural voices as we know them; they could
# not be checked against the live service while this was written. Run
# `python -m modules.voice_library.cli --check` (needs internet + `pip install edge-tts`) to confirm.
BUILTIN_VOICES: tuple[VoiceProfile, ...] = (
    VoiceProfile("en-aria", "Aria", "en", "en-US", "female", ENGINE_EDGE, "en-US-AriaNeural"),
    VoiceProfile("en-jenny", "Jenny", "en", "en-US", "female", ENGINE_EDGE, "en-US-JennyNeural"),
    VoiceProfile("en-guy", "Guy", "en", "en-US", "male", ENGINE_EDGE, "en-US-GuyNeural"),
    VoiceProfile("en-christopher", "Christopher", "en", "en-US", "male", ENGINE_EDGE, "en-US-ChristopherNeural"),
    VoiceProfile("en-sonia", "Sonia", "en", "en-GB", "female", ENGINE_EDGE, "en-GB-SoniaNeural"),
    VoiceProfile("en-ryan", "Ryan", "en", "en-GB", "male", ENGINE_EDGE, "en-GB-RyanNeural"),
    VoiceProfile("vi-hoaimy", "Hoài My", "vi", "vi-VN", "female", ENGINE_EDGE, "vi-VN-HoaiMyNeural"),
    VoiceProfile("vi-namminh", "Nam Minh", "vi", "vi-VN", "male", ENGINE_EDGE, "vi-VN-NamMinhNeural"),
)
BUILTIN_DEFAULTS = {"en": "en-aria", "vi": "vi-hoaimy"}


class VoiceLibrary:
    """An ordered, immutable collection of voices with one default voice per language."""

    def __init__(self, voices: Iterable[VoiceProfile], defaults: Optional[dict[str, str]] = None):
        self._voices: dict[str, VoiceProfile] = {}
        for v in voices:
            if v.voice_id in self._voices:
                raise VoiceLibraryError(f"duplicate voice_id {v.voice_id!r}")
            self._voices[v.voice_id] = v
        self._defaults: dict[str, str] = {}
        for lang in self.languages():
            wanted = (defaults or {}).get(lang)
            if wanted is not None and (wanted not in self._voices or self._voices[wanted].language != lang):
                raise VoiceLibraryError(f"default {wanted!r} for {lang!r} is not a {lang} voice in the library")
            self._defaults[lang] = wanted or next(v.voice_id for v in self._voices.values() if v.language == lang)

    # ---- container protocol
    def __len__(self) -> int:
        return len(self._voices)

    def __iter__(self) -> Iterator[VoiceProfile]:
        return iter(self._voices.values())

    def __contains__(self, voice_id: object) -> bool:
        return voice_id in self._voices

    # ---- queries
    def get(self, voice_id: str) -> VoiceProfile:
        try:
            return self._voices[voice_id]
        except KeyError:
            raise UnknownVoiceError(f"unknown voice {voice_id!r}; choose one of {sorted(self._voices)}") from None

    def languages(self) -> list[str]:
        """Languages that have at least one voice, in the order of LANGUAGES."""
        present = {v.language for v in self._voices.values()}
        return [lang for lang in LANGUAGES if lang in present]

    def list(self, language: Optional[str] = None, gender: Optional[str] = None,
             locale: Optional[str] = None) -> list[VoiceProfile]:
        if language is not None and language not in LANGUAGES:
            raise ValueError(f"language must be one of {sorted(LANGUAGES)}, got {language!r}")
        return [v for v in self._voices.values()
                if (language is None or v.language == language)
                and (gender is None or v.gender == gender)
                and (locale is None or v.locale == locale)]

    def default(self, language: str) -> VoiceProfile:
        if language not in self._defaults:
            raise UnknownVoiceError(f"no voice for language {language!r}; available: {self.languages()}")
        return self._voices[self._defaults[language]]

    def extended(self, voices: Iterable[VoiceProfile], defaults: Optional[dict[str, str]] = None) -> "VoiceLibrary":
        """A new library with `voices` added; a voice with an existing id REPLACES that voice."""
        merged = dict(self._voices)
        for v in voices:
            merged[v.voice_id] = v
        return VoiceLibrary(merged.values(), {**self._defaults, **(defaults or {})})

    # ---- JSON
    @staticmethod
    def parse_json(path: Path) -> tuple[list[VoiceProfile], dict[str, str]]:
        """Read {"voices": [{...}], "defaults": {"en": "..."}}. Unknown keys are an error."""
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise VoiceLibraryError(f"cannot read voice library {path}: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("voices"), list):
            raise VoiceLibraryError(f'{path}: expected an object with a "voices" list')
        fields = set(VoiceProfile.__dataclass_fields__)
        voices = []
        for i, raw in enumerate(data["voices"]):
            if not isinstance(raw, dict):
                raise VoiceLibraryError(f"{path}: voices[{i}] is not an object")
            extra = set(raw) - fields
            if extra:
                raise VoiceLibraryError(f"{path}: voices[{i}] has unknown keys {sorted(extra)}")
            try:
                voices.append(VoiceProfile(**raw))
            except TypeError as exc:
                raise VoiceLibraryError(f"{path}: voices[{i}]: {exc}") from exc
        defaults = data.get("defaults", {})
        if not isinstance(defaults, dict):
            raise VoiceLibraryError(f'{path}: "defaults" must be an object')
        return voices, defaults

    def to_json(self) -> str:
        return json.dumps({"voices": [asdict(v) for v in self], "defaults": dict(self._defaults)},
                          ensure_ascii=False, indent=2)


def builtin_library() -> VoiceLibrary:
    return VoiceLibrary(BUILTIN_VOICES, BUILTIN_DEFAULTS)


def load_library(user_file: Optional[Path] = None) -> VoiceLibrary:
    """Built-in voices plus the team's own file (`data/voice_library.json`) when it exists.

    A voice in the file with the same id as a built-in one replaces it, which is how a measured
    speaking rate is added. A broken file raises VoiceLibraryError (it is never silently ignored)."""
    lib = builtin_library()
    path = Path(user_file) if user_file is not None else USER_LIBRARY_FILE
    if path.exists():
        voices, defaults = VoiceLibrary.parse_json(path)
        lib = lib.extended(voices, defaults)
    return lib
