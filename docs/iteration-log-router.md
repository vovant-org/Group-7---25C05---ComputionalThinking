# Iteration log – Router (report 5.1 / 5.9.1, criteria S12, S14, R5, R7)

Reproduce: `python -m evaluation.router_benchmark` (CSV in `outputs/router_benchmark.csv`).
Test set: `evaluation/router_cases.py` – 51 cases (S14 word boundaries 1499/1500/1501,
S12 duration boundaries 59/60/120/121, budget and cost rules, use cases U11–U16, Vietnamese
requests, ambiguous format, prompt-injection and parser-trap cases, 5 adversarial cases (tag "adversarial")).
**Labels were written by hand from the report; the team must review and extend them.**
"Exact match" = status + reason codes + resolved format + duration + intent all correct.

| Version | Idea | Status accuracy | Exact match | Limit cases (S12/S14) | Injection | Free-text exact |
|---|---|---|---|---|---|---|
| v0 | A1 policy table, structured fields only | 43/51 | 27/51 | 9/15 | 1/2 | 1/25 |
| v1 | A4: + intent parser (naive duration regex) | 46/51 | 44/51 | 14/15 | 2/2 | 18/25 |
| v2 | A4: duration counts only near a video word | 46/51 | 45/51 | 14/15 | 2/2 | 19/25 |

Before the 5 adversarial cases were added (46 cases): v2 was 45/46 status and 45/46 exact.

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
5. **Adversarial cases (5 added):** all five break v2. They show five different failure
   modes of the regex parser: (a) unit not recognized (`150s`) so an over-limit request is
   silently ACCEPTed with the default 90 s, which violates S12 ("100%"); (b) a thousands
   separator (`1,000 credits`) is read as budget 0; (c) two durations in one phrase
   (`1 minute 30 seconds`) pick the wrong one; (d) negation (`not animation`) is read as
   "both formats mentioned"; (e) words inside the topic (`convert to animation`) are read as
   a switch-format command.
6. **Status accuracy hides errors:** `adv_topic_says_convert` gets the right status (ACCEPT)
   but the wrong intent and format, so only Exact match catches it. The most serious case is
   `adv_150s_abbrev`: the parser fails open, i.e. when it cannot read the duration it falls
   back to the default instead of warning. Hard limits should not depend on the parser.

## Next step
Add the LLM classifier behind `parse_intent`, re-run this benchmark, and extend the cases
Team members should each add ≥ 5 cases they believe will break the router.
Done so far: 5 cases by Vũ Thành Nam (tag `adversarial`). Planned fixes for v3, by priority:
(1) recognise `s`, `hour` and use a fail-closed rule when a number sits next to a video word
but the unit is unknown; (2) parse `1,000`; (3) restrict the intent parser to the request
verb part, not the topic; (4) negation handling or an LLM behind `parse_intent`.

## Label notes (review of hand-written labels against the report)
Reviewed all 46 labels against the report (S12, S14, 1.5 Use Cases, 5.1, 5.9.1). Most
labels follow the report directly. Three points are design decisions, not report rules:

1. **Structured field vs. free text** (`structured_beats_text`, `inject_structured`): the
   report does not say what to do when the form field and the request text disagree. The
   team chose "the structured field wins, silently". A possible improvement is a warning
   code such as FORMAT_CONFLICT.
2. **Missing output_format**: the report allows two behaviours ("ask one question" or
   "default to INFOGRAPHIC and say so"). The labels follow the second one
   (FORMAT_DEFAULTED + ACCEPT).
3. **Prompt injection (R7)**: section 5.1 does not mention it. The labels rely on the
   principle in 5.9.1 that hard limits must be deterministic.

Known dependency: the `budget_*` boundary labels (14 / 36 / 18) depend on `MODE_COST` in
`core/config.py`, which is an unmeasured assumption. They must be recomputed after the
provider cost measurement.
