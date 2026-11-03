# Iteration log – Scene Segmenter / claim selection (report 5.2, 5.9.4; criteria S13, S16)

Reproduce: `python -m evaluation.scene_benchmark` (default `--n 300 --seed 21`, CSV in
`outputs/scene_benchmark.csv`); tests: `python -m pytest -q`.

> **Data caveats (read first).**
> * Hand-written cases (`evaluation/scene_cases.py`): two cases built from the report's examples
>   (sleep, inflation). Importance scores, paraphrases, distractors and gold flags were written by
>   the AI assistant, **not yet reviewed by the team**. They compress the input only 2.2–2.5×
>   (the real task is 4–10×), so selection pressure is weaker than in the real pipeline.
> * Synthetic documents (`evaluation/scene_benchmark.py`): ideas with paraphrased claims that
>   share concept words, partly shared topic words and a skew that lowers the importance of every
>   facet but one. This is an **assumption** about claim data, not real REASON output. Because
>   paraphrases share vocabulary, lexical similarity detects them easily here: treat the MMR gain
>   as an upper bound.
> * Ideas/gold labels are used only for scoring; the algorithms never see them.

## Versions

| Version | Idea |
|---|---|
| D1 greedy | Highest importance first until W_target = wpm·T/60 is reached (never above +10%) |
| D2 MMR | λ·importance − (1−λ)·max similarity to already chosen claims (TF-IDF cosine), λ = 0.7 |
| D2f MMR + facet | One claim per facet first (budget permitting), then MMR |

Metrics: gold coverage, redundancy (share of selected claims repeating a selected idea), facet
coverage (facets holding a gold idea that appear in the selection), words within ±10% of W_target.

## Results

**A. Hand-written cases (T = 60 s, W_target = 165 words)**

| Case / algorithm | Gold coverage | Redundancy | Facet coverage |
|---|---|---|---|
| sleep / D1 | 85.7% | 33.3% | 66.7% |
| sleep / D2 | 85.7% | 25.0% | 66.7% |
| sleep / D2f | 100% | 16.7% | 100% |
| inflation / D1 | 100% | 23.1% | 100% |
| inflation / D2 | 87.5% | 16.7% | 100% |
| inflation / D2f | 100% | 16.7% | 100% |

**B. Synthetic, 300 documents, seed 21** (5-seed means in brackets; spread ≈ ±1 point)

| Skew | Algorithm | Gold coverage | Redundancy | Facet coverage |
|---|---|---|---|---|
| 0.0 | D1 | 65.4% (64.6) | 35.9% | 92.8% (93.3) |
| 0.0 | D2 | 87.8% (87.0) | 2.2% | 98.7% (98.5) |
| 0.0 | D2f | 88.0% (87.3) | 2.2% | 100% (100) |
| 0.3 | D1 | 63.0% (62.2) | 36.1% | 67.3% (66.2) |
| 0.3 | D2 | 82.7% (82.0) | 7.9% | 89.0% (88.7) |
| 0.3 | D2f | 83.4% (82.7) | 6.8% | 100% (100) |

**C. MMR weight λ (synthetic, skew 0.3):** D2f coverage 85.3% (λ=0.5), 83.4% (0.7), 73.6% (0.9);
redundancy 0.1%, 6.8%, 22.6%.

In-budget (±10%) is 100% everywhere: it holds by construction of the selection loop as long as
enough claims exist, so it is not evidence of quality.

## Findings (CT process)
1. **D1 → D2 (the problem is redundancy, not importance).** Highest-importance-first selects
   paraphrases of the same top idea: 36% of selected claims repeat an idea, gold coverage 65%.
   MMR removes the repeats (2–8%) and raises coverage to 83–88%. Counter-example in
   `test_greedy_picks_paraphrases_while_mmr_picks_a_new_idea`. Upper bound, see caveats.
2. **D2 → D2f (perspectives, not coverage).** The facet constraint does not change gold coverage
   beyond the noise (+0.3 to +0.7 points) but guarantees every perspective appears: facet coverage
   88.7% → 100% when one facet is over-rated (skew 0.3). That is what the report asks for (same
   question seen from science, economics, society...), so this is a requirement-driven choice.
3. **Plain MMR is not always better than greedy.** On the inflation example it dropped the gold
   idea "savers" while greedy kept it (87.5% vs 100%), because novelty pushed out a lower-importance
   but required claim. Two cases are anecdotal, but D2f (100% on both) is the only version without
   a failure. Documented in `test_documented_limitation_plain_mmr_loses_a_gold_idea...`.
4. **Lexical similarity is the weak spot.** On the hand-written paraphrases (e.g. "need about 7 to
   9 hours" vs "require seven to nine hours") TF-IDF cosine is ≈ 0.46, so D2f still keeps 17% repeated
   ideas. Fix candidates: embeddings, an NLI check between claims, or LLM de-duplication in REASON.
5. **Do not tune λ on the synthetic data.** It favours λ = 0.5 because paraphrases are easy to
   detect there; real claims will not be. Keep 0.7 until λ is measured on real REASON output.
6. **Scenes.** One scene per selected claim: 12 scenes in both hand-written cases (inside the
   6-30 range), average 4.6 s, none above t_max = 10 s, **but 3 of the 12 scenes in each case are
   shorter than t_min = 4 s** (they need merging or a longer claim) and the total narration is
   about 55 s, below the 60 s minimum, because the selection may stop at -10% of W_target. The
   Timeline Assembler and pauses must handle both (S12). Layouts come from the deterministic lookup
   of report 5.2 (analogy -> big_number if the claim has a figure, else loop) and are unit-tested.

## Limits and next steps
- Add scene merging for scenes shorter than t_min, and decide how to reach 60 s when the selection stops early.
- Gap: there is still no narration-script generator (claims → sentences → voice units), so the
  Voice Segmenter and Scene Segmenter are not connected; the report says 1 voice ↔ 1–3 scenes.
- The team must add its own hard cases (3 each) with real claim lists, ideally from real documents,
  and more compression (4–10×), then re-run and update every table.
- Try a semantic similarity (embeddings/NLI) behind `similarity_matrix`, and re-evaluate λ.
- The narration order is the source order; the report's problem → mechanism → conclusion order
  needs the script generator (E2).
