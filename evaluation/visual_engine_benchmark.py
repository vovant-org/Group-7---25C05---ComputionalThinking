"""Benchmark of the Topic-aware Visual Engine (report: Pattern Recognition M11, Part 3; Testing & Evaluation).

Usage:  python -m evaluation.visual_engine_benchmark       -> outputs/visual_engine_benchmark.csv + a Markdown table

Compares four versions on the same cases (evaluation/visual_cases.py), each scene = one sentence of narration:
  base   the generic cut-out animation (one stick figure + 6 props chosen by explain_pattern)
  v0     engine, domain pool only: the topic decides the world, but objects are rotated, not tied to the words
  v1     v0 + objects chosen from the concepts the narration mentions (in order)
  v2     v1 + no repeated object set in the last two scenes
  v3     v2 + when no fresh object exists, differ from the LAST scene (RELAX_REPEAT) + 'packet/router/server' words  (shipped)

Metrics
  domain accuracy   topic -> domain equals the gold domain                                   (engine versions)
  gold hit          share of scenes with >= 1 object in the gold set of that sentence        (engine versions)
  repeat rate       share of scenes whose picture equals the previous scene's                 (lower is better)
  distinct          different pictures / scenes                                               (higher is better)
  cross-topic       mean Jaccard overlap of the object sets of two different topics           (lower: topics look different)
  empty scenes      scenes whose objects cover < 0.4 % of the picture at 90 % of the scene
  sync gap          largest |object appears - word spoken| over mentioned objects (s)
  ms / scene        time to build and render the frame at 90 % of an 8 s scene
The 'base' picture of a scene is the pair (prop, pose) of the Motion Planner; it has no topic, so domain accuracy
and gold hit are not applicable (n/a) rather than 0.
"""
from __future__ import annotations

import csv
import itertools
import time

import numpy as np

from core.config import OUTPUT_DIR
from core.models import Scene
from modules.video.animation import compose_animation_scene
from modules.video.composer import Style
from modules.video.motion_planner import plan_motion
from modules.visual_engine import analyse_topic, engine as E
from modules.visual_engine.engine import compose_topic_scene
from modules.visual_engine.quality import FIGURE_PARTS, MIN_COVERAGE, object_coverage
from modules.video.animation import AnimatedScene, LayerRenderer
from evaluation.visual_cases import CASES

ST = Style()
VERSIONS = ("base", "v0", "v1", "v2", "v3")


def scenes_of(sentences):
    return [Scene(scene_id=i, narration=s, explain_pattern="cause_effect", importance=0.6, facet="science")
            for i, (s, _) in enumerate(sentences)]


def run_version(version: str, topic: str, sentences):
    scenes = scenes_of(sentences)
    n = len(scenes)
    t0 = time.perf_counter()
    if version == "base":
        comp = [compose_animation_scene(s, s.narration, ST, i, n) for i, s in enumerate(scenes)]
        sigs = [(c.plan.prop, c.plan.pose) for c in comp]
        cov = []
        for c in comp:
            layers = [l for l in c.layers if l.name not in FIGURE_PARTS]
            fr = LayerRenderer(AnimatedScene(c.scene_id, c.plan, c.base, layers), 8.0, ST).frame(7.2).astype(np.int16)
            cov.append(float((np.abs(fr - np.asarray(c.base).astype(np.int16)).max(axis=2) > 24)[ST.header_h:ST.size[1] - ST.sub_h].mean()))
        ms = (time.perf_counter() - t0) * 1000 / n
        return dict(domain=None, objects=[set([c.plan.prop]) for c in comp], sigs=sigs, empty=sum(x < MIN_COVERAGE for x in cov), sync=None, ms=ms)
    prof = analyse_topic(topic, [s for s, _ in sentences])
    orig, orig_relax = E.find_concepts, E.RELAX_REPEAT
    E.RELAX_REPEAT = version == "v3"
    if version == "v0":
        E.find_concepts = lambda text, vn=None: []                  # ignore the words: domain pool only
    try:
        recent, out = [], []
        for i, s in enumerate(scenes):
            ts = compose_topic_scene(s, s.narration, prof, ST, i, n, recent if version in ("v2", "v3") else ())
            out.append(ts)
            recent = (recent + [ts.signature])[-E.RECENT:]
    finally:
        E.find_concepts, E.RELAX_REPEAT = orig, orig_relax
    cov = [object_coverage(ts, 8.0, 7.0, ST) for ts in out]
    gaps = [abs(l["appear_s"] - l["mention_s"]) for ts in out for l in ts.sync_log if l["mention_s"] is not None]
    ms = (time.perf_counter() - t0) * 1000 / n
    return dict(domain=prof.domain, objects=[set(ts.objects) for ts in out], sigs=[ts.signature for ts in out],
                empty=sum(x < MIN_COVERAGE for x in cov), sync=max(gaps, default=0.0), ms=ms)


def summarise(version: str):
    rows, sets_by_topic = [], {}
    for name, topic, gold_domain, sentences in CASES:
        r = run_version(version, topic, sentences)
        n = len(sentences)
        sigs = r["sigs"]
        gold_hit = None if version == "base" else sum(bool(o & g) for o, (_, g) in zip(r["objects"], sentences)) / n
        rows.append(dict(version=version, case=name, scenes=n,
                         domain_ok=None if version == "base" else int(r["domain"] == gold_domain),
                         gold_hit=gold_hit, repeat=sum(a == b for a, b in zip(sigs, sigs[1:])) / max(1, n - 1),
                         distinct=len(set(sigs)) / n, empty=r["empty"], sync=r["sync"], ms=r["ms"]))
        sets_by_topic[name] = set().union(*r["objects"])
    overlaps = [len(a & b) / max(1, len(a | b)) for a, b in itertools.combinations(sets_by_topic.values(), 2)]
    return rows, float(np.mean(overlaps))


def main() -> None:
    all_rows, table = [], []
    for v in VERSIONS:
        rows, cross = summarise(v)
        all_rows += rows
        m = lambda k: [r[k] for r in rows if r[k] is not None]
        avg = lambda k: (f"{np.mean(m(k)):.0%}" if m(k) else "n/a")
        table.append((v, avg("domain_ok"), avg("gold_hit"), avg("repeat"), avg("distinct"), f"{cross:.2f}",
                      f"{sum(r['empty'] for r in rows)}/{sum(r['scenes'] for r in rows)}",
                      f"{max(m('sync')):.2f}" if m("sync") else "n/a", f"{np.mean(m('ms')):.0f}"))
    out = OUTPUT_DIR / "visual_engine_benchmark.csv"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0]))
        w.writeheader()
        w.writerows(all_rows)
    print(f"{len(CASES)} topics x {len(CASES[0][3])} scenes; CSV: {out}\n")
    head = ("version", "domain acc", "gold hit", "repeat rate", "distinct", "cross-topic", "empty", "sync gap s", "ms/scene")
    print("| " + " | ".join(head) + " |\n|" + "---|" * len(head))
    for row in table:
        print("| " + " | ".join(row) + " |")


if __name__ == "__main__":
    main()
