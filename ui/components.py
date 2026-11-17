"""Pure HTML builders for the reusable UI components (no Streamlit import, so they are unit-tested).

Every text that can come from the user or from a file (topic, narration, labels, project names) goes
through `html.escape`. The functions return strings meant for `st.markdown(..., unsafe_allow_html=True)`.
"""
from __future__ import annotations

import html
from typing import Optional, Sequence

from ui.theme import BADGE_KINDS, MODE_COLORS, TOKENS

_e = html.escape


def _color(kind: str) -> str:
    return TOKENS[BADGE_KINDS.get(kind, "muted")]


# ------------------------------------------------------------------ small pieces
def badge(text: str, kind: str = "muted", title: str = "") -> str:
    """Status badge. kind: success | warning | error | accent | info | muted."""
    c = _color(kind)
    tip = f' title="{_e(title)}"' if title else ""
    return (f'<span class="sf-badge" style="color:{c};background:{c}1f"{tip}>{_e(text)}</span>')


def metric_card(label: str, value: str, hint: str = "") -> str:
    h = f'<div class="h">{_e(hint)}</div>' if hint else ""
    return f'<div class="sf-metric"><div class="l">{_e(label)}</div><div class="v">{_e(value)}</div>{h}</div>'


def empty_state(icon: str, title: str, body: str) -> str:
    return (f'<div class="sf-card" style="text-align:center;padding:36px 20px">'
            f'<div style="font-size:34px">{_e(icon)}</div><div class="sf-title" style="margin-top:8px">{_e(title)}</div>'
            f'<div class="sf-sub">{_e(body)}</div></div>')


def error_box(title: str, message: str, kind: str = "error") -> str:
    c = _color(kind)
    return (f'<div class="sf-card" style="border-color:{c};background:{c}14">'
            f'<div class="sf-title" style="color:{c}">{_e(title)}</div>'
            f'<div class="sf-sub" style="color:var(--sf-text)">{_e(message)}</div></div>')


def hero(title: str, subtitle: str) -> str:
    return f'<div class="sf-hero"><h1>{_e(title)}</h1><p>{_e(subtitle)}</p></div>'


def section_label(text: str) -> str:
    return f'<div class="sf-section">{_e(text)}</div>'


def logo(name: str = "StoryFrame Studio") -> str:
    return f'<div class="sf-logo"><div class="mark">🎬</div><div>{_e(name)}</div></div>'


def user_chip(name: str, caption: str) -> str:
    initial = _e((name.strip()[:1] or "?").upper())
    return (f'<div class="sf-user"><div class="sf-avatar">{initial}</div>'
            f'<div><div style="font-weight:600;font-size:14px">{_e(name)}</div>'
            f'<div class="sf-sub" style="font-size:12px">{_e(caption)}</div></div></div>')


# ------------------------------------------------------------------ cards
def format_card(title: str, description: str, icon: str, selected: bool = False, available: bool = True,
                note: str = "") -> str:
    """One of the three video-format cards. A card that is not built is dimmed and says why."""
    cls = "sf-card" + (" sel" if selected else "") + ("" if available else " off")
    tag = badge("Selected", "accent") if selected else (badge("Not available yet", "muted") if not available else "")
    extra = f'<div class="sf-sub" style="margin-top:6px">{_e(note)}</div>' if note else ""
    return (f'<div class="{cls}"><div class="sf-row"><div class="sf-icon">{_e(icon)}</div>'
            f'<div style="flex:1"><div class="sf-title">{_e(title)}</div></div>{tag}</div>'
            f'<div class="sf-sub" style="margin-top:8px">{_e(description)}</div>{extra}</div>')


