# Topic-aware Visual Engine (ANIMATION format)

Goal: not only swap the text, but give **every topic its own way of being drawn**. Before, the animation used
one stick figure and six props chosen only by `explain_pattern`; "sleep", "inflation" and "floods" looked the
same. Now the picture follows what the narration says.

Run: `python -m modules.video.make_video "Make a 60-second animated video about ..." --reference notes.txt`
(`--no-visual-engine` brings back the old animation). Tests: `python -m pytest tests/test_visual_engine.py`.
Benchmark: `python -m evaluation.visual_engine_benchmark`.

## The five steps and where they live

| Step | Module | What it does | Logic type |
|---|---|---|---|
| 1 Analyse the topic | `topic.py`, `textmatch.py` | domain, audience, concepts (objects the engine can draw), relations (orbits / flows / grows / causes), trend (rise / fall) | lexicon EN+VI, weighted counting (topic words x3) |
| 2 Choose the visual kit | `kits.py`, `engine.select_objects` | backdrop per domain (night sky, skyline, hills, starfield, rainy city, tech grid), presenter figure yes/no, the objects of each scene | lookup tables + ordered selection |
| 3 Motion by content | `objects.py` | animals walk (legs swing), birds fly (wings flap), fish swim, plants grow then bloom, planets orbit a sun, coins circulate between two places, prices step up/down, bars grow, flood water rises, rain falls, data packets travel | keyframe tracks (same `Layer`/`Track` as the old animation) |
| 4 Sync voice and subtitles | `sync.py` | each word gets a time (length + pause after punctuation); an object appears 0.2 s before its word | deterministic, option H1 per word |
| 5 Quality checks | `quality.py` | empty scenes, repeated visuals, subtitles, audio, duration, object-word sync | checks on real frames and the real timeline |

`engine.py` ties them together (`analyse_topic` once per video, `compose_topic_scenes` for all scenes) and is
called from `make_video` for ANIMATION. The layers of a scene are built when the real audio duration is known,
so the sync uses real durations. The report gets a `visual_engine` block (domain, concepts, objects and sync log
per scene, quality checks).

Domains: sleep, economy, nature, space, weather, tech, generic. 28 objects. A topic with no known word falls back
to the generic kit (never guesses). No AI model is used: the same input gives the same frames, nothing to misspell.

## Computational Thinking mapping (for the report)

* **Decomposition**: topic -> concepts -> objects -> motion -> timing -> checks (five independent modules).
* **Pattern recognition**: concept -> object is a fixed mapping; the same few motions recur (walk, grow, orbit,
  circulate, step, rise, fall, pulse) so one builder per object serves every topic.
* **Abstraction**: the engine sees only the `TopicProfile` and the scene's words, never raw user text; the sprite
  is separate from its keyframe tracks.
* **Algorithm design**: selection (mention order, in-domain first, filler from the pool, no repeats), word timing,
  checks with thresholds.

## Alternatives considered

| Question | Options | Chosen / why |
|---|---|---|
| Find concepts | LLM tagger / embeddings / lexicon | Lexicon: deterministic, testable, free, works offline; cost: misses words not listed (measured below) |
| Draw objects | image model / stock assets / code-drawn sprites | Code-drawn: no provider, no cost, consistent style, reproducible; cost: simple look |
| Motion | image-to-video (CLIP) / cut-out keyframes | Keyframes (option L2): cheap and stable; CLIP has no provider here |
| Timing words | TTS timestamps (H2) / proportional (H1) | H1 per word until a provider returns timestamps |
| Avoid repeats | random choice / history window | History window (last 2 scenes): deterministic |

## Iteration record (benchmark: 9 topics x 6 scenes, EN + VI)

`python -m evaluation.visual_engine_benchmark`, CSV in `outputs/visual_engine_benchmark.csv`.

| Version | Change | domain acc | gold hit | repeat rate | distinct | cross-topic overlap | empty | sync gap |
|---|---|---|---|---|---|---|---|---|
| base | generic stick figure + 6 props | n/a | n/a | 80 % | 33 % | 1.00 | 0/54 | n/a |
| v0 | topic -> domain kit, objects from the pool | 100 % | 70 % | 4 % | 72 % | 0.12 | 0/54 | 0.00 |
| v1 | objects from the words the narration mentions | 100 % | 100 % | 2 % | 83 % | 0.11 | 0/54 | 0.40 s |
| v2 | no repeated object set in the last 2 scenes | 100 % | 100 % | 0 % | 87 % | 0.11 | 0/54 | 0.40 s |
| v3 | `RELAX_REPEAT`: differ from the last scene when no fresh object exists | 100 % | 100 % | 0 % | 87 % | 0.11 | 0/54 | 0.40 s |

Problems found by running it and how they were fixed (each has a test):
1. Folded Vietnamese keywords matched English words ("trả" -> "tra" hit "travel"): folded text now needs whole-word matches for diacritic keywords.
2. (by design, tested) "mưa" (rain) vs "mua" (buy) differ only by diacritics: matching keeps diacritics whenever the text has any.
3. "sinh **học**" (biology) triggered the book object: keyword narrowed to "học sinh", "học tập".
4. "the moon **rises**" added a chart to a sleep scene: in-domain concepts win when a scene has at least two.
5. A sentence with no known word ("packets", "routers") scored a gold miss: words added to the lexicon.
6. An object mentioned at the end of a scene appeared 0.72 s late (cap at 85 %): cap raised to 92 %.
7. The quality check on subtitles exposed a bug of the OLD subtitle splitter: long sentences lost the connector ("so"), so
   subtitles lacked a spoken word. `cue_texts` now falls back to an even word split (regression test added).
8. Scenes with a lone wide object (planets) were identical two scenes apart: a companion object is added.

## Data caveats (read first)

* Topics, sentences and **gold labels were written by the AI assistant and not reviewed by the team**; the gold
  was written knowing the lexicon, so "gold hit 100 %" is optimistic. Use the table as a regression and iteration
  record, not as quality on real videos. Add real scripts from the team to `evaluation/visual_cases.py`.
* `base` has no topic, so domain accuracy and gold hit are "n/a", not 0. Its repeat rate counts (prop, pose) pairs.
* v3 does not change the numbers on this data (v2 already reached 0 % repeats); `test_relax_repeat_...` builds the
  case where it matters.
* Thresholds are assumptions: object coverage >= 0.4 % of the picture, distinct pictures >= 60 %, sync gap <= 0.5 s,
  cue length 0.5-8 s, audible audio above -50 dB. ms/scene is on the machine that ran the benchmark.
* Word timing is proportional (H1), not measured on TTS audio; with a real TTS compare against H2 timestamps.
* The audio check is skipped (with a note) for the silent engine; speech was not tested here with a real voice.

## Limits and next steps

* INFOGRAPHIC is unchanged (its text and layouts already come from the claims); topic palettes/icons could reuse `kits.py`.
* HYBRID is still not built by `make_video`.
* Only the words listed in `topic.py` are recognised (EN, VI). Extend `CONCEPTS` or add an object in `objects.py` +
  `OBJECTS`, a pool entry in `kits.POOLS`, and a test (`test_every_object_...` runs automatically).
* Objects are simple flat shapes; animals have one species look (elephant variant by keyword).
