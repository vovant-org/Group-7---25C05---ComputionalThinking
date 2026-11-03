"""Scene Segmenter benchmark. Usage: python -m evaluation.scene_benchmark [--n 300] [--seed 21]

Two data sources:
  * hand-written cases (evaluation/scene_cases.py) built from the report's examples;
  * SYNTHETIC documents (this file): ideas with paraphrased claims, partly shared topic words,
    importance scores, facets, and GOLD ideas (the top idea of every facet + the top 30% overall).
    "skew" lowers the importance of every facet except the first, i.e. models an upstream
    scorer that over-rates one perspective. The generator is an ASSUMPTION about how claims look;
    it is not real REASON output.
Metrics (ideas are used only for scoring, never by the algorithms):
  coverage    share of gold ideas present in the selection
  redundancy  share of selected claims repeating an idea already selected
  facet cov.  share of facets that hold a gold idea and appear in the selection
  in budget   selection words within W_target +-10%
"""
from __future__ import annotations

import argparse
import csv
import random
import time

from core.config import OUTPUT_DIR, VOICE_WPM
from evaluation.scene_cases import CASES, SceneCase
from modules.scene_segmenter.segmenter import ALGORITHMS, Claim, SegParams, select_claims, target_words

FILLERS = ["the", "of", "and", "to", "is", "that", "with", "for"]


def make_doc(rng: random.Random, idx: int, skew: float) -> SceneCase:
    facets = ["science", "economics", "society", "policy"][: rng.choice([3, 4])]
    t = rng.choice([60, 90, 120])
    need = rng.uniform(3, 8) * target_words(t, VOICE_WPM)          # compression 3x-8x
    topic_words = [f"topic{idx}x{k}" for k in range(3)]
    rows, ideas, total, i = [], [], 0, 0                           # rows: (idea, facet, importance, text)
    while total < need or i < 10:
        facet = facets[i % len(facets)]
        base = rng.uniform(0.3, 1.0) * (1.0 if facet == facets[0] else 1.0 - skew)
        concept = [f"c{idx}x{i}x{k}" for k in range(rng.randint(6, 8))]
        for _ in range(rng.choice([1, 1, 2, 3])):                  # paraphrases of the same idea
            words = rng.sample(concept, max(3, round(len(concept) * rng.uniform(0.6, 0.85))))
            if rng.random() < 0.5:
                words.append(rng.choice(topic_words))
            target_len = int(min(30, max(10, round(rng.gauss(18, 5)))))
            while len(words) < target_len:
                words.insert(rng.randrange(len(words) + 1), rng.choice(FILLERS))
            rows.append((f"i{i}", facet, min(1.0, max(0.01, base + rng.gauss(0, 0.03))), " ".join(words) + "."))
            total += target_len
        ideas.append((f"i{i}", facet, base))
        i += 1
    rng.shuffle(rows)
    claims, idea_of = [], {}
    for k, (idea, facet, imp, text) in enumerate(rows):
        claims.append(Claim(f"d{idx}c{k}", text, facet, imp, order=k))
        idea_of[f"d{idx}c{k}"] = idea
    gold = {max((x for x in ideas if x[1] == f), key=lambda x: x[2])[0] for f in facets}
    gold |= {x[0] for x in sorted(ideas, key=lambda x: -x[2])[: max(1, round(0.3 * len(ideas)))]}
    return SceneCase(f"syn{idx}", t, claims, idea_of, gold)


def score(case: SceneCase, sel) -> dict:
    ideas = [case.idea_of[c.claim_id] for c in sel.claims]
    gold_facets = {c.facet for c in case.claims if case.idea_of[c.claim_id] in case.gold}
    return {
        "coverage": len(case.gold & set(ideas)) / len(case.gold),
        "redundancy": (len(ideas) - len(set(ideas))) / len(ideas) if ideas else 0.0,
        "facet_cov": len(gold_facets & {c.facet for c in sel.claims}) / len(gold_facets),
        "in_budget": int(0.9 * sel.w_target <= sel.words <= 1.1 * sel.w_target),
        "n_claims": len(sel.claims),
    }


def run(n: int, seed: int, skew: float, lam: float = 0.7, algos=None):
    rng = random.Random(seed)
    rows, params = [], SegParams(lam=lam)
    for idx in range(n):
        case = make_doc(rng, idx, skew)
        for algo in algos or ALGORITHMS:
            t0 = time.perf_counter()
            sel = select_claims(case.claims, case.t_target, algo, params)
            rows.append({"doc": idx, "skew": skew, "lam": lam, "algorithm": algo, "t_target": case.t_target,
                         "input_claims": len(case.claims), "ms": (time.perf_counter() - t0) * 1000,
                         **score(case, sel)})
    return rows


def line(label, r):
    m = lambda k: sum(x[k] for x in r) / len(r)
    return (f"| {label} | {100 * m('coverage'):.1f}% | {100 * m('redundancy'):.1f}% | {100 * m('facet_cov'):.1f}% "
            f"| {100 * m('in_budget'):.1f}% | {m('n_claims'):.1f} | {m('ms'):.1f} |")


HEAD = "| {a} | Gold coverage | Redundancy | Facet coverage | In budget (±10%) | Claims chosen | ms |\n|---|---|---|---|---|---|---|"


def handwritten_table():
    out = [HEAD.format(a="Case / algorithm")]
    for case in CASES:
        for algo in ALGORITHMS:
            r = score(case, select_claims(case.claims, case.t_target, algo))
            r["ms"] = 0.0
            out.append(line(f"{case.id} / {algo}", [r]))
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=21)
    a = ap.parse_args()
    all_rows = []
    out = ["**A. Hand-written cases (report examples, T = 60 s)**\n", handwritten_table()]
    for skew in (0.0, 0.3):
        rows = run(a.n, a.seed, skew)
        all_rows += rows
        out += [f"\n**B. Synthetic, skew {skew} ({a.n} documents, seed {a.seed})**\n", HEAD.format(a="Algorithm")]
        out += [line(algo, [x for x in rows if x["algorithm"] == algo]) for algo in ALGORITHMS]
    out += ["\n**C. MMR weight lambda (synthetic, skew 0.3)**\n", HEAD.format(a="Algorithm / lambda")]
    for algo in ("D2_mmr", "D2f_mmr_facet"):
        for lam in (0.5, 0.7, 0.9):
            rows = run(a.n, a.seed, 0.3, lam, [algo])
            all_rows += rows
            out.append(line(f"{algo} / {lam}", rows))
    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(OUTPUT_DIR / "scene_benchmark.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0]))
        w.writeheader()
        w.writerows(all_rows)
    print(f"seed {a.seed}; synthetic data = assumption, not real REASON output -> outputs/scene_benchmark.csv\n")
    print("\n".join(out))
