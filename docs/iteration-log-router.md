# Iteration log – Router (report 5.1 / 5.9.1, criteria S12, S14, R5, R7)

Reproduce: `python -m evaluation.router_benchmark` (CSV in `outputs/router_benchmark.csv`).
Test set: `evaluation/router_cases.py` – 46 cases (S14 word boundaries 1499/1500/1501,
S12 duration boundaries 59/60/120/121, budget and cost rules, use cases U11–U16, Vietnamese
requests, ambiguous format, prompt-injection and parser-trap cases).
**Labels were written by hand from the report; the team must review and extend them.**
"Exact match" = status + reason codes + resolved format + duration + intent all correct.

| Version | Idea | Status accuracy | Exact match | Limit cases (S12/S14) | Injection | Free-text exact |
|---|---|---|---|---|---|---|
| v0 | A1 policy table, structured fields only | 39/46 | 27/46 | 9/14 | 1/2 | 1/20 |
| v1 | A4: + intent parser (naive duration regex) | 44/46 | 44/46 | 14/14 | 2/2 | 18/20 |
| v2 | A4: duration counts only near a video word | 45/46 | 45/46 | 14/14 | 2/2 | 19/20 |

## Findings (CT process)
1. **v0 → v1 (pattern recognition):** users write requests as free text ("a 5-minute video"),
   so a table that reads only structured fields silently ACCEPTs over-limit videos (U15) and
   lets an injected "ignore all limits ... 10-minute" through. The parser only *fills missing
   fields*; the hard limits are still checked by deterministic rules (structured input wins
   over text, see `structured_beats_text`, `inject_structured`).
2. **v1 → v2 (error analysis):** v1 read "why 5 minutes of daily exercise helps" as a 300 s
   video and rejected a valid request. Fix: accept number+unit as the video length only if a
   video word is within 2 words (window = 2).
3. **Remaining error (honest limitation):** "a video about 5 minutes of yoga" still fails.
   Regex cannot tell the topic from the length; this motivates plugging a real LLM into
   `parse_intent` (only for missing information) and measuring it on the same cases.
4. **Trade-off:** the LLM option (A3) was not chosen as the primary path because limits must be
   deterministic (S14) and repeatable; the hybrid keeps rules for hard limits.

## Next step
Add the LLM classifier behind `parse_intent`, re-run this benchmark, and extend the cases
(team members should each add ≥ 5 cases they believe will break the router).
