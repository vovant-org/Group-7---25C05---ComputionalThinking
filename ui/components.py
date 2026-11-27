"""Reusable UI components. Each function takes plain data and returns an HTML string.

No Streamlit import: the components can be unit-tested and rendered in any browser. Interactive pieces
(buttons that must react to a click) are wrapped in `ui/widgets.py`, which places a Streamlit button
under the card HTML.

Rules that keep the markup safe inside `st.markdown(..., unsafe_allow_html=True)`:
  * every piece of text from the backend or the user goes through `esc()` (which also neutralises `$`,
    because Streamlit would otherwise try to render `$...$` as maths);
  * the HTML is one line per component (`h()` strips the indentation and drops blank lines), because
    Markdown turns an indented line or a blank line inside an HTML block into code or a paragraph.
"""
from __future__ import annotations

import html
from typing import Iterable, Optional, Sequence

from ui.theme import MODE_COLORS

MODE_HELP = {"STATIC": "still frame", "PAN": "pan / zoom", "REVEAL": "parts appear with the narration",
             "LAYERED": "cut-out animation", "CLIP": "AI image-to-video clip"}

# ---------------------------------------------------------------------------------------------- helpers
def esc(text: object) -> str:
    """HTML-escape any value; `$` becomes an entity so Markdown never starts a maths block."""
    return html.escape(str(text), quote=True).replace("$", "&#36;")


def h(*parts: str) -> str:
    """Join HTML fragments into one line: no indentation, no blank lines."""
    out = []
    for part in parts:
        for line in str(part).splitlines():
            line = line.strip()
            if line:
                out.append(line)
    return "".join(out)


_ICONS = {
    "infographic": '<line x1="6" y1="20" x2="6" y2="11"/><line x1="12" y1="20" x2="12" y2="5"/><line x1="18" y1="20" x2="18" y2="14"/><line x1="3" y1="20.5" x2="21" y2="20.5"/>',
    "animation": '<circle cx="12" cy="12" r="9"/><polygon points="10,8.5 16,12 10,15.5"/>',
    "hybrid": '<polygon points="12,3 21,8 12,13 3,8"/><polyline points="3,12 12,17 21,12"/><polyline points="3,16 12,21 21,16"/>',
    "mic": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><line x1="12" y1="18" x2="12" y2="21"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><polyline points="12,7 12,12 15,14"/>',
    "coin": '<circle cx="12" cy="12" r="9"/><path d="M14.5 9.2c-.4-.9-1.4-1.4-2.5-1.4-1.5 0-2.6.8-2.6 2s1 1.7 2.6 2 2.6.8 2.6 2-1.1 2-2.6 2c-1.1 0-2.1-.5-2.5-1.4"/><line x1="12" y1="6" x2="12" y2="7.8"/><line x1="12" y1="16.2" x2="12" y2="18"/>',
    "check": '<polyline points="5,13 10,18 19,7"/>',
    "x": '<line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/>',
    "alert": '<path d="M12 3.5 2.8 19.5h18.4z"/><line x1="12" y1="10" x2="12" y2="14.5"/><line x1="12" y1="17.2" x2="12" y2="17.3"/>',
    "info": '<circle cx="12" cy="12" r="9"/><line x1="12" y1="11" x2="12" y2="16.5"/><line x1="12" y1="7.7" x2="12" y2="7.8"/>',
    "upload": '<path d="M12 16V4"/><path d="M7 9l5-5 5 5"/><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/>',
    "subtitles": '<rect x="3" y="5" width="18" height="14" rx="3"/><line x1="7" y1="11" x2="12" y2="11"/><line x1="14" y1="11" x2="17" y2="11"/><line x1="7" y1="15" x2="10" y2="15"/><line x1="12" y1="15" x2="17" y2="15"/>',
    "video": '<rect x="3" y="5" width="18" height="14" rx="3"/><polygon points="10,9.5 15,12 10,14.5"/>',
    "sparkle": '<path d="M12 3l2.2 6.3L21 12l-6.8 2.7L12 21l-2.2-6.3L3 12l6.8-2.7z"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "layout": '<rect x="3" y="4" width="18" height="16" rx="3"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="10" y1="10" x2="10" y2="20"/>',
    "wand": '<line x1="4" y1="20" x2="14" y2="10"/><path d="M15 4l1 2 2 1-2 1-1 2-1-2-2-1 2-1z"/>',
    "wave": '<line x1="4" y1="10" x2="4" y2="14"/><line x1="8" y1="7" x2="8" y2="17"/><line x1="12" y1="4" x2="12" y2="20"/><line x1="16" y1="8" x2="16" y2="16"/><line x1="20" y1="10" x2="20" y2="14"/>',
    "list": '<line x1="8" y1="7" x2="20" y2="7"/><line x1="8" y1="12" x2="20" y2="12"/><line x1="8" y1="17" x2="20" y2="17"/><line x1="4" y1="7" x2="4.1" y2="7"/><line x1="4" y1="12" x2="4.1" y2="12"/><line x1="4" y1="17" x2="4.1" y2="17"/>',
}