def voice_card(name: str, language: str, traits: str, selected: bool = False, rate_note: str = "") -> str:
    """A voice of the library: name, language, characteristics (gender, accent, speaking rate)."""
    cls = "sf-card" + (" sel" if selected else "")
    tag = badge("Selected", "accent") if selected else ""
    note = f'<div class="sf-sub" style="font-size:12px;margin-top:2px">{_e(rate_note)}</div>' if rate_note else ""
    return (f'<div class="{cls}" style="padding:12px 14px"><div class="sf-row">'
            f'<div class="sf-icon" style="width:34px;height:34px;font-size:17px">🎙️</div>'
            f'<div style="flex:1;min-width:0"><div class="sf-title" style="margin:0;display:flex;gap:8px;align-items:center;'
            f'flex-wrap:wrap">{_e(name)} {tag}</div>'
            f'<div class="sf-sub">{_e(language)} · {_e(traits)}</div>{note}</div></div></div>')


def example_card(icon: str, title: str, hint: str = "") -> str:
    h = f'<div class="sf-sub" style="font-size:12px">{_e(hint)}</div>' if hint else ""
    return (f'<div class="sf-card" style="padding:12px 14px"><div class="sf-row"><div class="sf-icon" '
            f'style="width:34px;height:34px;font-size:17px">{_e(icon)}</div><div><div class="sf-title" style="margin:0">'
            f'{_e(title)}</div>{h}</div></div></div>')


def budget_card(cost: Optional[int], budget: Optional[int], status: str, message: str, source: str = "") -> str:
    """Cost estimate before generation. status: ok | over | unknown."""
    kinds = {"ok": ("Within budget", "success"), "over": ("Over budget", "error"), "unknown": ("Not estimated", "warning")}
    label, kind = kinds.get(status, kinds["unknown"])
    if cost is not None and budget:
        pct = max(0.0, min(100.0, cost / budget * 100))
        bar = (f'<div class="sf-bar" style="margin:8px 0"><div style="width:{pct:.0f}%;'
               f'background:{_color(kind)}"></div></div>')
        numbers = f'<span style="font-size:24px;font-weight:700">{cost}</span> / {budget} credits'
    elif cost is not None:
        bar, numbers = "", f'<span style="font-size:24px;font-weight:700">{cost}</span> credits'
    else:
        bar, numbers = "", '<span style="font-size:24px;font-weight:700">–</span>'
    src = f" · budget: {_e(source)}" if source else ""
    return (f'<div class="sf-card"><div class="sf-row" style="justify-content:space-between">'
            f'<div class="sf-title" style="margin:0">Estimated cost</div>{badge(label, kind)}</div>'
            f'<div style="margin-top:6px">{numbers}</div>{bar}'
            f'<div class="sf-sub">{_e(message)}{src}</div></div>')


# ------------------------------------------------------------------ progress
_DOT = {"done": ("done", "✓"), "run": ("run", "●"), "fail": ("fail", "✕"), "pending": ("", "")}


def progress_tracker(stages: Sequence[dict], fraction: Optional[float] = None) -> str:
    """Step list. Each stage: {title, state: done|run|fail|pending, detail}. `fraction` draws the bar; by
    default it is the share of finished stages. A stage is only 'done' when the caller says the backend
    confirmed it."""
    n = len(stages)
    done = sum(s["state"] == "done" for s in stages)
    frac = done / n if fraction is None and n else (fraction or 0.0)
    rows = []
    for i, s in enumerate(stages, 1):
        cls, mark = _DOT.get(s["state"], _DOT["pending"])
        shown = mark or str(i)
        color = "var(--sf-text)" if s["state"] != "pending" else "var(--sf-muted)"
        rows.append(f'<div class="sf-step"><div class="sf-dot {cls}">{shown}</div><div>'
                    f'<div style="font-weight:600;font-size:14px;color:{color}">{_e(s["title"])}</div>'
                    f'<div class="sf-sub">{_e(s.get("detail", ""))}</div></div></div>')
    return (f'<div class="sf-card"><div class="sf-bar"><div style="width:{max(0.0, min(1.0, frac)) * 100:.0f}%"></div></div>'
            f'<div class="sf-sub" style="margin:6px 0 4px">{done} of {n} steps confirmed</div>{"".join(rows)}</div>')


