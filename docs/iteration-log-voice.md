# Iteration log – Voice Segmenter (report 4(f), 5.7, 5.9.6; criterion S19)

Reproduce: `python -m evaluation.voice_benchmark` (default `--n 300 --seed 11`, CSV in
`outputs/voice_benchmark.csv`); tests: `python -m pytest -q`.

> **Important – these numbers come from a SIMULATED TTS** (`modules/providers/mock_tts.py`):
> true speaking rate is drawn from 145–185 wpm per script, ±6% noise per sentence and a 0.3 s
> pause after each sentence. Scripts are random (sentence length ~ N(19, 7) words, clipped to
> 5–40). Planning wpm = 165 is an assumption. Nothing here is a measurement of a real voice:
> repeat the benchmark with FFprobe durations of real audio (to-do items 12 and 14) before
> quoting S19 in the report. Vietnamese is not tested (words = syllables; wpm must be measured).

## Versions

| Version | Idea |
|---|---|
| F1 greedy | Sequential greedy (report 5.7 pseudocode; tail merge fixed, see finding 1) |
| F2 DP deviation | DP minimising sum of \|duration − 11 s\| (the report's F2) |
| F3 DP band | DP minimising the number of voices outside [10, 12] s, then deviation |
| F4 DP share | Like F3, ties broken towards MORE in-band voices (fix of finding 3) |

## Results, seed 11, 300 scripts, no post-TTS repair

"Actual in-band" = share of voices whose (simulated) real duration is in 10–12 s (the last voice
may be shorter) = the S19 metric. Calibration: none = 165 wpm and no pause term (report formula);
wpm = true wpm known; wpm+pause = true wpm and pause known.

| Algorithm | Calibration | Actual in-band (S19) | Within ±1 s | Voice count in 4(f) range | Voices < 5 s / script | TTS calls / script |
|---|---|---|---|---|---|---|
| F1 | none | 25.3% | 45.9% | 16.0% | 0.34 | 10.2 |
| F2 | none | 30.6% | 53.7% | 92.3% | 0.00 | 8.2 |
| F3 | none | 32.7% | 52.6% | 82.0% | 0.04 | 7.9 |
| F4 | none | 35.0% | 54.7% | 76.0% | 0.17 | 8.3 |
| F1 | wpm+pause | 24.6% | 42.9% | 11.0% | 0.45 | 10.6 |
| F2 | wpm+pause | 32.6% | 56.9% | 77.3% | 0.01 | 8.6 |
| F3 | wpm+pause | 35.9% | 54.8% | 81.3% | 0.04 | 8.0 |
| F4 | wpm+pause | 37.7% | 56.0% | 75.0% | 0.17 | 8.4 |

Noise check (5 seeds × 300 scripts, actual in-band, mean [min–max]): F1 25.7 [25.0–26.2],
F2 30.8 [29.6–31.6], F3 32.6 [31.8–33.5], F4 34.8 [34.1–35.7] (calibration none). Differences
between versions are larger than the seed-to-seed spread (about ±1 point); a 1-point gap would not be.

## Findings (CT process)

1. **The report's F1 pseudocode breaks its own rule.** Its "merge a short tail" step appends the
   remaining 1–2 sentences to the previous voice if that voice has fewer than 2 sentences, so
   sentences [10 s, 3 s, 3 s] become one 3-sentence voice. Found by the invariant test
   (`test_partition_order_and_max_two_sentences`); reproduced with `faithful=True`
   (`test_report_pseudocode_of_f1_can_emit_a_three_sentence_voice`). F1 now merges only if the
   result keeps ≤ 2 sentences.
2. **F1 → F2 (algorithm choice):** greedy cuts leave many leftover voices (10.2 voices/script,
   0.34 voices shorter than 5 s). DP over cut points is optimal for its objective (checked against
   brute force) and raises S19 from 25.3% to 30.6%.
3. **F2 → F3 → F4 (the objective was wrong):** minimising Σ|d − 11| is not the S19 metric. Counter-
   example [3 s, 11 s, 3 s, 11 s]: greedy has 2 of 4 voices in band, F2 chooses two 14 s voices
   (0 in band). F3 (count voices outside the band) still ties on this input; F4 breaks the tie
   towards more in-band voices (`test_f2_and_f3_lose_to_greedy_on_3_11_3_11_and_f4_fixes_it`).
   Trade-off: F4 gains ≈ 2 points over F3 but produces 4× more voices shorter than 5 s
   (0.17 vs 0.04 per script; in report example B it created a 1.5 s clip) and a slightly lower
   share of scripts whose voice count falls in the 4(f) range (76% vs 82%). A minimum-length floor
   would be the next step.
4. **S19 is capped by the script, not by the algorithm.** Even F4 reaches only ≈ 43% *planned*
   in-band (37.7% actual) with free sentence lengths, ≤ 2 sentences and a 2 s band; DP is optimal
   here, so the ceiling is structural. Allowing 3 sentences gives 43.0% actual but only 49% of
   scripts in the 4(f) count range; 1 sentence per voice gives 16.0%. To set the S19 threshold
   (`[TODO]%` in the report) the team must either widen the band, relax the rule, or make the
   script generator control sentence length (the real lever).
5. **Estimation error matters, mostly the pause.** Calibrating wpm alone helps ≈ 1–2 points; adding
   the per-sentence pause helps ≈ 3–4 (F3: 32.7 → 33.7 → 35.9; 5-seed means 32.6 → 34.6 → 36.4).
   The size of the pause effect depends on the simulator's 0.3 s; the mechanism (1–2 sentence
   voices accumulate a pause per sentence) should hold for real TTS, but the value must be measured.
6. **The post-TTS repair of report 5.7 hurts (negative result).** Splitting voices that are too
   long and merging ones that are too short lowered actual in-band from 37.7% to 32.1% (5-seed
   means 38.7 → 32.8), pushed the share of scripts in the 4(f) count range from 75% to 8.7% and
   raised TTS calls per script from 8.4 to 13.1 (+56%). Splitting a long 2-sentence voice makes two
   short voices (voices < 5 s: 0.17 → 0.37 per script). Not fixed yet; idea: accept a repair only
   if it reduces the number of out-of-band voices, or re-plan locally with measured per-sentence
   durations.
7. **The worked examples of report 5.8 do not follow the rule either.** Three of the 18 example
   voices have 3 sentences (A–V1, B–V4, B–V6; `test_report_examples_contain_voices_with_three_sentences`),
   they last 7.6–11.6 s at 165 wpm (not "10 s each"), and F1–F3 cut the same scripts into 10 voices
   (F4: 10–11) while 4(f) expects 8–9 for 90 s. Regenerate the examples from the Segmenter's output.

## Limits and next steps
- Replace `MockTTS` with real durations; re-run and update every table above.
- Measure wpm and pause per language (Vietnamese counts syllables), then fix the S19 threshold.
- Add a minimum voice length to F4, and a better repair rule (finding 6).
- One simulator, one sentence-length distribution, no confidence intervals beyond the 5-seed check.
