"""Streamlit front end of the pipeline demo.   Run:  streamlit run app.py

Layout: sidebar (request + options) | status banner, stage tracker, success-criteria chips |
tabs: Timeline, Storyboard, Voice units, Router, Evidence (benchmarks).
All data shaping lives in `modules/pipeline/ui_helpers.py` (unit-tested without Streamlit).
"""
import json

import pandas as pd
import streamlit as st

from core.config import OUTPUT_DIR, VOICE_WPM
from core.models import OutputFormat
from modules.pipeline.pipeline import DEFAULT_TTS_PARAMS, STAGE_ORDER, run_pipeline
from modules.pipeline.sample_claims import TOPIC_LABELS, get_sample_claims, topic_keys
from modules.pipeline.ui_helpers import (MODE_COLORS, MODE_HELP, benchmark_summaries, chips_html, codes_html,
                                         criteria_checks, legend_html, result_summary, scene_rows,
                                         timeline_bar_html, voice_rows)
from modules.providers.mock_tts import MockTTS
from modules.router.router import Request
from modules.timeline_assembler.export import timeline_to_dict

CUSTOM = "(write your own)"
EXAMPLES = ["Make a 90-second infographic video about sleep",
            "Make a 60-second infographic video about inflation",
            "Make an infographic or animation video about sleep",
            "Make a 300-second video about sleep",
            "Make a 90-second infographic video about sleep with a budget of 16 credits"]
EXAMPLE_HINTS = {EXAMPLES[0]: "happy path", EXAMPLES[1]: "may fail S12 (too short)",
                 EXAMPLES[2]: "Router asks which format", EXAMPLES[3]: "Router rejects (> 120 s)",
                 EXAMPLES[4]: "budget too small"}

st.set_page_config(page_title="StoryFrame Studio – pipeline demo", page_icon="🎬", layout="wide")

# ------------------------------------------------------------------ state and callbacks
if "req_text" not in st.session_state:
    st.session_state["req_text"] = EXAMPLES[0]


def _on_example():
    chosen = st.session_state.get("example", CUSTOM)
    if chosen != CUSTOM:
        st.session_state["req_text"] = chosen


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("1 · Request")
    st.selectbox("Example requests", [CUSTOM] + EXAMPLES, key="example", on_change=_on_example,
                 format_func=lambda x: x if x not in EXAMPLE_HINTS else f"{x}  —  {EXAMPLE_HINTS[x]}")
    text = st.text_area("Request", key="req_text", height=110,
                        placeholder="Make a 90-second infographic video about sleep")
    n_words = len(text.split())
    st.caption(f"{n_words:,} / 1,500 words" + ("  ⚠️ over the limit, the Router will reject it" if n_words > 1500 else ""))
    topic = st.selectbox("Claim fixture pack", topic_keys(), format_func=TOPIC_LABELS.get,
                         help="Hand-written claims that stand in for the REASON step (not built yet).")

    st.header("2 · Options")
    fmt = st.selectbox("Format", ["auto"] + [f.value for f in OutputFormat],
                       help="auto = read it from the request, or default to INFOGRAPHIC.")
    t_target = st.number_input("Duration (s)", 0, 600, 0, step=5, help="0 = read it from the request (default 90 s).")
    budget = st.number_input("Budget (credits)", 0, 1000, 0, step=1,
                             help="0 = read it from the request, otherwise twice the cheapest feasible plan.")

    with st.expander("Algorithms"):
        router_algo = st.selectbox("Router", ["v3_hardened", "v2_hybrid_windowed", "v0_policy_table"])
        select_algo = st.selectbox("Claim selection", ["D2f_mmr_facet", "D2_mmr", "D1_greedy"])
        opt_algo = st.selectbox("Optimizer", ["v2_dp_motion_state", "v1_dp_post_check", "v0_greedy_upgrade"])
        voice_algo = st.selectbox("Voice Segmenter", ["F4_dp_share", "F3_dp_band", "F2_dp_deviation", "F1_greedy"])
    with st.expander("Simulated TTS"):
        wpm = st.slider("True speed (words/min)", 100, 220, int(DEFAULT_TTS_PARAMS["true_wpm"]), 5,
                        help=f"The planner assumes {VOICE_WPM:.0f} wpm; move this to see the timeline checks fail.")
        pause = st.slider("Pause per sentence (s)", 0.0, 1.0, DEFAULT_TTS_PARAMS["pause_s"], 0.05)

    run_btn = st.button("▶ Run pipeline", type="primary", disabled=not text.strip())
    st.caption("After the first run, changing any control re-runs the pipeline automatically.")

