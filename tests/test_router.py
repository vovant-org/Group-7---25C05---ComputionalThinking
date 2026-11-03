import pytest

from evaluation.router_benchmark import check
from evaluation.router_cases import CASES, Case
from modules.router.router import Request, count_words, route

ALGOS = ["v0_policy_table", "v1_hybrid_naive", "v2_hybrid_windowed", "v3_hardened"]
V2_ERA = [c for c in CASES if not ({"limitation", "adversarial", "v3"} & c.tags)]
ADVERSARIAL = [c for c in CASES if "adversarial" in c.tags]


def by_id(cid) -> Case:
    return next(c for c in CASES if c.id == cid)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_v3_matches_all_labels(case):
    assert check(case, route(case.req, "v3_hardened"))["exact_ok"]


@pytest.mark.parametrize("case", V2_ERA, ids=lambda c: c.id)
def test_v2_matches_original_labels(case):
    assert check(case, route(case.req, "v2_hybrid_windowed"))["exact_ok"]


@pytest.mark.parametrize("case", ADVERSARIAL, ids=lambda c: c.id)
def test_history_v2_fails_adversarial_case_and_v3_fixes_it(case):
    """Before/After evidence: keep these tests, they document why v3 exists."""
    assert not check(case, route(case.req, "v2_hybrid_windowed"))["exact_ok"]
    assert check(case, route(case.req, "v3_hardened"))["exact_ok"]


@pytest.mark.parametrize("algo", ALGOS)
@pytest.mark.parametrize("case", [c for c in CASES if "structured" in c.tags and "s14" in c.tags],
                         ids=lambda c: c.id)
def test_hard_limits_hold_in_every_version(algo, case):
    """S12/S14 on structured input must not depend on the algorithm version."""
    assert route(case.req, algo).status.value == case.status


def test_word_count_is_whitespace_based():
    assert count_words("Tại sao TP.HCM bị ngập\nvào mùa mưa\t?") == 9


def test_router_is_deterministic():
    for algo in ALGOS:
        for c in CASES:
            a, b = route(c.req, algo), route(c.req, algo)
            assert (a.status, a.codes, a.fmt, a.t_target, a.intent) == (b.status, b.codes, b.fmt, b.t_target, b.intent)


def test_history_naive_parser_false_positive_is_fixed_in_v2():
    case = by_id("trap_far_duration")
    assert not check(case, route(case.req, "v1_hybrid_naive"))["exact_ok"]   # Before
    assert check(case, route(case.req, "v2_hybrid_windowed"))["exact_ok"]    # After


def test_history_v2_limitation_is_fixed_in_v3():
    case = by_id("trap_near_duration")
    assert not check(case, route(case.req, "v2_hybrid_windowed"))["exact_ok"]
    assert check(case, route(case.req, "v3_hardened"))["exact_ok"]


def test_v0_cannot_see_duration_in_text():
    d = route(Request("Make a 5-minute video about inflation"), "v0_policy_table")
    assert d.status.value == "ACCEPT"      # the A1 weakness the hybrid fixes
