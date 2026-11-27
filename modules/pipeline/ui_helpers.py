"""Pure helpers for the Streamlit page (no streamlit import, so they are unit-tested).

Everything here only READS a PipelineResult or the CSV files written by `evaluation/*`.
"""
from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

import pandas as pd

from core.config import PROFILES
from core.models import OutputFormat, TimelineEntry
from modules.pipeline.pipeline import PipelineResult
from modules.voice_library.library import VoiceLibrary, VoiceProfile
from modules.voice_segmenter.segmenter import VoiceParams, in_band

_EPS = 1e-9

MODE_COLORS = {"STATIC": "#9aa0a6", "PAN": "#4e8cff", "REVEAL": "#2ea36b",
               "LAYERED": "#e08a1e", "CLIP": "#c0392b"}
MODE_SHORT = {"STATIC": "ST", "PAN": "PN", "REVEAL": "RV", "LAYERED": "LY", "CLIP": "CL"}
MODE_HELP = {"STATIC": "still frame", "PAN": "pan / zoom", "REVEAL": "parts appear with the narration",
             "LAYERED": "cut-out animation", "CLIP": "AI image-to-video clip"}
LAYOUT_LABELS = {"cause_chain": "🔗 cause chain", "compare_2col": "⚖️ two-column compare",
                 "steps": "🪜 steps", "trend_chart": "📈 trend chart",
                 "big_number": "🔢 big number", "loop": "🔁 loop"}


CUTOUT_LABELS = {"cause_effect": "cause → effect", "bars": "bars", "steps": "steps", "chart": "chart",
                 "bulb": "idea", "bubble": "talking", "ai_picture": "AI picture"}


def layout_label(layout: Optional[str]) -> str:
    if layout and layout.startswith("cutout:"):                 # ANIMATION scene: "cutout:<prop>"
        prop = layout.split(":", 1)[1]
        return f"🧍 cut-out · {CUTOUT_LABELS.get(prop, prop)}"
    return LAYOUT_LABELS.get(layout, "🎞️ character scene" if layout is None else layout)


# ------------------------------------------------------------------ timeline bar
def _tick_step(total: float) -> float:
    for step in (5, 10, 15, 30, 60):
        if total / step <= 9:
            return step
    return 60


def timeline_bar_html(entries: Sequence[TimelineEntry]) -> str:
    """Proportional bar of the scenes (colour = render mode) with a time axis underneath."""
    if not entries:
        return ""
    total = sum(e.duration_s for e in entries)
    segs = []
    for e in entries:
        mode = e.render_mode.value if e.render_mode else "STATIC"
        tip = html.escape(f"scene {e.scene_id}: {e.start_s:.1f}-{e.start_s + e.duration_s:.1f} s, {mode}")
        segs.append(
            f'<div title="{tip}" style="flex:{e.duration_s};min-width:0;background:{MODE_COLORS[mode]};'
            f'color:#fff;text-align:center;padding:6px 0;border-right:2px solid rgba(255,255,255,.85);'
            f'overflow:hidden;line-height:1.15"><b style="font-size:13px">{e.scene_id}</b><br>'
            f'<span style="font-size:10px;opacity:.9">{MODE_SHORT[mode]}</span></div>')
    step = _tick_step(total)
    ticks, t = [], 0.0
    while t <= total + _EPS:
        ticks.append(f'<span style="position:absolute;left:{t / total * 100:.2f}%;transform:translateX(-50%);'
                     f'font-size:11px;opacity:.7">{t:g}s</span>')
        t += step
    return (f'<div style="display:flex;width:100%;border-radius:6px;overflow:hidden">{"".join(segs)}</div>'
            f'<div style="position:relative;height:18px;margin-top:2px">{"".join(ticks)}</div>')


def legend_html(entries: Sequence[TimelineEntry]) -> str:
    counts: dict[str, int] = {}
    for e in entries:
        mode = e.render_mode.value if e.render_mode else "STATIC"
        counts[mode] = counts.get(mode, 0) + 1
    chips = [f'<span style="display:inline-block;margin:2px 12px 2px 0;font-size:13px">'
             f'<span style="display:inline-block;width:11px;height:11px;border-radius:3px;'
             f'background:{MODE_COLORS[m]};margin-right:5px"></span><b>{m}</b> × {n}'
             f' <span style="opacity:.65">({MODE_HELP[m]})</span></span>'
             for m, n in counts.items()]
    return "".join(chips)