def icon(name: str, size: int = 18, stroke: float = 1.8) -> str:
    body = _ICONS.get(name, _ICONS["info"])
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{body}</svg>')


def fmt_time(seconds: float) -> str:
    """72.4 -> '1:12'."""
    seconds = max(0.0, float(seconds))
    m, s = divmod(int(round(seconds)), 60)
    return f"{m}:{s:02d}"


# --------------------------------------------------------------------------------------- brand, sidebar
def brand() -> str:
    return h('<div class="sf-brand"><div class="sf-brand-mark">', icon("sparkle", 20), '</div><div>',
             '<div class="sf-brand-name">StoryFrame Studio</div>',
             '<div class="sf-brand-sub">AI video workspace</div></div></div>')


def side_label(text: str) -> str:
    return f'<div class="sf-side-label">{esc(text)}</div>'


def side_empty(text: str) -> str:
    return f'<div class="sf-side-empty">{esc(text)}</div>'


def profile(name: str, sub: str) -> str:
    initials = "".join(w[0] for w in name.split()[:2]).upper() or "?"
    return h('<div class="sf-profile"><div class="sf-avatar">', esc(initials), '</div><div>',
             f'<div class="sf-profile-name">{esc(name)}</div><div class="sf-profile-sub">{esc(sub)}</div></div></div>')


# -------------------------------------------------------------------------------------- text and badges
def hero(title: str, subtitle: str) -> str:
    return f'<div class="sf-hero"><h1>{esc(title)}</h1><p>{esc(subtitle)}</p></div>'


def heading(title: str, subtitle: str = "") -> str:
    return h(f'<div class="sf-h2">{esc(title)}</div>', f'<div class="sf-sub">{esc(subtitle)}</div>' if subtitle else "")


def section(text: str) -> str:
    return f'<div class="sf-section">{esc(text)}</div>'


def badge(text: str, kind: str = "neutral", icon_name: Optional[str] = None) -> str:
    """kind: neutral | ok | warn | err | accent | info"""
    cls = "sf-badge" + ("" if kind == "neutral" else f" {kind}")
    return f'<span class="{cls}">{icon(icon_name, 12, 2.2) if icon_name else ""}{esc(text)}</span>'


def mode_badge(mode: str) -> str:
    color = MODE_COLORS.get(mode, "#64748B")
    return (f'<span class="sf-badge" title="{esc(MODE_HELP.get(mode, ""))}" style="border-color:{color}88;color:{color};'
            f'background:{color}1A">{esc(mode)}</span>')


def metric_card(label: str, value: str, hint: str = "", icon_name: Optional[str] = None) -> str:
    return h('<div class="sf-metric"><div class="sf-metric-label">', icon(icon_name, 13) if icon_name else "", esc(label), '</div>',
             f'<div class="sf-metric-value">{esc(value)}</div>', f'<div class="sf-metric-hint">{esc(hint)}</div>' if hint else "", '</div>')


