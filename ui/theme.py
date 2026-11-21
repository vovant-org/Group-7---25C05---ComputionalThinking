"""Design system "Dark Premium AI Studio": tokens and the global stylesheet.

`CSS` is a plain string so it can be unit-tested and rendered in any browser; `inject_theme()` is the
only function that touches Streamlit. Colours match the brief exactly.
"""
from __future__ import annotations

TOKENS = {
    "bg": "#0B0D12",          # main background
    "bg2": "#121620",         # secondary background (sidebar, inputs)
    "card": "#181E2A",        # card background
    "accent": "#8B5CF6",      # primary accent
    "accent2": "#06B6D4",     # secondary accent
    "text": "#F8FAFC",        # main text
    "muted": "#94A3B8",       # secondary text
    "border": "#293244",
    "success": "#22C55E",
    "warning": "#F59E0B",
    "error": "#EF4444",
}

# Render modes keep their meaning from the original UI (modules/pipeline/ui_helpers.MODE_COLORS) but
# use the new palette so the timeline and storyboard stay consistent with the rest of the app.
MODE_COLORS = {"STATIC": "#64748B", "PAN": "#38BDF8", "REVEAL": "#22C55E", "LAYERED": "#F59E0B", "CLIP": "#EF4444"}

CSS = """
:root{
  --sf-bg:#0B0D12;--sf-bg2:#121620;--sf-card:#181E2A;--sf-accent:#8B5CF6;--sf-accent2:#06B6D4;
  --sf-text:#F8FAFC;--sf-muted:#94A3B8;--sf-border:#293244;--sf-ok:#22C55E;--sf-warn:#F59E0B;--sf-err:#EF4444;
  --sf-radius:16px;--sf-radius-sm:12px;
}
html,body,[data-testid="stAppViewContainer"],.stApp{background:var(--sf-bg)!important;color:var(--sf-text);
  font-family:Inter,"Segoe UI",system-ui,-apple-system,Roboto,"Helvetica Neue",Arial,sans-serif}
[data-testid="stHeader"]{background:transparent!important}
[data-testid="stAppDeployButton"],.stDeployButton,#MainMenu,footer{display:none!important}
[data-testid="stSidebarNav"]{display:none!important}
.block-container{padding-top:1.6rem!important;padding-bottom:3rem!important;max-width:1440px}
h1,h2,h3,h4{letter-spacing:-.01em;color:var(--sf-text)}
a{color:var(--sf-accent2)}
hr{border-color:var(--sf-border)!important}

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"]{background:var(--sf-bg2)!important;border-right:1px solid var(--sf-border)}
section[data-testid="stSidebar"] .block-container,section[data-testid="stSidebar"] [data-testid="stSidebarContent"]{padding-top:1rem}
section[data-testid="stSidebar"] .stButton>button{width:100%;justify-content:flex-start;text-align:left;background:transparent;
  border:1px solid transparent;color:var(--sf-muted);border-radius:12px;padding:.5rem .75rem;font-weight:500;box-shadow:none;transition:all .15s ease}
section[data-testid="stSidebar"] .stButton>button:hover{background:rgba(139,92,246,.10);color:var(--sf-text);border-color:transparent}
section[data-testid="stSidebar"] .stButton>button[kind="primary"],
section[data-testid="stSidebar"] .stButton>button[data-testid="stBaseButton-primary"]{background:rgba(139,92,246,.16);
  color:var(--sf-text);border:1px solid rgba(139,92,246,.45)}
.sf-brand{display:flex;align-items:center;gap:.7rem;padding:.2rem .35rem 1rem .35rem}
.sf-brand-mark{width:36px;height:36px;border-radius:11px;display:flex;align-items:center;justify-content:center;color:#fff;
  background:linear-gradient(135deg,#8B5CF6 0%,#06B6D4 120%);box-shadow:0 6px 18px rgba(139,92,246,.35)}
.sf-brand-name{font-weight:700;font-size:1.02rem;line-height:1.1}
.sf-brand-sub{font-size:.72rem;color:var(--sf-muted)}
.sf-side-label{font-size:.68rem;letter-spacing:.09em;text-transform:uppercase;color:var(--sf-muted);padding:.9rem .35rem .3rem .35rem}
.sf-profile{display:flex;align-items:center;gap:.65rem;padding:.7rem;border:1px solid var(--sf-border);border-radius:14px;background:var(--sf-card);margin-top:1rem}
.sf-avatar{width:34px;height:34px;border-radius:50%;background:linear-gradient(135deg,#8B5CF6,#06B6D4);display:flex;align-items:center;
  justify-content:center;font-weight:700;font-size:.85rem;color:#fff}
.sf-profile-name{font-size:.86rem;font-weight:600;line-height:1.15}
.sf-profile-sub{font-size:.72rem;color:var(--sf-muted)}
.sf-side-empty{font-size:.8rem;color:var(--sf-muted);padding:.2rem .5rem}

/* ---------- typography helpers ---------- */
.sf-hero{text-align:center;padding:1.2rem 0 1.1rem 0}
.sf-hero h1{font-size:2.15rem;margin:0 0 .35rem 0;font-weight:700;background:linear-gradient(90deg,#F8FAFC 30%,#B9A5FB 100%);
  -webkit-background-clip:text;background-clip:text;color:transparent}
.sf-hero p{color:var(--sf-muted);font-size:1.02rem;margin:0}
.sf-h2{font-size:1.15rem;font-weight:650;margin:0 0 .15rem 0}
.sf-sub{color:var(--sf-muted);font-size:.86rem;margin:0 0 .8rem 0}
.sf-section{font-size:.72rem;letter-spacing:.09em;text-transform:uppercase;color:var(--sf-muted);margin:1.1rem 0 .5rem 0;font-weight:600}
.sf-muted{color:var(--sf-muted)}
.sf-mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}

/* ---------- cards ---------- */
.sf-card{background:var(--sf-card);border:1px solid var(--sf-border);border-radius:var(--sf-radius);padding:16px 18px;
  box-shadow:0 8px 24px rgba(0,0,0,.22);transition:border-color .15s ease,transform .15s ease,box-shadow .15s ease}
.sf-card.hover:hover{border-color:rgba(139,92,246,.6);transform:translateY(-1px)}
.sf-card.selected{border-color:var(--sf-accent);background:linear-gradient(180deg,rgba(139,92,246,.12),var(--sf-card) 70%);
  box-shadow:0 0 0 1px var(--sf-accent),0 12px 30px rgba(139,92,246,.18)}
.sf-card.disabled{opacity:.55}
.sf-card-title{font-weight:650;font-size:.98rem;margin:0}
.sf-card-text{color:var(--sf-muted);font-size:.84rem;margin:.25rem 0 0 0;line-height:1.45}
.sf-card-head{display:flex;align-items:center;gap:.65rem;margin-bottom:.35rem}
.sf-ico{width:38px;height:38px;border-radius:11px;display:flex;align-items:center;justify-content:center;flex:none;
  background:rgba(139,92,246,.14);color:#B9A5FB}
.sf-ico.cyan{background:rgba(6,182,212,.14);color:#67E8F9}
.sf-ico.sm{width:30px;height:30px;border-radius:9px}
.sf-card.selected .sf-ico{background:var(--sf-accent);color:#fff}
.sf-check{margin-left:auto;width:22px;height:22px;border-radius:50%;background:var(--sf-accent);color:#fff;display:flex;align-items:center;justify-content:center}
.sf-bullets{margin:.5rem 0 0 0;padding:0;list-style:none}
.sf-bullets li{font-size:.8rem;color:var(--sf-muted);padding:.12rem 0 .12rem 1rem;position:relative}
.sf-bullets li:before{content:"";position:absolute;left:0;top:.62rem;width:5px;height:5px;border-radius:50%;background:var(--sf-accent2)}

/* ---------- badges ---------- */
.sf-badge{display:inline-flex;align-items:center;gap:.35rem;padding:2px 10px;border-radius:999px;font-size:.72rem;font-weight:600;
  border:1px solid var(--sf-border);color:var(--sf-muted);background:rgba(148,163,184,.08);white-space:nowrap}
.sf-badge.ok{color:#4ADE80;border-color:rgba(34,197,94,.4);background:rgba(34,197,94,.10)}
.sf-badge.warn{color:#FBBF24;border-color:rgba(245,158,11,.45);background:rgba(245,158,11,.10)}
.sf-badge.err{color:#F87171;border-color:rgba(239,68,68,.45);background:rgba(239,68,68,.10)}
.sf-badge.accent{color:#C4B5FD;border-color:rgba(139,92,246,.5);background:rgba(139,92,246,.12)}
.sf-badge.info{color:#67E8F9;border-color:rgba(6,182,212,.45);background:rgba(6,182,212,.10)}

/* ---------- metric cards ---------- */
.sf-metric{background:var(--sf-card);border:1px solid var(--sf-border);border-radius:14px;padding:12px 14px;height:100%}
.sf-metric-label{font-size:.72rem;color:var(--sf-muted);text-transform:uppercase;letter-spacing:.07em;display:flex;align-items:center;gap:.4rem}
.sf-metric-value{font-size:1.5rem;font-weight:700;line-height:1.2;margin-top:.15rem}
.sf-metric-hint{font-size:.75rem;color:var(--sf-muted);margin-top:.1rem}

/* ---------- budget card ---------- */
.sf-bar{height:8px;border-radius:99px;background:rgba(148,163,184,.16);overflow:hidden;margin:.55rem 0 .35rem 0}
.sf-bar>span{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#8B5CF6,#06B6D4)}
.sf-bar.warn>span{background:var(--sf-warn)}.sf-bar.err>span{background:var(--sf-err)}.sf-bar.ok>span{background:linear-gradient(90deg,#22C55E,#06B6D4)}
.sf-kv{display:flex;justify-content:space-between;gap:1rem;font-size:.84rem;padding:.22rem 0;border-bottom:1px dashed rgba(41,50,68,.8)}
.sf-kv:last-child{border-bottom:none}.sf-kv span:first-child{color:var(--sf-muted)}

/* ---------- progress tracker ---------- */
.sf-steps{display:flex;flex-direction:column;gap:0}
.sf-step{display:flex;gap:.85rem;position:relative;padding-bottom:1rem}
.sf-step:last-child{padding-bottom:0}
.sf-step:not(:last-child):before{content:"";position:absolute;left:15px;top:32px;bottom:2px;width:2px;background:var(--sf-border)}
.sf-step.done:not(:last-child):before{background:rgba(34,197,94,.55)}
.sf-dot{width:32px;height:32px;border-radius:50%;flex:none;display:flex;align-items:center;justify-content:center;font-size:.8rem;font-weight:700;
  border:2px solid var(--sf-border);color:var(--sf-muted);background:var(--sf-bg2);z-index:1}
.sf-step.done .sf-dot{background:rgba(34,197,94,.15);border-color:var(--sf-ok);color:#4ADE80}
.sf-step.warning .sf-dot{background:rgba(245,158,11,.15);border-color:var(--sf-warn);color:#FBBF24}
.sf-step.failed .sf-dot{background:rgba(239,68,68,.15);border-color:var(--sf-err);color:#F87171}
.sf-step.running .sf-dot{border-color:var(--sf-accent);color:#C4B5FD;box-shadow:0 0 0 4px rgba(139,92,246,.18)}
.sf-step-title{font-weight:600;font-size:.92rem;line-height:1.2}
.sf-step.pending .sf-step-title{color:var(--sf-muted)}
.sf-step-desc{font-size:.8rem;color:var(--sf-muted);margin-top:.12rem;line-height:1.4}
.sf-step-detail{font-size:.78rem;color:#CBD5E1;margin-top:.2rem}
.sf-spin{width:14px;height:14px;border-radius:50%;border:2px solid rgba(196,181,253,.3);border-top-color:#C4B5FD;animation:sfspin .9s linear infinite}
@keyframes sfspin{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion:reduce){.sf-spin{animation:none}.sf-card,.sf-card.hover:hover{transition:none;transform:none}}

/* ---------- storyboard ---------- */
.sf-scene{background:var(--sf-card);border:1px solid var(--sf-border);border-radius:var(--sf-radius);padding:14px 16px;height:100%;
  transition:border-color .15s ease}
.sf-scene:hover{border-color:rgba(139,92,246,.55)}
.sf-scene.selected{border-color:var(--sf-accent);box-shadow:0 0 0 1px var(--sf-accent)}
.sf-scene-head{display:flex;align-items:center;gap:.55rem;margin-bottom:.5rem}
.sf-scene-num{width:28px;height:28px;border-radius:9px;background:rgba(139,92,246,.18);color:#C4B5FD;font-weight:700;font-size:.82rem;
  display:flex;align-items:center;justify-content:center;flex:none}
.sf-scene-title{font-weight:650;font-size:.9rem;line-height:1.2}
.sf-scene-time{margin-left:auto;font-size:.74rem;color:var(--sf-muted);white-space:nowrap}
.sf-scene-narr{font-size:.86rem;line-height:1.5;margin:.15rem 0 .55rem 0}
.sf-scene-label{font-size:.66rem;text-transform:uppercase;letter-spacing:.08em;color:var(--sf-muted);margin-top:.5rem;font-weight:600}
.sf-scene-text{font-size:.8rem;color:#CBD5E1;line-height:1.45}
.sf-chips{display:flex;flex-wrap:wrap;gap:.3rem;margin-top:.45rem}

/* ---------- timeline ---------- */
.sf-tl{background:var(--sf-card);border:1px solid var(--sf-border);border-radius:var(--sf-radius);padding:14px 16px}
.sf-tl-row{display:flex;align-items:stretch;gap:.7rem;margin-bottom:.45rem}
.sf-tl-label{width:92px;flex:none;display:flex;align-items:center;gap:.4rem;font-size:.76rem;color:var(--sf-muted);font-weight:600}
.sf-tl-track{position:relative;flex:1;height:38px;background:rgba(11,13,18,.7);border:1px solid var(--sf-border);border-radius:10px;overflow:hidden}
.sf-clip{position:absolute;top:3px;bottom:3px;border-radius:7px;display:flex;align-items:center;justify-content:center;overflow:hidden;
  font-size:.7rem;font-weight:700;color:#0B0D12;border-right:2px solid rgba(11,13,18,.9);min-width:2px}
.sf-clip.audio{background:linear-gradient(180deg,#22D3EE,#0891B2);color:#04202A}
.sf-clip.sub{background:linear-gradient(180deg,#A78BFA,#7C3AED);color:#fff;font-weight:600}
.sf-clip.sel{outline:2px solid #fff;outline-offset:-2px}
.sf-clip.silent{background:repeating-linear-gradient(135deg,rgba(148,163,184,.25) 0 6px,rgba(148,163,184,.1) 6px 12px);color:#CBD5E1}
.sf-axis{position:relative;height:18px;margin-left:calc(92px + .7rem)}
.sf-axis span{position:absolute;transform:translateX(-50%);font-size:.68rem;color:var(--sf-muted)}
.sf-legend{display:flex;flex-wrap:wrap;gap:.9rem;margin-top:.7rem;font-size:.76rem;color:var(--sf-muted)}
.sf-legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:.35rem;vertical-align:-1px}

/* ---------- properties ---------- */
.sf-prop{padding:.55rem 0;border-bottom:1px solid rgba(41,50,68,.7)}
.sf-prop:last-child{border-bottom:none}
.sf-prop-k{font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;color:var(--sf-muted);font-weight:600;margin-bottom:.15rem}
.sf-prop-v{font-size:.88rem;line-height:1.45}
.sf-claim{border-left:2px solid var(--sf-accent2);padding:.2rem 0 .2rem .6rem;margin:.35rem 0;font-size:.82rem;color:#CBD5E1}
.sf-claim b{color:#67E8F9;font-weight:600;font-size:.72rem}

/* ---------- states ---------- */
.sf-empty{border:1px dashed var(--sf-border);border-radius:var(--sf-radius);padding:2.2rem 1.4rem;text-align:center;background:rgba(24,30,42,.5)}
.sf-empty .sf-ico{margin:0 auto .8rem auto;width:48px;height:48px;border-radius:14px}
.sf-empty h4{margin:0 0 .3rem 0;font-size:1.02rem}
.sf-empty p{margin:0;color:var(--sf-muted);font-size:.86rem}
.sf-alert{display:flex;gap:.7rem;border-radius:14px;padding:.8rem 1rem;border:1px solid;margin:.4rem 0;font-size:.86rem;line-height:1.45}
.sf-alert .t{font-weight:650;margin-bottom:.1rem}
.sf-alert.err{background:rgba(239,68,68,.09);border-color:rgba(239,68,68,.45);color:#FCA5A5}
.sf-alert.warn{background:rgba(245,158,11,.09);border-color:rgba(245,158,11,.45);color:#FCD34D}
.sf-alert.info{background:rgba(6,182,212,.08);border-color:rgba(6,182,212,.4);color:#A5F3FC}
.sf-alert.ok{background:rgba(34,197,94,.09);border-color:rgba(34,197,94,.4);color:#86EFAC}
.sf-alert svg{flex:none;margin-top:2px}

/* ---------- video preview ---------- */
.sf-preview-bar{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;margin:.2rem 0 .7rem 0}
.sf-storyboard-preview{aspect-ratio:16/9;border-radius:16px;border:1px dashed var(--sf-border);display:flex;flex-direction:column;
  align-items:center;justify-content:center;text-align:center;background:linear-gradient(135deg,rgba(139,92,246,.08),rgba(6,182,212,.06));padding:1rem}

/* ---------- project list ---------- */
.sf-proj-title{font-weight:650;font-size:.95rem;line-height:1.3;margin:.1rem 0 .35rem 0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.sf-proj-meta{font-size:.78rem;color:var(--sf-muted);margin-top:.35rem}

/* ---------- native widget polish ---------- */
[data-testid="stTextArea"] textarea,[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input,
[data-baseweb="select"]>div{background:var(--sf-bg2)!important;border:1px solid var(--sf-border)!important;border-radius:var(--sf-radius-sm)!important}
[data-testid="stTextArea"] textarea{font-size:1.02rem;line-height:1.55;padding:.9rem 1rem}
[data-testid="stTextArea"] textarea:focus,[data-testid="stTextInput"] input:focus{border-color:var(--sf-accent)!important;box-shadow:0 0 0 1px var(--sf-accent)!important}
.stButton>button,.stDownloadButton>button{border-radius:12px;font-weight:600;transition:all .15s ease;border:1px solid var(--sf-border)}
.stButton>button:hover,.stDownloadButton>button:hover{border-color:var(--sf-accent);color:var(--sf-text)}
.stButton>button[kind="primary"],.stButton>button[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,#8B5CF6 0%,#7C4DEB 55%,#6D6AF0 100%);
  border:none;color:#fff;box-shadow:0 8px 22px rgba(139,92,246,.30)}
.stButton>button[kind="primary"]:hover,.stButton>button[data-testid="stBaseButton-primary"]:hover{filter:brightness(1.08);color:#fff}
.stButton>button:disabled{opacity:.45}
button[data-baseweb="tab"]{font-weight:600}
[data-baseweb="tab-highlight"]{background:var(--sf-accent)!important}
[data-testid="stExpander"]{border:1px solid var(--sf-border)!important;border-radius:14px!important;background:rgba(24,30,42,.55)}
[data-testid="stFileUploader"] section{background:var(--sf-bg2);border:1px dashed var(--sf-border);border-radius:14px}
[data-testid="stProgress"]>div>div>div{background:linear-gradient(90deg,#8B5CF6,#06B6D4)!important}
[data-testid="stDataFrame"]{border:1px solid var(--sf-border);border-radius:12px;overflow:hidden}
[data-testid="stVideo"] video,video{border-radius:16px;border:1px solid var(--sf-border);background:#000}
[data-testid="stAlert"]{border-radius:14px}
div[data-testid="stVerticalBlockBorderWrapper"]{border-color:var(--sf-border)!important}

/* ---------- responsive: tablet ---------- */
@media (max-width:1100px){
  .block-container{padding-left:1.1rem!important;padding-right:1.1rem!important}
  div[data-testid="stHorizontalBlock"]:has(.sf-split){flex-wrap:wrap!important;gap:1rem!important}
  div[data-testid="stHorizontalBlock"]:has(.sf-split)>div[data-testid="stColumn"],
  div[data-testid="stHorizontalBlock"]:has(.sf-split)>div[data-testid="column"]{min-width:100%!important;flex:1 1 100%!important}
  .sf-hero h1{font-size:1.7rem}
}
@media (max-width:760px){
  .sf-tl-label{width:60px}.sf-axis{margin-left:calc(60px + .7rem)}
}

/* ---------- step-by-step flow ---------- */
.sf-steps{display:flex;align-items:center;justify-content:center;gap:.4rem;margin:.2rem 0 1.5rem 0;flex-wrap:wrap}
.sf-step{display:flex;align-items:center;gap:.55rem;padding:.4rem .9rem .4rem .45rem;border:1px solid var(--sf-border);border-radius:999px;
  background:var(--sf-card);color:var(--sf-muted);font-size:.85rem;font-weight:550}
.sf-step .n{width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:var(--sf-bg2);
  border:1px solid var(--sf-border);font-size:.76rem;font-weight:700}
.sf-step.on{border-color:rgba(139,92,246,.6);background:rgba(139,92,246,.14);color:var(--sf-text)}
.sf-step.on .n{background:var(--sf-accent);border-color:transparent;color:#fff}
.sf-step.done{color:var(--sf-text)}
.sf-step.done .n{background:var(--sf-ok);border-color:transparent;color:#fff}
.sf-step-line{width:22px;height:2px;background:var(--sf-border);border-radius:2px}
@media (max-width:760px){.sf-step:not(.on) .l{display:none}.sf-step-line{width:12px}}
.stButton > button,
[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-primary"] {
    background-color: #1e2230 !important;
    color: #f8fafc !important;
    border: 1px solid #3b4254 !important;
}
.stButton > button *,
[data-testid="stBaseButton-secondary"] *,
[data-testid="stBaseButton-primary"] * {
    color: #f8fafc !important;
}
.stButton > button:hover,
[data-testid="stBaseButton-secondary"]:hover,
[data-testid="stBaseButton-primary"]:hover {
    background-color: #2b3144 !important;
    border-color: #6366f1 !important;
}
[data-testid="stSidebar"] *,
[data-testid="stRadio"] *,
label, .stMarkdown p {
    color: #f1f5f9 !important;
}
"""


def inject_theme() -> None:
    """Add the stylesheet to the current page (call once, first thing, on every page)."""
    import streamlit as st
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


def legacy_page_header() -> None:
    """For the original pages kept as developer tools: same look, plus a link back to the workspace."""
    import streamlit as st
    inject_theme()
    try:
        st.sidebar.page_link("app.py", label="← StoryFrame workspace")
    except Exception:                                   # old Streamlit without page_link, or run outside multipage mode
        pass
