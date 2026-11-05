"""Streamlit front end of the pipeline demo (Lab04).   Run:  streamlit run app.py"""
import pandas as pd
import streamlit as st

from core.config import VOICE_WPM
from core.models import OutputFormat
from modules.pipeline.pipeline import DEFAULT_TTS_PARAMS, STAGE_ORDER, PipelineStatus, run_pipeline
from modules.pipeline.sample_claims import TOPIC_LABELS, get_sample_claims, topic_keys
from modules.providers.mock_tts import MockTTS
from modules.router.router import Request

MODE_COLORS = {"STATIC": "#9aa0a6", "PAN": "#4e8cff", "REVEAL": "#2ea36b", "LAYERED": "#e08a1e", "CLIP": "#c0392b"}
EXAMPLES = ["Make a 90-second infographic video about sleep",
            "Make a 60-second infographic video about inflation",
            "Make an infographic or animation video about sleep",
            "Make a 300-second video about sleep",
            "Make a 90-second infographic video about sleep with a budget of 16 credits"]

st.set_page_config(page_title="StoryFrame Studio – pipeline demo", layout="wide")
st.title("StoryFrame Studio – pipeline demo")
st.caption("Router → Scene Segmenter → Budget Optimizer → Voice Segmenter → Timeline Assembler. "
           "**Simulated inputs:** claims are hand-written fixtures and narration time comes from MockTTS.")

with st.sidebar:
    st.header("Request")
    example = st.selectbox("Example requests", ["(write your own)"] + EXAMPLES)
    text = st.text_area("Request", value="" if example == "(write your own)" else example,
                        placeholder="Make a 90-second infographic video about sleep")
    topic = st.selectbox("Claim fixture pack", topic_keys(), format_func=TOPIC_LABELS.get)
    fmt = st.selectbox("Format (optional override)", ["auto"] + [f.value for f in OutputFormat])
    t_target = st.number_input("Duration in s (0 = from text)", 0, 600, 0, step=5)
    budget = st.number_input("Budget in credits (0 = from text / auto)", 0, 1000, 0, step=1)
    st.header("Algorithms")
    router_algo = st.selectbox("Router", ["v3_hardened", "v2_hybrid_windowed", "v0_policy_table"])
    select_algo = st.selectbox("Claim selection", ["D2f_mmr_facet", "D2_mmr", "D1_greedy"])
    opt_algo = st.selectbox("Optimizer", ["v2_dp_motion_state", "v1_dp_post_check", "v0_greedy_upgrade"])
    voice_algo = st.selectbox("Voice Segmenter", ["F4_dp_share", "F3_dp_band", "F2_dp_deviation", "F1_greedy"])
    st.header("Simulated TTS")
    wpm = st.slider("True speed (words/min)", 100, 220, int(DEFAULT_TTS_PARAMS["true_wpm"]), 5,
                    help=f"The planner assumes {VOICE_WPM:.0f} wpm; move this to see the timeline checks fail.")
    pause = st.slider("Pause per sentence (s)", 0.0, 1.0, DEFAULT_TTS_PARAMS["pause_s"], 0.05)
    run_btn = st.button("Run pipeline", type="primary", disabled=not text.strip())

if not run_btn:
    st.info("Pick an example or type a request in the sidebar, then press **Run pipeline**.")
    st.stop()

request = Request(topic=text, output_format=None if fmt == "auto" else OutputFormat(fmt),
                  t_target=int(t_target) or None, budget=int(budget) or None)
tts = MockTTS(**{**DEFAULT_TTS_PARAMS, "true_wpm": float(wpm), "pause_s": float(pause)})
res = run_pipeline(request, get_sample_claims(topic), router_algorithm=router_algo,
                   selection_algorithm=select_algo, optimizer_algorithm=opt_algo,
                   voice_algorithm=voice_algo, tts=tts)

# ---- status banner and stage tracker
if res.ok:
    st.success("Timeline built: every stage passed (S12/S13 hold).")