if run_btn:
    st.session_state["ran"] = True

# ------------------------------------------------------------------ header
st.title("🎬 StoryFrame Studio")
st.markdown('<span style="display:inline-block;padding:2px 10px;border-radius:12px;background:#e08a1e22;'
            'border:1px solid #e08a1e;color:#e08a1e;font-size:12px;font-weight:600">SIMULATED INPUTS</span> '
            '<span style="font-size:14px;opacity:.8">claims are hand-written fixtures and narration time comes '
            'from <code>MockTTS</code>; no video file is produced yet.</span>', unsafe_allow_html=True)
st.caption("Router → Scene Segmenter → Budget Optimizer → Voice Segmenter → Timeline Assembler")

if not st.session_state.get("ran"):
    st.info("Pick an example or type a request in the sidebar, then press **▶ Run pipeline**.")
    c1, c2, c3 = st.columns(3)
    for col, (title, body) in zip((c1, c2, c3), [
            ("1 · Understand", "The Router reads the request, fills in the format and duration, and enforces the hard limits."),
            ("2 · Plan", "Claims become scenes; the optimizer picks a render mode per scene within the budget."),
            ("3 · Check", "Voice units and the timeline are checked against S11–S19 before anything is rendered.")]):
        with col, st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(body)
    st.stop()

if not text.strip():
    st.warning("The request is empty.")
    st.stop()

# ------------------------------------------------------------------ run
request = Request(topic=text, output_format=None if fmt == "auto" else OutputFormat(fmt),
                  t_target=int(t_target) or None, budget=int(budget) or None)
tts = MockTTS(**{**DEFAULT_TTS_PARAMS, "true_wpm": float(wpm), "pause_s": float(pause)})
res = run_pipeline(request, get_sample_claims(topic), router_algorithm=router_algo,
                   selection_algorithm=select_algo, optimizer_algorithm=opt_algo,
                   voice_algorithm=voice_algo, tts=tts)

# ---- banner, stage tracker, criteria
if res.ok:
    st.success("**Timeline built** – every stage passed.  " + result_summary(res))
else:
    st.error(f"**Stopped at {res.stopped_at.value.replace('_', ' ')}** – {res.status.value}")

done = {s.stage: s for s in res.stages}
for col, stage in zip(st.columns(len(STAGE_ORDER)), STAGE_ORDER):
    log = done.get(stage)
    icon = "⏭️" if log is None else ("✅" if log.ok else "❌")
    with col, st.container(border=True):
        st.markdown(f"**{icon} {stage.value.replace('_', ' ').title()}**")
        st.caption(log.summary if log else "not run")

for m in res.messages:
    st.warning(m)

checks = criteria_checks(res)
if checks:
    st.markdown("**Success criteria on this run**")
    st.markdown(chips_html(checks), unsafe_allow_html=True)

# ------------------------------------------------------------------ tabs
tab_tl, tab_story, tab_voice, tab_route, tab_evid = st.tabs(
    ["⏱️ Timeline", "🎞️ Storyboard", "🎙️ Voice units", "🧭 Router", "📊 Evidence"])

with tab_tl:
    tl = res.timeline
    if tl is None:
        st.write("No timeline: the run stopped before the Timeline Assembler.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", f"{tl.total_s:.1f} s")
        c2.metric("Target", f"{tl.t_target:.0f} s")
        c3.metric("Deviation (S13 ≤ 5%)", f"{tl.deviation:.1%}")
        c4.metric("Cost / budget", f"{res.optimize.total_cost}/{res.budget}",
                  help=f"Budget source: {res.budget_source}. Credit costs per mode are assumptions, not measured.")
        st.markdown(timeline_bar_html(tl.entries), unsafe_allow_html=True)
        st.markdown(legend_html(tl.entries), unsafe_allow_html=True)
        if tl.codes:
            st.error("Failed checks: " + ", ".join(sorted(tl.codes)))
        d1, d2, _ = st.columns([1, 1, 3])
        d1.download_button("⬇ Timeline JSON", json.dumps(timeline_to_dict(tl), ensure_ascii=False, indent=2),
                           file_name="timeline.json", mime="application/json")
        d2.download_button("⬇ Scenes CSV", pd.DataFrame(scene_rows(res)).to_csv(index=False).encode("utf-8"),
                           file_name="scenes.csv", mime="text/csv")
        df = pd.DataFrame(scene_rows(res))[["scene", "start_s", "duration_s", "mode", "narration"]]
        st.dataframe(df, hide_index=True, column_config={
            "scene": st.column_config.NumberColumn("Scene", width="small"),
            "start_s": st.column_config.NumberColumn("Start (s)", width="small"),
            "duration_s": st.column_config.NumberColumn("Length (s)", width="small"),
            "mode": st.column_config.TextColumn("Mode", width="small"),
            "narration": st.column_config.TextColumn("Narration", width="large")})