# ------------------------------------------------------------------ criteria
@dataclass(frozen=True)
class Check:
    id: str
    label: str
    status: str          # "pass" | "fail" | "info"
    detail: str


def criteria_checks(res: PipelineResult) -> list[Check]:
    """Success criteria that can be evaluated on a (simulated) run. Missing data -> no check."""
    out: list[Check] = []
    d = res.decision
    if d is not None:
        out.append(Check("S14", "input ≤ 1,500 words", "pass" if d.word_count <= 1500 else "fail",
                         f"{d.word_count} words"))
    tl = res.timeline
    if tl is not None:
        out.append(Check("S12", "60–120 s", "pass" if 60 - _EPS <= tl.total_s <= 120 + _EPS else "fail",
                         f"{tl.total_s:.1f} s"))
        out.append(Check("S13", "deviation ≤ 5 %", "pass" if tl.deviation <= 0.05 + _EPS else "fail",
                         f"{tl.deviation:.1%}"))
    elif d is not None and d.t_target is not None and not (60 <= d.t_target <= 120):
        out.append(Check("S12", "60–120 s", "fail", f"requested {d.t_target} s"))
    o = res.optimize
    if o is not None and o.feasible and d is not None and d.fmt is not None:
        need = PROFILES[d.fmt].min_motion_ratio
        out.append(Check("S11", f"motion ratio ≥ {need:.0%}", "pass" if o.motion_ratio + _EPS >= need else "fail",
                         f"{o.motion_ratio:.0%}"))
        if res.budget is not None:
            out.append(Check("S18", "cost ≤ budget", "pass" if o.total_cost <= res.budget else "fail",
                             f"{o.total_cost}/{res.budget} credits (assumed costs)"))
    if res.voice_in_band_share is not None:
        out.append(Check("S19", "voices in 10–12 s", "info", f"{res.voice_in_band_share:.0%} (estimated)"))
    return out


_STATUS = {"pass": ("#1f9d55", "✅"), "fail": ("#d64545", "❌"), "info": ("#6b7280", "ℹ️")}


def chips_html(checks: Sequence[Check]) -> str:
    chips = []
    for c in checks:
        color, icon = _STATUS[c.status]
        chips.append(f'<span style="display:inline-block;margin:3px 8px 3px 0;padding:4px 11px;'
                     f'border-radius:14px;border:1px solid {color};color:{color};font-size:13px">'
                     f'<b>{icon} {html.escape(c.id)}</b> {html.escape(c.label)}: {html.escape(c.detail)}</span>')
    return "".join(chips)


def codes_html(codes: Sequence[str]) -> str:
    if not codes:
        return '<span style="opacity:.7">none</span>'
    return "".join(f'<code style="margin-right:6px">{html.escape(c)}</code>' for c in sorted(codes))


# ------------------------------------------------------------------ summaries and tables
def result_summary(res: PipelineResult) -> str:
    d, tl = res.decision, res.timeline
    if not res.ok or d is None or tl is None or res.optimize is None or res.voice is None:
        return ""
    text = (f"{d.fmt.value} · {tl.total_s:.1f} s (target {tl.t_target:.0f} s) · {len(res.scenes)} scenes · "
            f"cost {res.optimize.total_cost}/{res.budget} · motion {res.optimize.motion_ratio:.0%} · "
            f"{len(res.voice.units)} voice units")
    if res.voice_profile is not None:
        text += f" · voice {res.voice_profile.name}"
    return text