else:
    st.error(f"Stopped at **{res.stopped_at.value}** – {res.status.value}")
done = {s.stage: s for s in res.stages}
cols = st.columns(len(STAGE_ORDER))
for col, stage in zip(cols, STAGE_ORDER):
    log = done.get(stage)
    icon = "⏭️" if log is None else ("✅" if log.ok else "❌")
    col.markdown(f"**{icon} {stage.value.replace('_', ' ')}**")
    col.caption(log.summary if log else "not run")
for m in res.messages:
    st.warning(m)

# ---- details
tab_tl, tab_scenes, tab_voice, tab_route = st.tabs(["Timeline", "Scenes & modes", "Voice units", "Router decision"])

with tab_tl:
    tl = res.timeline
    if tl is None:
        st.write("No timeline: the run stopped before the Timeline Assembler.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", f"{tl.total_s:.1f} s")
        c2.metric("Target", f"{tl.t_target:.0f} s")
        c3.metric("Deviation (S13 ≤ 5%)", f"{tl.deviation:.1%}")
        c4.metric("Cost", f"{res.optimize.total_cost}/{res.budget}")
        bars = "".join(
            f'<div title="scene {e.scene_id}: {e.duration_s:.1f}s {e.render_mode.value}" '
            f'style="flex:{e.duration_s};background:{MODE_COLORS[e.render_mode.value]};color:#fff;'
            f'font-size:12px;text-align:center;padding:10px 0;border-right:2px solid #fff;overflow:hidden">'
            f'{e.scene_id}</div>' for e in tl.entries)
        st.markdown(f'<div style="display:flex;width:100%">{bars}</div>', unsafe_allow_html=True)
        st.caption("Scene length is proportional to its duration. Colour = render mode: "
                   + ", ".join(f"{k}" for k in MODE_COLORS))
        if tl.codes:
            st.error("Failed checks: " + ", ".join(sorted(tl.codes)))
        st.dataframe(pd.DataFrame([{"scene": e.scene_id, "start_s": round(e.start_s, 1),
                                    "duration_s": round(e.duration_s, 1), "mode": e.render_mode.value,
                                    "narration": e.narration} for e in tl.entries]),
                     hide_index=True)

with tab_scenes:
    if not res.scenes:
        st.write("No scenes: the run stopped before the Scene Segmenter finished.")
    else:
        st.write(f"{len(res.scenes)} scenes from {len(res.selection.claims)} selected claims "
                 f"({res.selection.algorithm}); estimated {res.scene_report['total_s']} s.")
        st.dataframe(pd.DataFrame([{"scene": s.scene_id, "claim": ",".join(s.claim_ids), "facet": s.facet,
                                    "pattern": s.explain_pattern, "layout": s.layout,
                                    "mode": s.render_mode.value if s.render_mode else "-",
                                    "cost": s.cost_credit, "est_s": s.duration_s} for s in res.scenes]),
                     hide_index=True)

with tab_voice:
    if res.voice is None:
        st.write("No voice units: the run stopped earlier.")
    else:
        st.metric("Units inside the 10–12 s band (S19, estimated)", f"{res.voice_in_band_share:.0%}")
        st.dataframe(pd.DataFrame([{"unit": i, "sentences": len(u.sentences), "est_s": round(u.est_s, 1),
                                    "text": u.text} for i, u in enumerate(res.voice.units)]),
                     hide_index=True)
        st.caption("Voice units are cut over the whole script and need not align with scene borders "
                   "(open question in the Timeline Assembler); the timeline uses per-scene audio.")

with tab_route:
    d = res.decision
    st.write(f"**Status:** {d.status.value} · **format:** {d.fmt.value if d.fmt else '-'} · "
             f"**duration:** {d.t_target} s · **input words:** {d.word_count}")
    st.write("**Codes:** " + (", ".join(sorted(d.codes)) or "none"))
    for m in d.messages:
        st.write("• " + m)
