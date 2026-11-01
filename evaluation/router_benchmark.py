"""Router benchmark (S14, R5, R7). Usage: python -m evaluation.router_benchmark"""
from __future__ import annotations

import csv

from core.config import OUTPUT_DIR
from evaluation.router_cases import CASES
from modules.router.router import route

ALGOS = ["v0_policy_table", "v1_hybrid_naive", "v2_hybrid_windowed"]


def check(case, d):
    return {
        "status_ok": d.status.value == case.status,
        "exact_ok": (d.status.value == case.status and d.codes == case.codes
                     and d.fmt == case.fmt and d.t_target == case.t and d.intent == case.intent),
    }


def run():
    rows = []
    for a in ALGOS:
        for c in CASES:
            d = route(c.req, a)
            r = check(c, d)
            rows.append({"algorithm": a, "case": c.id, "tags": "|".join(sorted(c.tags)),
                         "expected_status": c.status, "got_status": d.status.value,
                         "got_codes": "|".join(sorted(d.codes)), **{k: int(v) for k, v in r.items()}})
    return rows


def summary(rows):
    out = ["| Algorithm | Status accuracy | Exact match | S12/S14 limit cases | Injection cases | Free-text exact |",
           "|---|---|---|---|---|---|"]
    for a in ALGOS:
        r = [x for x in rows if x["algorithm"] == a]
        def acc(sel, key):
            s = [x for x in r if sel(x)]
            return f"{sum(x[key] for x in s)}/{len(s)}"
        out.append(f"| {a} | {acc(lambda x: True, 'status_ok')} | {acc(lambda x: True, 'exact_ok')} "
                   f"| {acc(lambda x: 's14' in x['tags'].split('|'), 'status_ok')} "
                   f"| {acc(lambda x: 'injection' in x['tags'].split('|'), 'status_ok')} "
                   f"| {acc(lambda x: 'freetext' in x['tags'].split('|'), 'exact_ok')} |")
    return "\n".join(out)


if __name__ == "__main__":
    rows = run()
    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(OUTPUT_DIR / "router_benchmark.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(f"cases={len(CASES)} -> outputs/router_benchmark.csv\n")
    print(summary(rows))
    print("\nFailures of v2 (exact match):")
    for x in rows:
        if x["algorithm"] == "v2_hybrid_windowed" and not x["exact_ok"]:
            print(f"  - {x['case']}: expected {x['expected_status']}, got {x['got_status']} [{x['got_codes']}]")