def alert(kind: str, title: str, text: str = "") -> str:
    """kind: err | warn | info | ok. Used for validation messages, errors and notices."""
    ico = {"err": "alert", "warn": "alert", "info": "info", "ok": "check"}[kind]
    return h(f'<div class="sf-alert {kind}">', icon(ico, 18), '<div>', f'<div class="t">{esc(title)}</div>',
             f'<div>{esc(text)}</div>' if text else "", '</div></div>')


def empty_state(title: str, text: str, icon_name: str = "folder") -> str:
    return h('<div class="sf-empty"><div class="sf-ico">', icon(icon_name, 24), '</div>', f'<h4>{esc(title)}</h4><p>{esc(text)}</p></div>')


# --------------------------------------------------------------------------------------------- cards
def _card(inner: str, selected: bool = False, disabled: bool = False, hover: bool = True) -> str:
    cls = "sf-card" + (" hover" if hover and not disabled else "") + (" selected" if selected else "") + (" disabled" if disabled else "")
    return f'<div class="{cls}">{inner}</div>'


def format_card(title: str, description: str, bullets: Sequence[str], icon_name: str, selected: bool = False,
                available: bool = True, note: str = "") -> str:
    """Selectable format card (INFOGRAPHIC / ANIMATION / HYBRID). `available=False` shows 'Coming soon'."""
    check = f'<div class="sf-check">{icon("check", 13, 2.6)}</div>' if selected else ""
    soon = badge("Coming soon", "warn") if not available else ""
    lis = "".join(f"<li>{esc(b)}</li>" for b in bullets)
    inner = h('<div class="sf-card-head"><div class="sf-ico">', icon(icon_name, 20), '</div>', f'<div class="sf-card-title">{esc(title)}</div>',
              check or soon, '</div>', f'<div class="sf-card-text">{esc(description)}</div>', f'<ul class="sf-bullets">{lis}</ul>',
              f'<div class="sf-card-text" style="margin-top:.5rem">{esc(note)}</div>' if note else "")
    return _card(inner, selected, disabled=not available)


def voice_card(name: str, language: str, traits: Sequence[str], selected: bool = False, note: str = "") -> str:
    check = f'<div class="sf-check">{icon("check", 13, 2.6)}</div>' if selected else ""
    chips = "".join(badge(t) for t in traits)
    inner = h('<div class="sf-card-head"><div class="sf-ico cyan sm">', icon("mic", 16), '</div>',
              f'<div><div class="sf-card-title">{esc(name)}</div><div class="sf-card-text" style="margin:0">{esc(language)}</div></div>',
              check, '</div>', f'<div class="sf-chips">{chips}</div>', f'<div class="sf-card-text" style="margin-top:.45rem">{esc(note)}</div>' if note else "")
    return _card(inner, selected)


def example_card(title: str, hint: str, icon_name: str = "wand") -> str:
    return _card(h('<div class="sf-card-head" style="margin:0"><div class="sf-ico sm">', icon(icon_name, 16), '</div>',
                   f'<div><div class="sf-card-title" style="font-size:.9rem">{esc(title)}</div>',
                   f'<div class="sf-card-text" style="margin:0;font-size:.78rem">{esc(hint)}</div></div></div>'))


def project_card(title: str, fmt: str, total_s: Optional[float], when: str, status: str = "", status_kind: str = "ok",
                 sub: str = "") -> str:
    meta = " · ".join(x for x in (fmt.title() if fmt else "", fmt_time(total_s) if total_s else "", when) if x)
    return _card(h('<div class="sf-card-head" style="margin-bottom:.2rem"><div class="sf-ico sm">', icon("video", 16), '</div>',
                   badge(status, status_kind) if status else "", '</div>',
                   f'<div class="sf-proj-title">{esc(title)}</div>', f'<div class="sf-proj-meta">{esc(meta)}</div>',
                   f'<div class="sf-proj-meta">{esc(sub)}</div>' if sub else ""))