with tab_story:
    if not res.scenes:
        st.write("No scenes: the run stopped before the Scene Segmenter finished.")
    else:
        st.write(f"**{len(res.scenes)} scenes** from {len(res.selection.claims)} selected claims "
                 f"({res.selection.algorithm}); estimated {res.scene_report['total_s']} s before audio.")
        view = st.radio("View", ["Cards", "Table"], horizontal=True, label_visibility="collapsed")
        rows = scene_rows(res)
        if view == "Table":
            st.dataframe(pd.DataFrame(rows), hide_index=True, column_config={
                "narration": st.column_config.TextColumn("narration", width="large")})
        else:
            per_row = 3
            for i in range(0, len(rows), per_row):
                for col, r in zip(st.columns(per_row), rows[i:i + per_row]):
                    color = MODE_COLORS.get(r["mode"], "#9aa0a6")
                    with col, st.container(border=True):
                        st.markdown(
                            f'<b>Scene {r["scene"]}</b> '
                            f'<span style="float:right;background:{color};color:#fff;border-radius:10px;'
                            f'padding:1px 9px;font-size:12px" title="{MODE_HELP.get(r["mode"], "")}">{r["mode"]}</span>',
                            unsafe_allow_html=True)
                        st.write(r["narration"])
                        st.caption(f'{r["layout"]} · {r["start_s"]}–{r["start_s"] + r["duration_s"]:.1f} s · '
                                   f'{r["facet"]} · {r["claims"]} · {r["cost"]} credits')

with tab_voice:
    vrows = voice_rows(res)
    if not vrows:
        st.write("No voice units: the run stopped earlier.")
    else:
        v1, v2 = st.columns(2)
        v1.metric("Units in the 10–12 s band (S19, estimated)", f"{res.voice_in_band_share:.0%}",
                  help="Computed on estimated durations; the real S19 needs a measured TTS.")
        v2.metric("Voice units", len(vrows))
        vdf = pd.DataFrame(vrows)
        st.bar_chart(vdf.set_index("unit")[["est_s"]])
        st.dataframe(vdf, hide_index=True, column_config={
            "text": st.column_config.TextColumn("text", width="large")})
        st.caption("Voice units are cut over the whole script and need not align with scene borders "
                   "(open question in the Timeline Assembler); the timeline uses per-scene audio.")

with tab_route:
    d = res.decision
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Status", d.status.value)
    r2.metric("Format", d.fmt.value if d.fmt else "-")
    r3.metric("Duration", f"{d.t_target} s" if d.t_target else "-")
    r4.metric("Input words", f"{d.word_count:,}")
    st.markdown("**Reason codes:** " + codes_html(d.codes), unsafe_allow_html=True)
    for m in d.messages:
        st.write("• " + m)

with tab_evid:
    st.caption("Aggregated from `outputs/*.csv` (re-run the `evaluation.*_benchmark` modules to refresh). "
               "These tables are the before/after evidence for the iteration logs in `docs/`.")


    @st.cache_data
    def _load():
        return benchmark_summaries(OUTPUT_DIR)


    summaries = _load()
    sections = [("budget", "Budget Optimizer – feasible instances solved",
                 "300 random instances. **Credit costs per mode are assumptions.**", "python -m evaluation.budget_benchmark"),
                ("router", "Router – exact match on the labelled cases",
                 "55 hand-written cases; some v3 labels were AI-written and still need team review.", "python -m evaluation.router_benchmark"),
                ("voice", "Voice Segmenter – S19, share of voices in 10–12 s",
                 "**Simulated TTS**, not a real voice.", "python -m evaluation.voice_benchmark"),
                ("scene", "Scene Segmenter – gold-idea coverage",
                 "**Synthetic data**, λ = 0.7, no facet skew.", "python -m evaluation.scene_benchmark")]
    for key, title, note, cmd in sections:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(note)
            data = summaries.get(key)
            if data is None:
                st.info(f"`outputs/{key}_benchmark.csv` not found. Run `{cmd}`.")
                continue
            ch, tb = st.columns([2, 3])
            ch.bar_chart(data.set_index("algorithm")[["score"]])
            tb.dataframe(data[["algorithm", "detail"]], hide_index=True, column_config={
                "detail": st.column_config.TextColumn("result", width="large")})
