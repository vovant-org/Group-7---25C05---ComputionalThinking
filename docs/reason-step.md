# REASON step (v1): research a question that has no material

**Where:** `modules/reason/research.py`, called from New Project → step 1 ("Research this topic with AI").

## Why
Every later module (claims → Scene Segmenter → Budget → Voice → Timeline) is built on *reference text*: full
sentences of 8–24 words. Before this step a user with only a question ("Vì sao thiên tài luôn khác biệt?") was
blocked with "Add reference material" and had to paste text or use a demo pack.

## How it works
1. The user types a question and ticks "I understand my question is sent to an online AI service".
2. `research_topic(question, llm, language=…, t_target_s=…)` asks a free LLM (the providers of `modules/ai/llm.py`:
   **auto** = Gemini with `GEMINI_API_KEY`, then Pollinations without a key) for JSON:
   `{"title", "sentences":[{"text","role":"hook|explain|example|summary"}]}`.
   * language = the language of the question (`detect_language`), so a Vietnamese question gives Vietnamese material
     and step 3 then offers Vietnamese voices;
   * number of sentences from the duration (`sentence_count`: 90 s → 15, ~16 words each).
3. Checks on every sentence (project rule "no invented facts"):

| check | dropped when |
|---|---|
| length | fewer than 8 or more than 24 words (one scene ≤ 10 s) |
| numbers | it contains a digit (no invented statistics, years, %) |
| language | `detect_language(sentence)` differs from the question's language |
| duplicate | same sentence twice |

   Fewer than 8 sentences left → one retry with a larger request → else an error message (nothing is filled in).
4. The text fills the material box, one paragraph per role. A warning says **"Material written by AI, not verified"**;
   the user edits it like their own text. Nothing is built until they press Continue.
5. The project record gets `"content_origin": "ai"` so the Studio/Projects data shows where the content came from.

Safety rails in the UI: the button is disabled without a question, without consent, or when the box holds the
user's own text (AI research never overwrites it). Only the question and the optional extra instructions are sent.

## Limits / ASSUMPTIONS
* The checks catch format problems, not wrong facts. The prompt asks for well-established knowledge, no names, no
  studies, and to correct exaggerated premises ("always", "everyone"); the user's review is the real check.
* No web search or citations yet: a *verified* REASON (claims linked to sources) is still TODO.
* Free tiers are rate limited; Pollinations can take up to a minute. Offline the step is unavailable (clear message).

## Tests
`tests/test_reason.py` uses a fake LLM (no network): language, length, digit and duplicate filters, the retry, bad
JSON, provider errors, paragraphs by role, and that the produced text becomes claims with `claims_from_text`.
