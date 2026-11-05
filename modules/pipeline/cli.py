"""Command-line front end of the pipeline demo.

    python -m modules.pipeline.cli "Make a 90-second infographic video about sleep" --topic sleep
"""
from __future__ import annotations

import argparse

from modules.pipeline.pipeline import PipelineResult, run_pipeline
from modules.pipeline.sample_claims import get_sample_claims, topic_keys
from modules.router.router import Request


def format_report(r: PipelineResult) -> str:
    lines = [f"Request: {r.request.topic!r}", f"Status : {r.status.value}"
             + (f" (stopped at {r.stopped_at.value})" if r.stopped_at else ""), ""]
    for s in r.stages:
        lines.append(f"  [{'ok' if s.ok else 'XX'}] {s.stage.value:<18} {s.summary}")
    for m in r.messages:
        lines.append(f"  note: {m}")
    if r.timeline and r.timeline.entries:
        lines += ["", "  scene  start   dur  mode     narration"]
        for e in r.timeline.entries:
            mode = e.render_mode.value if e.render_mode else "-"
            lines.append(f"  {e.scene_id:>5} {e.start_s:6.1f} {e.duration_s:5.1f}  {mode:<8} {e.narration[:55]}")
    lines += ["", "  (SIMULATED: claims are fixtures, narration time comes from MockTTS)"]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("request", help="free-text request, e.g. 'Make a 90-second video about sleep'")
    ap.add_argument("--topic", choices=topic_keys(), default="sleep", help="claim fixture pack")
    ap.add_argument("--budget", type=int, default=None, help="credits (default: from the text, else auto)")
    args = ap.parse_args(argv)
    res = run_pipeline(Request(topic=args.request, budget=args.budget), get_sample_claims(args.topic))
    print(format_report(res))
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
