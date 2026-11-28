# Iteration log: ANIMATION format (Thành Nam)

Run: `python -m evaluation.animation_benchmark` (offline, about 45 s; writes `outputs/animation_motion.csv` and
`outputs/animation_loop.csv`). The voice in part B is simulated (SilentEngine); no MP4 is written.

## A. Motion quality on real frames (packs sleep and inflation, 24 scenes per variant)

| Variant | S11 scenes that move | Subtitle band untouched | Motion, all scenes | Motion, key scenes | Motion, other scenes |
|---|---|---|---|---|---|
| v0 still (character never moves) | 0/24 | 24/24 | 0.000 | 0.000 | 0.000 |
| v1 keyframes, uniform energy | 24/24 | 24/24 | 2.671 | 2.618 | 2.716 |
| v2 keyframes + Motion Planner energy (shipped) | 24/24 | 24/24 | 2.753 | 2.796 | 2.716 |

Motion = mean absolute pixel change between frames 1/8 of a scene apart (0-255, area above the subtitle band).
Key scenes = hook, summary and importance >= 0.75.

- v0 -> v1 is the real gain: S11 goes from 0/24 to 24/24.
- v1 -> v2 is small: key scenes move about 7 % more (2.618 -> 2.796) and the other scenes are unchanged,
  as intended. Energy only scales the size of the movements, so the effect is modest. We keep it because it is cheap and
  follows report 5.3 (important scenes get more motion), but it should not be presented as a large improvement.
- Cost: about 8 ms per frame. v0 is the same picture drawn once, so its time is not a fair comparison.

## B. Duration loop on the animation format (2 packs x 3 targets x 7 voice speeds = 42 runs)

| | passes S12 and S13 |
|---|---|
| before (no adjustment loop) | 3/42 |
| after (N0-N4 loop) | 35/42 |

The 7 runs that still fail are all at a true speed of 120 wpm (6 runs) or inflation, 120 s, 135 wpm (1 run):
the voice is 18-27 % slower than the planned 165 wpm and the video stays too short even after dropping claims
and pushing pauses and speed to their limits. The same 7 runs fail for the infographic format, so this is a limit of
the loop (and of the size of the demo claim packs), not of the animation.

## Limits to state in the report
- Animation is LAYERED cut-out drawn by code (report 5.9.10, option L2). CLIP (AI image-to-video) and HYBRID are not built.
- The motion score measures pixel change, not whether the movement looks good. Quality was judged by watching the video.
- Voice speeds in part B are simulated; with a real voice only the measured rate matters.

## C. ANIMATION from AI pictures (design note, NOT yet measured)
Code: `modules/video/ai_animation.py`, tests: `tests/test_ai_animation.py` (fake provider, no network).
Each scene = one AI picture (same style prompt as the INFOGRAPHIC pictures) cut out of its plain white background
and animated by the existing Layer/Track parts: slide-in from alternating sides, pop, float, slow zoom; the Motion
Planner's energy scales the movement. Backdrop colour comes from the picture's dominant colour.

Fallback policy A (decision of the team): scenes without a picture are retried (2 rounds, circuit breaker re-opened,
another seed); if any scene still has none, the WHOLE video is drawn by the code-drawn animation and the report says why.
Reason: one video must never mix AI pictures with stick figures.

Not measured yet (fill in after running on a real provider; do not quote numbers before): share of pictures whose
background was removed cleanly, share of videos that fall back, render time per video.
Known limits: the cut-out assumes a plain background (the style prompt asks for it; FLUX schnell does not always obey);
FLUX schnell takes no seed, so consistency between scenes comes from the shared prompt only; the subject itself does not
move (the whole picture slides, floats and zooms), which is a limit of one still image per scene.

## D. Jointed stick figure (design note, NOT yet measured on viewers)
Code: `modules/video/stickman.py`, tests: `tests/test_stickman.py` (offline, no AI, no network).
The cut-out figure of part A was four rigid sprites: the legs never moved and each arm was one stiff piece.
The default figure (`animation.RIG = "jointed"`) is now a 2D skeleton drawn every frame:

- joints: shoulder-elbow-hand, hip-knee-foot, torso lean, head tilt; the lowest foot always stands on the ground,
  so bending the knees really crouches and `dy` really jumps;
- 13 actions: idle, talk, walk, run, wave, point, think, idea, shrug, cheer, jump, surprised, nod;
- choreography from the Motion Planner pose and role: walk in (constant speed) -> main pose -> explaining gestures;
  think scenes end with an "idea", the summary scene ends with a cheer (lively) or a nod. Poses are blended for
  0.28 s between beats. `script=[Beat(...)]` lets a caller give the beats directly (planned: AI director, step b);
- lip-sync: one mouth open-close per syllable while a word is spoken (same word timing as the objects, `sync.py`),
  closed in the pauses; blinking every 2.6-4.4 s (deterministic);
- cost: about 2 ms per frame for the figure (measured on the dev container, not on the team's laptops).

The figure is timed in SECONDS (walking speed, mouth, blinks), the props still in fractions u of the scene.
The old figure is kept: `character_layers(..., rig="cutout")` or `RIG = "cutout"`.
Not measured yet: whether viewers find it more lively than the cut-out figure (watch test planned).
Known limits: word times are estimated from the text (H1), so the mouth follows the estimate, not the real audio;
one figure per scene; legs swing in the picture plane (profile walk) while the face looks at the viewer.

## E. AI director for the jointed figure (design note, NOT yet measured on viewers)
Code: `modules/ai/director.py` + `stickman.beats_from_directions`, tests: `tests/test_director.py` (fake LLM, no network).
One LLM call per video: the narration of every scene with numbered words goes in; per scene a short list of
`{"from_word", "action"}` comes out, and the figure starts that gesture when the narrator says that word (same word times
as the lip-sync). The model only picks from a fixed menu (no walk/run); invalid actions, out-of-range words and beats closer
than 0.7 s are dropped; a scene without a valid answer keeps the default choreography; a provider error changes nothing and
the report (`report["director"]`) says so. The figure still walks in first. Online: needs the user's consent (`--allow-online`,
UI checkbox). Domains without a presenter figure (nature, space, tech) ignore the directions.

Not measured yet (do not quote numbers before): share of scenes with a valid answer on a real provider, whether viewers find
the directed gestures better than the Motion Planner's fixed ones, call time. Known limits: word times are estimated (H1),
so a gesture can start a little early or late against the real voice; the prompt and MAX_BEATS = 5 are our own choice.