# ------------------------------------------------------------------------------------ cost estimation
def budget_card(est: dict) -> str:
    """Cost estimation. `est` comes from ui.adapters.estimate_from_pipeline (all values from the Budget Optimizer)."""
    kind = {"within": "ok", "over": "err", "infeasible": "err", "blocked": "warn", "pending": "neutral"}.get(est.get("status_key", "pending"), "neutral")
    label = est.get("status_text", "Waiting for input")
    cost, budget = est.get("cost"), est.get("budget")
    if cost is not None and budget:
        pct = max(0.0, min(100.0, 100.0 * cost / budget))
        big = f'{cost} <span class="sf-muted" style="font-size:.95rem;font-weight:500">/ {budget} credits</span>'
        bar = f'<div class="sf-bar {"" if kind == "neutral" else kind}"><span style="width:{pct:.0f}%"></span></div>'
    elif cost is not None:
        big, bar = f"{cost} credits", ""
    else:
        big, bar = '<span class="sf-muted">—</span>', ""
    rows = []
    for key, text in (("n_scenes", "Scenes"), ("n_claims", "Claims used"), ("motion", "Scenes with motion"), ("est_total_s", "Estimated length"),
                      ("min_cost", "Cheapest feasible plan"), ("budget_source", "Budget source")):
        value = est.get(key)
        if value is None:
            continue
        if key == "motion":
            value = f"{value:.0%}"
        elif key == "est_total_s":
            value = f"{value:.0f} s"
        elif key == "min_cost":
            value = f"{value} credits"
        elif key == "budget_source":
            value = {"request": "set here", "text": "read from your text", "auto": "automatic (2× cheapest plan)"}.get(value, value)
        rows.append(f'<div class="sf-kv"><span>{esc(text)}</span><span>{esc(value)}</span></div>')
    msgs = "".join(f'<div class="sf-card-text" style="margin-top:.4rem">{esc(m)}</div>' for m in est.get("messages", []))
    inner = h('<div class="sf-card-head"><div class="sf-ico cyan sm">', icon("coin", 16), '</div>', '<div class="sf-card-title">Estimated cost</div>',
              f'<div style="margin-left:auto">{badge(label, kind)}</div></div>', f'<div class="sf-metric-value" style="margin-top:.2rem">{big}</div>', bar,
              "".join(rows), msgs,
              '<div class="sf-card-text" style="margin-top:.5rem;font-size:.74rem">Credits are the project’s assumed per-mode costs, not money. '
              'The estimate comes from the Budget Optimizer on a planning pass; the final plan can differ slightly after timing adjustments.</div>')
    return _card(inner, hover=False)


# ---------------------------------------------------------------------------------- progress tracker
def progress_tracker(stages: Sequence[dict], headline: str = "", sub: str = "", pending_label: str = "Not reached") -> str:
    """Stage list. Each stage: {title, desc, state: done|warning|failed|running|pending, detail}.
    A stage is drawn as done ONLY when the caller says so (the adapter derives that from backend logs)."""
    items = []
    for i, st in enumerate(stages, 1):
        state = st.get("state", "pending")
        mark = {"done": icon("check", 16, 2.6), "failed": icon("x", 16, 2.6), "warning": icon("alert", 15, 2.2),
                "running": '<div class="sf-spin"></div>'}.get(state, str(i))
        label = {"done": "Done", "warning": "Done with warnings", "failed": "Stopped here", "running": "Working", "pending": pending_label}[state]
        kind = {"done": "ok", "warning": "warn", "failed": "err", "running": "accent", "pending": "neutral"}[state]
        items.append(h(f'<div class="sf-step {state}"><div class="sf-dot">{mark}</div><div style="flex:1;min-width:0">',
                       f'<div style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap"><span class="sf-step-title">{esc(st["title"])}</span>{badge(label, kind)}</div>',
                       f'<div class="sf-step-desc">{esc(st.get("desc", ""))}</div>',
                       f'<div class="sf-step-detail">{esc(st["detail"])}</div>' if st.get("detail") else "", '</div></div>'))
    head = h(f'<div class="sf-h2">{esc(headline)}</div>' if headline else "", f'<div class="sf-sub">{esc(sub)}</div>' if sub else "")
    return _card(h(head, f'<div class="sf-steps">{"".join(items)}</div>'), hover=False)


