"""Design tokens and CSS of the "Dark Premium AI Studio" look. No Streamlit import: `css()` returns text."""
from __future__ import annotations

TOKENS = {
    "bg": "#0B0D12", "bg2": "#121620", "card": "#181E2A", "accent": "#8B5CF6", "accent2": "#06B6D4",
    "text": "#F8FAFC", "muted": "#94A3B8", "border": "#293244",
    "success": "#22C55E", "warning": "#F59E0B", "error": "#EF4444",
}
# render mode -> colour (same meaning as the older timeline bar, tuned for the dark theme)
MODE_COLORS = {"STATIC": "#64748B", "PAN": "#3B82F6", "REVEAL": "#22C55E", "LAYERED": "#F59E0B", "CLIP": "#EF4444"}
BADGE_KINDS = {"success": "success", "warning": "warning", "error": "error", "accent": "accent",
               "info": "accent2", "muted": "muted"}


def css(hide_nav: bool = True) -> str:
    """The stylesheet. hide_nav=False keeps Streamlit's automatic page list (used on the two tool pages, which have
    no sidebar of their own, so the list is how you get back to the Studio)."""
    t = TOKENS
    nav = '[data-testid="stSidebarNav"], ' if hide_nav else ""
    return f"""
<style>
:root {{
  --sf-bg:{t['bg']}; --sf-bg2:{t['bg2']}; --sf-card:{t['card']}; --sf-accent:{t['accent']};
  --sf-accent2:{t['accent2']}; --sf-text:{t['text']}; --sf-muted:{t['muted']}; --sf-border:{t['border']};
  --sf-success:{t['success']}; --sf-warning:{t['warning']}; --sf-error:{t['error']};
}}
/* our own navigation replaces Streamlit's automatic page list; the pages stay reachable from the sidebar */
{nav}footer {{ display:none !important; }}
.stApp {{ background: var(--sf-bg); color: var(--sf-text); }}
[data-testid="stSidebar"] {{ background: var(--sf-bg2); border-right: 1px solid var(--sf-border); }}
.block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1400px; }}
h1, h2, h3 {{ letter-spacing: -0.01em; }}

/* buttons */
.stButton > button, .stDownloadButton > button {{
  border-radius: 12px; border: 1px solid var(--sf-border); background: var(--sf-card); color: var(--sf-text);
  transition: border-color .15s, transform .15s, background .15s; }}
.stButton > button:hover, .stDownloadButton > button:hover {{ border-color: var(--sf-accent); transform: translateY(-1px); }}
.stButton > button[kind="primary"] {{
  background: linear-gradient(135deg, var(--sf-accent), #6D45E0); border: 0; color: #fff; font-weight: 600;
  box-shadow: 0 6px 20px rgba(139,92,246,.30); }}
.stButton > button[kind="primary"]:hover {{ filter: brightness(1.08); }}
.stButton > button:disabled {{ opacity: .45; }}

/* inputs */
.stTextArea textarea, .stTextInput input, .stNumberInput input {{
  background: var(--sf-bg2) !important; border-radius: 12px !important; border: 1px solid var(--sf-border) !important; }}
.stTextArea textarea:focus, .stTextInput input:focus {{ border-color: var(--sf-accent) !important; }}

/* cards */
.sf-card {{ background: var(--sf-card); border: 1px solid var(--sf-border); border-radius: 16px; padding: 16px 18px;
  box-shadow: 0 8px 24px rgba(0,0,0,.25); transition: border-color .15s, transform .15s; }}
.sf-card:hover {{ border-color: #3a4660; }}
.sf-card.sel {{ border-color: var(--sf-accent); box-shadow: 0 0 0 1px var(--sf-accent), 0 8px 24px rgba(139,92,246,.18); }}
.sf-card.off {{ opacity: .55; }}
.sf-title {{ font-weight: 650; font-size: 15px; margin-bottom: 4px; }}
.sf-sub {{ color: var(--sf-muted); font-size: 13px; line-height: 1.45; }}
.sf-row {{ display:flex; align-items:center; gap:10px; }}
.sf-icon {{ font-size: 22px; width: 40px; height: 40px; border-radius: 12px; display:flex; align-items:center;
  justify-content:center; background: rgba(139,92,246,.14); flex: none; }}
.sf-hero h1 {{ font-size: 2.1rem; margin: 0 0 4px 0; }}
.sf-hero p {{ color: var(--sf-muted); margin: 0 0 18px 0; font-size: 1.02rem; }}
.sf-gradient {{ background: linear-gradient(90deg, var(--sf-accent), var(--sf-accent2)); -webkit-background-clip: text;
  background-clip: text; color: transparent; }}
.sf-logo {{ display:flex; align-items:center; gap:10px; font-weight:700; font-size:17px; margin-bottom: 10px; }}
.sf-logo .mark {{ width:32px; height:32px; border-radius:10px; display:flex; align-items:center; justify-content:center;
  background: linear-gradient(135deg, var(--sf-accent), var(--sf-accent2)); }}
.sf-section {{ color: var(--sf-muted); font-size: 11px; text-transform: uppercase; letter-spacing: .08em; margin: 14px 0 6px; }}
.sf-user {{ display:flex; align-items:center; gap:10px; padding:10px; border:1px solid var(--sf-border);
  border-radius:14px; background: var(--sf-card); }}
.sf-avatar {{ width:34px; height:34px; border-radius:50%; background: linear-gradient(135deg, var(--sf-accent2), var(--sf-accent));
  display:flex; align-items:center; justify-content:center; font-weight:700; }}

/* badges */
.sf-badge {{ display:inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 600;
  border: 1px solid currentColor; line-height: 1.5; white-space: nowrap; }}

/* metric */
.sf-metric {{ background: var(--sf-card); border:1px solid var(--sf-border); border-radius:14px; padding:12px 14px; }}
.sf-metric .l {{ color: var(--sf-muted); font-size: 12px; }}
.sf-metric .v {{ font-size: 24px; font-weight: 700; margin-top: 2px; }}
.sf-metric .h {{ color: var(--sf-muted); font-size: 11px; margin-top: 2px; }}

/* progress */
.sf-bar {{ height: 8px; background: var(--sf-bg2); border-radius: 999px; overflow: hidden; border: 1px solid var(--sf-border); }}
.sf-bar > div {{ height: 100%; background: linear-gradient(90deg, var(--sf-accent), var(--sf-accent2)); border-radius: 999px; }}
.sf-step {{ display:flex; gap:12px; padding: 10px 0; border-bottom: 1px solid var(--sf-border); align-items:flex-start; }}
.sf-step:last-child {{ border-bottom: 0; }}
.sf-dot {{ width:26px; height:26px; border-radius:50%; flex:none; display:flex; align-items:center; justify-content:center;
  font-size: 13px; font-weight:700; border: 1px solid var(--sf-border); color: var(--sf-muted); }}
.sf-dot.done {{ background: rgba(34,197,94,.15); border-color: var(--sf-success); color: var(--sf-success); }}
.sf-dot.run {{ background: rgba(139,92,246,.18); border-color: var(--sf-accent); color: var(--sf-accent); }}
.sf-dot.fail {{ background: rgba(239,68,68,.15); border-color: var(--sf-error); color: var(--sf-error); }}

/* timeline tracks */
.sf-track {{ display:flex; align-items:center; gap:10px; margin: 6px 0; }}
.sf-track .name {{ width: 74px; flex:none; color: var(--sf-muted); font-size: 12px; }}
.sf-lane {{ position: relative; flex: 1; height: 34px; background: var(--sf-bg2); border:1px solid var(--sf-border);
  border-radius: 10px; overflow: hidden; }}
.sf-clip {{ position:absolute; top:3px; bottom:3px; border-radius:7px; overflow:hidden; font-size: 11px; color:#fff;
  display:flex; align-items:center; justify-content:center; padding: 0 4px; white-space: nowrap; text-overflow: ellipsis;
  outline: 1px solid rgba(11,13,18,.75); }}
.sf-ruler {{ position: relative; height: 16px; margin-left: 84px; }}
.sf-ruler span {{ position:absolute; transform: translateX(-50%); font-size: 11px; color: var(--sf-muted); }}

/* responsive: tablets and narrow windows */
@media (max-width: 1100px) {{ .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
  .sf-hero h1 {{ font-size: 1.6rem; }} .sf-track .name {{ width: 56px; }} .sf-ruler {{ margin-left: 66px; }} }}
</style>
"""