def scene_rows(res: PipelineResult) -> list[dict]:
    """One row per scene: plan data, plus the timeline placement when a timeline exists."""
    placed = {e.scene_id: e for e in res.timeline.entries} if res.timeline else {}
    rows = []
    for s in res.scenes:
        e = placed.get(s.scene_id)
        rows.append({"scene": s.scene_id,
                     "start_s": round(e.start_s if e else s.start_s, 1),
                     "duration_s": round(e.duration_s if e else s.duration_s, 1),
                     "mode": s.render_mode.value if s.render_mode else "-",
                     "layout": layout_label(s.layout), "pattern": s.explain_pattern, "facet": s.facet,
                     "claims": ", ".join(s.claim_ids), "cost": s.cost_credit, "narration": s.narration})
    return rows


def voice_rows(res: PipelineResult, p: VoiceParams = VoiceParams()) -> list[dict]:
    if res.voice is None:
        return []
    n = len(res.voice.units)
    return [{"unit": i, "sentences": len(u.sentences), "est_s": round(u.est_s, 1),
             "in 10–12 s": "✅" if in_band(u.est_s, p, last=(i == n - 1)) else "❌", "text": u.text}
            for i, u in enumerate(res.voice.units)]


# ------------------------------------------------------------------ voice library
def voice_option_label(v: VoiceProfile) -> str:
    """Text of one entry in the voice picker, e.g. 'Hoài My — female, vi-VN'."""
    return f"{v.name} — {v.gender}, {v.locale}"


def voice_caption(v: VoiceProfile, speed: float = 1.0) -> str:
    """One line under the picker: the speaking rate the planner will use, and whether it is a measurement."""
    basis = "measured" if v.wpm_is_measured else "assumed, not measured yet"
    return f"Planned at {v.planning_wpm(speed):.0f} words/min ({basis})."


def voice_library_rows(lib: VoiceLibrary, language: Optional[str] = None) -> list[dict]:
    """Rows of the voice-library table (one per voice)."""
    return [{"id": v.voice_id, "name": v.name, "language": v.language, "locale": v.locale,
             "gender": v.gender, "wpm": round(v.base_wpm), "wpm source": "measured" if v.wpm_is_measured else "assumed",
             "engine voice": v.engine_voice, "default": "★" if lib.default(v.language) == v else ""}
            for v in lib.list(language=language)]


def voice_info(res: PipelineResult) -> str:
    """Which voice a run used; empty when no voice was chosen."""
    v = res.voice_profile
    if v is None:
        return ""
    basis = "measured" if v.wpm_is_measured else "assumed"
    return (f"Voice: {v.label} · speed ×{res.voice_speed:g} · planned at {res.planning_wpm:.0f} words/min ({basis}). "
            "Durations still come from the simulated TTS.")


# ------------------------------------------------------------------ benchmark evidence
def _read(out_dir: Path, name: str) -> Optional[pd.DataFrame]:
    path = Path(out_dir) / name
    return pd.read_csv(path) if path.exists() else None


def _pct(x: float) -> str:
    return f"{x:.1%}"


