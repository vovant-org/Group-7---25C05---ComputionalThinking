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
