import random

import pytest

from core.models import OutputFormat
from evaluation.scene_benchmark import make_doc, score
from evaluation.scene_cases import CASES
from modules.scene_segmenter.segmenter import (
    ALGORITHMS, Claim, SegParams, build_scenes, layout_for, select_claims, similarity_matrix, target_words,
)

ALGOS = list(ALGORITHMS)


def claim(cid, text, facet="science", imp=0.5, order=0, pattern="cause_effect", fig=False):
    return Claim(cid, text, facet, imp, pattern, fig, order)


# ----------------------------------------------------------------- similarity
def test_similarity_basics():
    cl = [claim("a", "Most adults need seven hours of sleep nightly"),
          claim("b", "Most adults need seven hours of sleep nightly"),
          claim("c", "Central banks raise interest rates")]
    sim = similarity_matrix(cl)
    assert sim[0][1] == pytest.approx(1.0) and sim[0][2] == pytest.approx(0.0)
    assert sim[1][0] == sim[0][1]


# ----------------------------------------------------------------- invariants
@pytest.mark.parametrize("algo", ALGOS)
def test_selection_invariants_on_random_documents(algo):
    rng = random.Random(4)
    for idx in range(40):
        case = make_doc(rng, idx, rng.choice([0.0, 0.3]))
        sel = select_claims(case.claims, case.t_target, algo)
        ids = [c.claim_id for c in sel.claims]
        assert len(ids) == len(set(ids)) and set(ids) <= {c.claim_id for c in case.claims}
        assert sel.words == sum(c.words for c in sel.claims) <= 1.1 * sel.w_target + 1e-9
        assert [c.order for c in sel.claims] == sorted(c.order for c in sel.claims)   # narration order
        assert sel.words >= 0.9 * sel.w_target                                         # enough claims exist
        assert select_claims(case.claims, case.t_target, algo).claims == sel.claims    # deterministic


@pytest.mark.parametrize("algo", ALGOS)
def test_selects_everything_when_input_is_smaller_than_budget(algo):
    cl = [claim(f"c{i}", f"short claim number {i} here", order=i) for i in range(5)]
    assert len(select_claims(cl, 60, algo).claims) == 5


def test_target_words_follows_report_formula():
    assert target_words(90, 165) == pytest.approx(247.5)


# ------------------------------------------------- counter-examples (Before/After)
def _budget_for_two(claims):
    """T such that W_target is about the length of two claims."""
    return 2 * claims[0].words * 60 / 165


def test_greedy_picks_paraphrases_while_mmr_picks_a_new_idea():
    a1 = claim("a1", "alpha beta gamma delta epsilon zeta eta theta", imp=0.90, order=0)
    a2 = claim("a2", "alpha beta gamma delta epsilon zeta eta iota", imp=0.89, order=1)
    b = claim("b", "kappa lambda mu nu xi omicron pi rho", imp=0.60, order=2)
    t = _budget_for_two([a1, a2, b])
    p = SegParams(tol=0.0)
    ids = lambda algo: {c.claim_id for c in select_claims([a1, a2, b], t, algo, p).claims}
    assert ids("D1_greedy") == {"a1", "a2"}                 # duplicates, new idea lost
    assert ids("D2_mmr") == {"a1", "b"}                     # novelty wins


def test_facet_constraint_forces_a_missing_perspective():
    sci = [claim(f"s{i}", f"science fact {i} about cells and atoms", facet="science", imp=0.9 - 0.01 * i, order=i)
           for i in range(6)]
    soc = claim("soc", "society reaction to the new rule", facet="society", imp=0.30, order=6)
    t = 4 * sci[0].words * 60 / 165
    p = SegParams(tol=0.0)
    assert "soc" not in {c.claim_id for c in select_claims(sci + [soc], t, "D1_greedy", p).claims}
    assert "soc" in {c.claim_id for c in select_claims(sci + [soc], t, "D2f_mmr_facet", p).claims}


def test_facet_constraint_never_breaks_the_budget():
    rng = random.Random(8)
    for idx in range(30):
        case = make_doc(rng, idx, 0.3)
        sel = select_claims(case.claims, case.t_target, "D2f_mmr_facet")
        assert sel.words <= 1.1 * sel.w_target + 1e-9


# ----------------------------------------------- hand-written cases (regressions)
def test_mmr_with_facets_covers_all_gold_ideas_on_the_report_examples():
    for case in CASES:
        assert score(case, select_claims(case.claims, case.t_target, "D2f_mmr_facet"))["coverage"] == 1.0


def test_documented_limitation_plain_mmr_loses_a_gold_idea_on_the_inflation_case():
    case = next(c for c in CASES if c.id == "infl")
    greedy = score(case, select_claims(case.claims, case.t_target, "D1_greedy"))["coverage"]
    mmr = score(case, select_claims(case.claims, case.t_target, "D2_mmr"))["coverage"]
    assert mmr < greedy == 1.0


def test_documented_limitation_lexical_similarity_misses_some_paraphrases():
    """Redundancy stays > 0 on the report examples even with MMR (needs semantic similarity)."""
    for case in CASES:
        assert score(case, select_claims(case.claims, case.t_target, "D2f_mmr_facet"))["redundancy"] > 0


# ------------------------------------------------------------------- scenes
@pytest.mark.parametrize("pattern,fig,expected", [
    ("cause_effect", False, "cause_chain"), ("comparison", False, "compare_2col"),
    ("step_by_step", False, "steps"), ("trend", False, "trend_chart"),
    ("analogy", True, "big_number"), ("analogy", False, "loop"), ("unknown", False, None)])
def test_layout_lookup_table(pattern, fig, expected):
    assert layout_for(claim("x", "t", pattern=pattern, fig=fig)) == expected


def test_scenes_for_infographic_and_animation():
    case = CASES[0]
    sel = select_claims(case.claims, case.t_target, "D2f_mmr_facet")
    scenes, rep = build_scenes(sel, OutputFormat.INFOGRAPHIC)
    assert len(scenes) == len(sel.claims) == rep["n_scenes"] and rep["scene_count_ok"]
    assert all(s.layout is not None for s in scenes if s.explain_pattern != "unknown")
    assert scenes[0].start_s == 0 and scenes[1].start_s == pytest.approx(scenes[0].duration_s)
    anim, _ = build_scenes(sel, OutputFormat.ANIMATION)
    assert all(s.layout is None for s in anim)


def test_scene_report_flags_too_long_and_too_short_scenes():
    long_c = claim("l", " ".join(["w"] * 40), order=0)          # 40 words at 165 wpm = 14.5 s
    short_c = claim("s", "three short words", order=1)           # ~1.1 s
    sel = select_claims([long_c, short_c], 60, "D1_greedy")
    _, rep = build_scenes(sel)
    assert rep["too_long"] == [0] and rep["too_short"] == [1] and not rep["scene_count_ok"]