def benchmark_summaries(out_dir: Path) -> dict[str, Optional[pd.DataFrame]]:
    """Aggregate `outputs/*.csv` into small tables with columns [algorithm, score (0-1), detail].

    The aggregation reproduces the headline numbers of the iteration logs:
    budget 88.6/88.6/100 %, router exact 27/47/48/55 of 55, voice S19 25.3 -> 35.0 % (simulated TTS),
    scene gold coverage 65.4 -> 88.0 % (synthetic data)."""
    out: dict[str, Optional[pd.DataFrame]] = {}

    b = _read(out_dir, "budget_benchmark.csv")
    if b is not None:
        rows = []
        for algo, g in b.groupby("algorithm", sort=False):
            feas = g[g["truly_feasible"] == 1]
            solved, n = int(feas["found_plan"].sum()), len(feas)
            rows.append({"algorithm": algo, "score": solved / n if n else 0.0,
                         "detail": f"{solved}/{n} feasible instances solved, "
                                   f"{int(g['over_budget'].sum())} over-budget plans, "
                                   f"{g['runtime_ms'].mean():.1f} ms on average"})
        out["budget"] = pd.DataFrame(rows)

    r = _read(out_dir, "router_benchmark.csv")
    if r is not None:
        rows = []
        for algo, g in r.groupby("algorithm", sort=False):
            ok, n = int(g["exact_ok"].sum()), len(g)
            rows.append({"algorithm": algo, "score": ok / n,
                         "detail": f"exact match {ok}/{n}, status correct {int(g['status_ok'].sum())}/{n}"})
        out["router"] = pd.DataFrame(rows)

    v = _read(out_dir, "voice_benchmark.csv")
    if v is not None:
        x = v[(v["max_sentences"] == 2) & (v["repair"] == 0) & (v["calibration"] == "none")]
        rows = []
        for algo, g in x.groupby("algorithm", sort=False):
            s19 = g["actual_in_band"].sum() / g["voices"].sum()
            rows.append({"algorithm": algo, "score": float(s19),
                         "detail": f"S19 {_pct(s19)} of voices in 10–12 s, "
                                   f"{g['synth_calls'].mean():.1f} TTS calls per script"})
        out["voice"] = pd.DataFrame(rows)

    s = _read(out_dir, "scene_benchmark.csv")
    if s is not None:
        y = s[(s["skew"] == 0.0) & (s["lam"] == 0.7)]
        rows = []
        for algo, g in y.groupby("algorithm", sort=False):
            m = g[["coverage", "redundancy", "facet_cov"]].mean()
            rows.append({"algorithm": algo, "score": float(m["coverage"]),
                         "detail": f"gold coverage {_pct(m['coverage'])}, redundancy {_pct(m['redundancy'])}, "
                                   f"facet coverage {_pct(m['facet_cov'])}"})
        out["scene"] = pd.DataFrame(rows)
    return out


# ------------------------------------------------------------------ "Make video" page
# key -> (label, one-line help, format handed to the Router; None = read it from the request text)
VIDEO_FORMATS = {
    "auto": ("Auto", "Use the format named in the request (infographic when none is named).", None),
    "infographic": ("Infographic", "Cards, arrows and numbers drawn by code; the parts appear with the narration.",
                    OutputFormat.INFOGRAPHIC),
    "animation": ("Animation", "A cut-out stick figure acts out each scene with keyframe motion. "
                  "AI clips (CLIP) are not available, so every scene is LAYERED.", OutputFormat.ANIMATION),
}
_CHECK_NAMES = {
    "INFOGRAPHIC": {"S11": "no AI clips", "S12": "60–120 s", "S13": "≤ 5 % off target", "S15": "labels"},
    "ANIMATION": {"S11": "every scene moves", "S12": "60–120 s", "S13": "≤ 5 % off target",
                  "S15": "no text drawn (n/a)"},
}


def format_from_choice(key: str) -> Optional[OutputFormat]:
    """The OutputFormat behind a radio choice; None for "auto". KeyError for an unknown key."""
    return VIDEO_FORMATS[key][2]


def video_check_names(fmt: str) -> dict:
    """Short names of the criteria chips, which depend on the format of the finished video."""
    return dict(_CHECK_NAMES.get(fmt, _CHECK_NAMES["INFOGRAPHIC"]))


def video_scene_rows(report: dict) -> list[dict]:
    """Table of the scenes of a finished video. Animation shows the motion plan, infographic the labels."""
    animation = report.get("format") == "ANIMATION"
    rows = []
    for t in report.get("timeline", []):
        row = {"scene": t["scene"], "start_s": t["start_s"], "length_s": t["duration_s"], "mode": t["mode"],
               "layout": layout_label(t["layout"])}
        if animation:
            row.update({"pose": t.get("pose", ""), "prop": t.get("prop", ""), "energy": t.get("energy", "")})
            row["narration"] = t["narration"]
        else:
            row["labels"] = " | ".join(t["labels"])
        rows.append(row)
    return rows


def video_metrics(report: dict) -> list[tuple[str, str, str]]:
    """Headline numbers of a finished video: (label, value, help)."""
    return [("Format", str(report.get("format", "")).title(), "format that was built"),
            ("Length", f"{report['total_s']:.1f} s", f"requested {report['t_target']:.0f} s"),
            ("Scenes", str(report["scenes"]), "one per selected claim"),
            ("Off target", f"{report['deviation']:.1%}", "S13: at most 5 %")]
