# Voice library (English and Vietnamese)

Lets the user pick the voice and speaking speed of the video. Report links: 1.2.2 (input "Voice settings:
language, speaking speed"), 4(e) `synthesize_voice(text, lang, wpm)`, 5.9.7 (TTS options G1-G4), to-do 12 and 14.

## What the user can do
- **Streamlit**: sidebar `1 · Request` → *Narration language* (English / Tiếng Việt) filters the claim packs
  and the voices; `2 · Voice` → pick a voice, set *Speaking speed* (0.75x-1.25x), open *Voice library* to see
  every voice, press *Hear this voice* to audition it (needs `edge-tts` + internet).
- **CLI**: `python -m modules.pipeline.cli "<request>" --topic sleep_vi --voice vi-hoaimy --speed 1.1`
- **List / check voices**: `python -m modules.voice_library.cli [--language vi] [--check]`

## Built-in voices
| id | name | locale | gender |
|---|---|---|---|
| en-aria (default) | Aria | en-US | female |
| en-jenny | Jenny | en-US | female |
| en-guy | Guy | en-US | male |
| en-christopher | Christopher | en-US | male |
| en-sonia | Sonia | en-GB | female |
| en-ryan | Ryan | en-GB | male |
| vi-hoaimy (default) | Hoài My | vi-VN | female |
| vi-namminh | Nam Minh | vi-VN | male |

Engine: the free `edge-tts` package (Microsoft Edge neural voices, option G1/G4 of 5.9.7).

## How a voice affects the pipeline
1. `voice.planning_wpm(speed)` replaces the fixed 165 wpm for claim selection (W_target = wpm x T / 60),
   the Scene Segmenter and the Voice Segmenter.
2. The simulated TTS speaks at that rate by default.
3. Language check: an English voice never reads Vietnamese claims and vice versa. The run stops at the
   voice stage with `VOICE_LANGUAGE_MISMATCH` before anything is planned (detector:
   `modules/voice_library/language.py`, Vietnamese letters/tone marks).
4. With no voice chosen, behaviour is identical to before (a regression test pins this).

## Add or change voices without code
Create `data/voice_library.json`; a voice with an existing id replaces the built-in one.
```json
{"voices": [{"voice_id": "en-aria", "name": "Aria", "language": "en", "locale": "en-US",
             "gender": "female", "engine_voice": "en-US-AriaNeural", "measured_wpm": 171.3}],
 "defaults": {"en": "en-aria"}}
```
A broken file is reported (error in the UI / `VoiceLibraryError`), never silently ignored.
After measuring real TTS (`evaluation/measure_tts.py`, `evaluation/fit_tts_model.py`), put the fitted
rate in `measured_wpm`; the UI then shows "measured" instead of "assumed".

## Honest limits
- **Speaking rates are ASSUMED**: every voice uses `VOICE_WPM` (165) until measured. Vietnamese counts
  one syllable as one "word", so 165 may be far from reality. Do not report durations as measured.
- Engine voice names are the ones we know for edge-tts; they were **not verified online** when this was
  written. Run `python -m modules.voice_library.cli --check` once with internet.
- The pipeline timeline still uses the **simulated** TTS; the preview does not feed the timeline.
- Only 2 Vietnamese voices are built in; add more through the JSON file (e.g. another engine).
- Vietnamese claim packs (`sleep_vi`, `inflation_vi`) are hand-written fixtures, like the English ones.
  Their sentence lengths were tuned so the default 90 s demo passes S12/S13. At 60 s or 120 s some runs
  still miss S13 (English too), because the N4 -> N3 -> N2 adjustment loop is not built yet.
- Privacy: a preview sends one fixed public sample sentence to an online service. User text is never sent.