# ------------------------------------------------------------------ storyboard
def storyboard_card(scene: dict, selected: bool = False) -> str:
    """scene: {number, title, narration, visual, layout, duration_s, mode, claims}."""
    mode = scene.get("mode") or ""
    mcolor = MODE_COLORS.get(mode, TOKENS["muted"])
    cls = "sf-card" + (" sel" if selected else "")
    claims = ", ".join(scene.get("claims") or [])
    claim_line = f' · evidence {_e(claims)}' if claims else ""
    return (f'<div class="{cls}" style="padding:14px 16px"><div class="sf-row" style="justify-content:space-between">'
            f'<div class="sf-sub" style="font-weight:700;color:var(--sf-text)">Scene {scene["number"]}</div>'
            f'<span class="sf-badge" style="color:{mcolor};background:{mcolor}1f">{_e(mode or "–")}</span></div>'
            f'<div class="sf-title" style="margin-top:6px">{_e(scene["title"])}</div>'
            f'<div class="sf-sub" style="color:var(--sf-text);margin-bottom:6px">{_e(scene["narration"])}</div>'
            f'<div class="sf-sub">🖼️ {_e(scene["visual"])}</div>'
            f'<div class="sf-sub">{_e(scene["layout"])} · {scene["duration_s"]:.1f} s{claim_line}</div></div>')


# ------------------------------------------------------------------ timeline tracks
def _ticks(total: float) -> list[float]:
    for step in (5, 10, 15, 30, 60):
        if total / step <= 9:
            break
    out, t = [], 0.0
    while t <= total + 1e-9:
        out.append(t)
        t += step
    return out


def timeline_tracks(tracks: dict, total_s: float) -> str:
    """Three lanes (Video, Audio, Subtitles) on one time axis.

    tracks = {"video": [{start, end, label, mode}], "audio": [{start, end, label, silent}], "subtitles": [{start, end, label}]}.
    The data is the real timeline; this function only positions it."""
    if total_s <= 0:
        return ""

    def lane(name: str, clips: Sequence[dict], colour) -> str:
        parts = []
        for c in clips:
            left = c["start"] / total_s * 100
            width = max(0.4, (c["end"] - c["start"]) / total_s * 100)
            col = colour(c)
            style = f"left:{left:.3f}%;width:{width:.3f}%;background:{col}"
            if c.get("silent"):
                style = (f"left:{left:.3f}%;width:{width:.3f}%;background:repeating-linear-gradient(45deg,"
                         f"{TOKENS['border']},{TOKENS['border']} 6px,{TOKENS['bg2']} 6px,{TOKENS['bg2']} 12px)")
            tip = _e(f'{c["label"]}  ({c["start"]:.1f}–{c["end"]:.1f} s)')
            parts.append(f'<div class="sf-clip" title="{tip}" style="{style}">{_e(c.get("short", ""))}</div>')
        return (f'<div class="sf-track"><div class="name">{_e(name)}</div><div class="sf-lane">{"".join(parts)}</div></div>')

    ruler = "".join(f'<span style="left:{t / total_s * 100:.2f}%">{t:g}s</span>' for t in _ticks(total_s))
    return (lane("Video", tracks.get("video", []), lambda c: MODE_COLORS.get(c.get("mode"), TOKENS["accent"]))
            + lane("Audio", tracks.get("audio", []), lambda c: TOKENS["accent"])
            + lane("Subtitles", tracks.get("subtitles", []), lambda c: TOKENS["accent2"])
            + f'<div class="sf-ruler">{ruler}</div>')


def track_legend(modes: Sequence[str]) -> str:
    chips = "".join(f'<span style="margin-right:14px;font-size:12px"><span style="display:inline-block;width:10px;height:10px;'
                    f'border-radius:3px;background:{MODE_COLORS.get(m, TOKENS["muted"])};margin-right:5px"></span>{_e(m)}</span>'
                    for m in dict.fromkeys(modes))
    return f'<div class="sf-sub" style="margin-left:84px">{chips}</div>'