# ------------------------------------------------------------------------------------------ storyboard
def scene_card(scene: dict, selected: bool = False) -> str:
    """One storyboard card. `scene` comes from ui.adapters.storyboard_scenes."""
    claims = scene.get("claims") or []
    ev = "".join(badge(c["claim_id"], "info") for c in claims)
    if not claims:
        ev = '<span class="sf-scene-text sf-muted">not recorded for this project</span>' if scene.get("evidence_missing") else \
             '<span class="sf-scene-text sf-muted">none linked</span>'
    return h(f'<div class="sf-scene{" selected" if selected else ""}"><div class="sf-scene-head"><div class="sf-scene-num">{esc(scene["scene"])}</div>',
             f'<div class="sf-scene-title">{esc(scene["title"])}</div>',
             f'<div class="sf-scene-time">{fmt_time(scene["start_s"])} · {scene["duration_s"]:.1f}s</div></div>',
             f'<div class="sf-scene-narr">{esc(scene["narration"])}</div>',
             '<div class="sf-scene-label">Visual</div>', f'<div class="sf-scene-text">{esc(scene["visual"])}</div>',
             f'<div class="sf-chips">{mode_badge(scene["mode"])}{badge(scene["layout"])}</div>',
             '<div class="sf-scene-label">Claims / evidence</div>', f'<div class="sf-chips" style="margin-top:.25rem">{ev}</div></div>')


def _ticks(total: float) -> str:
    step = next((s for s in (5, 10, 15, 30, 60) if total / s <= 9), 60)
    out, t = [], 0.0
    while t <= total + 1e-9:
        out.append(f'<span style="left:{100.0 * t / total:.2f}%">{fmt_time(t)}</span>')
        t += step
    return "".join(out)


def timeline_label(label: str, ico: str, extra_class: str = "") -> str:
    """The label at the left of one timeline row (also used by the clickable Video row in ui.widgets)."""
    return f'<div class="sf-tl-label {extra_class}">{icon(ico, 15)}{esc(label)}</div>'


def timeline_tracks(video: Sequence[dict], audio: Sequence[dict], subtitles: Sequence[dict], total_s: float,
                    selected_scene: Optional[int] = None, silent: bool = False, subtitles_note: str = "",
                    include_video: bool = True, framed: bool = True) -> str:
    """Three tracks on one time axis. Clips are positioned by their real start/end seconds.

    include_video=False leaves out the Video row (the Studio draws it as clickable buttons, see ui.widgets.timeline_video_row);
    framed=False drops the card frame so the rows can sit inside a bordered Streamlit container with those buttons."""
    total = max(total_s, max([c["end_s"] for c in video] + [0.0]), 0.001)

    def pos(c: dict) -> str:
        return f'left:{100.0 * c["start_s"] / total:.3f}%;width:{max(0.15, 100.0 * (c["end_s"] - c["start_s"]) / total):.3f}%'

    def clip(cls: str, c: dict, tip: str, body: str = "", extra_style: str = "") -> str:
        sel = " sel" if c.get("scene") == selected_scene and c.get("scene") is not None else ""
        return f'<div class="sf-clip {cls}{sel}" style="{pos(c)}{extra_style}" title="{esc(tip)}">{body}</div>'

    v = "".join(clip("video", c, "Scene %s: %.1f-%.1f s, %s" % (c["scene"], c["start_s"], c["end_s"], c["mode"]), esc(c["scene"]),
                     ";background:" + MODE_COLORS.get(c["mode"], "#64748B")) for c in video)
    a = "".join(clip("audio silent" if silent else "audio", c,
                     "Scene %s narration: %.1f-%.1f s%s" % (c["scene"], c["start_s"], c["end_s"], " (silent engine: no sound)" if silent else ""))
                for c in audio)
    s = "".join(clip("sub", dict(c, scene=None), "%.1f-%.1f s: %s" % (c["start_s"], c["end_s"], c["text"])) for c in subtitles)
    modes = []
    for c in video:
        if c["mode"] not in modes:
            modes.append(c["mode"])
    legend = "".join(f'<span><i style="background:{MODE_COLORS.get(m, "#64748B")}"></i>{esc(m)} · {esc(MODE_HELP.get(m, ""))}</span>' for m in modes)
    legend += '<span><i style="background:#22D3EE"></i>narration' + (" (silent)" if silent else "") + '</span><span><i style="background:#8B5CF6"></i>subtitle cue</span>'

    def row(label: str, ico: str, clips: str, empty: str) -> str:
        body = clips or f'<div class="sf-card-text" style="padding:.55rem .8rem;margin:0">{esc(empty)}</div>'
        return f'<div class="sf-tl-row">{timeline_label(label, ico)}<div class="sf-tl-track">{body}</div></div>'

    return h(f'<div class="sf-tl{"" if framed else " bare"}">', row("Video", "video", v, "No video clips") if include_video else "",
             row("Audio", "mic", a, "No audio clips"),
             row("Subtitles", "subtitles", s, subtitles_note or "No subtitle cues"), f'<div class="sf-axis">{_ticks(total)}</div>',
             f'<div class="sf-legend">{legend}</div></div>')


