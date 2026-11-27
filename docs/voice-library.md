# Voice library (English and Vietnamese)

Lets the user pick the voice and speaking speed of the video. Report links: 1.2.2 (input "Voice settings:
language, speaking speed"), 4(e) `synthesize_voice(text, lang, wpm)`, 5.9.7 (TTS options G1-G4), to-do 12 and 14.

## What the user can do
- **Streamlit**: sidebar `1 · Request` → *Narration language* (English / Tiếng Việt) filters the claim packs
  and the voices; `2 · Voice` → pick a voice, set *Speaking speed* (0.75x-1.25x), open *Voice library* to see
  every voice, listen to the voices before choosing (see below).
- **CLI**: `python -m modules.pipeline.cli "<request>" --topic sleep_vi --voice vi-hoaimy --speed 1.1`
- **List / check voices**: `python -m modules.voice_library.cli [--language vi] [--check]`

## Listening before choosing
Sidebar `2 · Voice` → **🎧 Listen to every voice**: each voice of the chosen language has **▶** (play a sample)
and **Use** (choose it). **🔊 Hear this voice** plays the currently selected voice.
Two audio sources, in this order:
1. **Bundled samples** `assets/voice_previews/<voice_id>.mp3` (normal speed only). They play offline and need no
   `edge-tts`. Create them once, on a machine with internet, then commit the folder:
   `pip install edge-tts` then `python -m modules.voice_library.cli --make-previews` (add `--force` to redo).
2. **Live synthesis** through `edge-tts` for any speed; cached in `outputs/voice_previews/` (git-ignored).
Without either, the sidebar tells the user what to do. The samples are the fixed public sentences in
`SAMPLE_TEXT` (one English, one Vietnamese); user text is never sent.

## Automatic language and voice casting (New Project → step 3 "Voice")
- **Language** is detected from the question + material (`modules/voice_library/language.py`): Vietnamese letters /
  tone marks, and now also Vietnamese typed **without** tone marks ("tai sao gia ca tang"). Step 3 shows only the
  voices of that language.
- **Voice casting** (`modules/voice_library/casting.py`): the topic analysis of the visual engine (domain, audience)
  plus a few tone cue words choose a mood, and the mood chooses voice, speaking speed and pitch:

| mood | when | voice (en / vi) | speed | pitch |
|---|---|---|---|---|
| calm | sleep, health, "relax", "stress" | Sonia / Hoài My | 0.90x | -2 Hz |
| serious | economy, weather/flood, "crisis", "history" | Christopher / Nam Minh | 0.95x | -3 Hz |
| energetic | technology, space, "sport", "future" | Guy / Nam Minh | 1.10x | +2 Hz |
| warm | children, "story", "family", "friendly" | Jenny / Hoài My | 0.95x | +3 Hz |
| curious | nature, students | Aria / Hoài My | 1.00x | +1 Hz |
| neutral | anything else / no topic yet | default voice | 1.00x | 0 Hz |

  The toggle **Auto-match the voice to my topic** (on by default) re-applies the proposal whenever the topic or
  language changes. Picking a voice by hand turns it off; **Use the suggested voice** turns it back on. Pitch is
  sent to edge-tts only (`pitch="+2Hz"`), so the offline system voice ignores it; at pitch 0 engine names, preview
  cache files and project ids are identical to before. Offline and deterministic: no text is sent anywhere.
  When the topic analysis cannot decide the subject ("Lạm phát hoạt động ra sao?"), a short list of subject words in
  `casting.py` (`_DOMAIN_HINTS`: inflation/lạm phát, chứng khoán, công nghệ, sức khỏe...) fills it in, for the voice only.
  ASSUMPTION: the mood table is our own judgement, not tested with listeners.

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