# ------------------------------------------------------------------------------------------ properties
def property_panel(scene: Optional[dict], voice: dict, evidence_note: str = "") -> str:
    """Details of the selected scene. Read-only: the backend has no scene editing, so no edit controls are drawn."""
    if scene is None:
        return empty_state("No scene selected", "Click a scene on the timeline's Video track to see its details.", "layout")
    claims = scene.get("claims") or []
    cl = "".join(f'<div class="sf-claim"><b>{esc(c["claim_id"])}</b><br>{esc(c.get("text") or "text not recorded")}</div>' for c in claims)
    if not cl:
        cl = f'<div class="sf-prop-v sf-muted">{esc(evidence_note or "No claims linked to this scene.")}</div>'

    def prop(k: str, v: str) -> str:
        return f'<div class="sf-prop"><div class="sf-prop-k">{esc(k)}</div><div class="sf-prop-v">{v}</div></div>'

    vrows = " · ".join(esc(x) for x in (voice.get("name"), voice.get("engine"), voice.get("speed")) if x) or '<span class="sf-muted">not recorded</span>'
    return _card(h(
        f'<div class="sf-card-head"><div class="sf-scene-num">{esc(scene["scene"])}</div><div class="sf-card-title">{esc(scene["title"])}</div></div>',
        prop("Narration", esc(scene["narration"])),
        prop("Duration", f'{scene["duration_s"]:.1f} s · starts at {fmt_time(scene["start_s"])}'),
        prop("Layout", f'{esc(scene["layout"])} {mode_badge(scene["mode"])}'),
        prop("Visual", esc(scene["visual"])),
        prop("Voice", vrows),
        prop("Claims and evidence", cl)), hover=False)


# ------------------------------------------------------------------------------------- video preview
def storyboard_preview(title: str, text: str) -> str:
    """Shown instead of a player when no video file exists. Never pretends a video was made."""
    return h('<div class="sf-storyboard-preview"><div class="sf-ico" style="width:52px;height:52px">', icon("layout", 26), '</div>',
             f'<div class="sf-card-title" style="margin-top:.7rem">{esc(title)}</div>', f'<div class="sf-card-text" style="max-width:420px">{esc(text)}</div></div>')


def badges(items: Iterable[tuple[str, str]]) -> str:
    """Row of badges: [(text, kind), ...]."""
    return f'<div class="sf-preview-bar">{"".join(badge(t, k) for t, k in items)}</div>'


# --------------------------------------------------------------------------------------------- wizard
def stepper(labels: Sequence[str], current: int) -> str:
    """Progress header of the step-by-step flow. `current` is 1-based; earlier steps show a check mark."""
    parts = []
    for i, label in enumerate(labels, start=1):
        state = "done" if i < current else ("on" if i == current else "")
        mark = icon("check", 13, 2.8) if i < current else str(i)
        parts.append(f'<div class="sf-wiz-step {state}"><span class="n">{mark}</span><span class="l">{esc(label)}</span></div>')
        if i < len(labels):
            parts.append('<div class="sf-wiz-line"></div>')
    return f'<div class="sf-wiz">{"".join(parts)}</div>'
