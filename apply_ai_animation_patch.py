"""Apply the 'ANIMATION from AI pictures' changes to the existing files. Run from the repo root:  py apply_ai_animation_patch.py

All anchors are checked FIRST; if any is missing or ambiguous nothing is written (so a half-patched repo is impossible).
Safe to run twice: files that already contain the new text are reported as 'already patched'."""
import sys
from pathlib import Path

PATCHES = {
"modules/video/make_video.py": [
("""    fmt = res.decision.fmt
    total_scenes = len(res.scenes)
    if fmt == OutputFormat.INFOGRAPHIC:""",
"""    fmt = res.decision.fmt
    total_scenes = len(res.scenes)
    ai_mode, ai_fallback = False, ""                 # ANIMATION drawn from AI pictures (modules/video/ai_animation.py)
    if fmt == OutputFormat.INFOGRAPHIC:"""),
("""    elif fmt == OutputFormat.ANIMATION:
        if visual_engine:""",
"""    elif fmt == OutputFormat.ANIMATION:
        composed = None
        if art is not None and visuals:             # AI pictures cut out and animated by code; all-or-nothing (policy A)
            from modules.video.ai_animation import collect_pictures, compose_ai_scenes
            pictures, ai_fallback = collect_pictures(art, res.scenes, visuals, progress=progress)
            if pictures is not None:
                composed, ai_mode = compose_ai_scenes(res.scenes, pictures, style), True
        if composed is not None:
            pass
        elif visual_engine:"""),
("    if fmt == OutputFormat.ANIMATION and visual_engine:\n",
 "    if fmt == OutputFormat.ANIMATION and visual_engine and not ai_mode:\n"),
("""    elif art is not None:
        report["notes"] = report.get("notes", []) + ["AI pictures are used for INFOGRAPHIC only; this video is not INFOGRAPHIC."]""",
"""    elif art is not None and fmt == OutputFormat.ANIMATION:
        report["ai_images"] = art.summary(total_scenes)
        if ai_mode:
            report["notes"] = report.get("notes", []) + [
                f"AI pictures: all {total_scenes} scenes use an AI picture ({art.provider.name}), cut out and animated by code. "
                "No text is drawn inside the pictures."]
        else:
            report["notes"] = report.get("notes", []) + [
                "AI pictures could not be used for every scene (" + (ai_fallback or "no picture descriptions were available")
                + "), so the whole video is the code-drawn animation (no mix of styles)."]
    elif art is not None:
        report["notes"] = report.get("notes", []) + ["AI pictures are used for INFOGRAPHIC and ANIMATION only; this video is neither."]"""),
],
"modules/ai/images.py": [
("    def summary(self, total: int) -> dict:\n",
"""    def reset_failures(self) -> None:
        \"\"\"Re-open the circuit breaker (used before a second attempt at the scenes that still have no picture).\"\"\"
        self._fails = 0

    def summary(self, total: int) -> dict:
"""),
],
"ui/runner.py": [
('image_kind=p.ai_image if p.fmt == "INFOGRAPHIC" else "off",', "image_kind=p.ai_image,"),
],
"ui/views/create.py": [
('        if ss["fmt"] == "INFOGRAPHIC":\n            st.radio("AI picture of each claim"',
 '        if ss["fmt"] in ("INFOGRAPHIC", "ANIMATION"):\n            st.radio("AI picture of each claim"'),
('if ss["ai_read"] != "off" or (ss["fmt"] == "INFOGRAPHIC" and ss["ai_image"] in ("pollinations", "cloudflare")):',
 'if ss["ai_read"] != "off" or ss["ai_image"] in ("pollinations", "cloudflare"):'),
('help="On: objects and motion follow the topic. Off: the generic stick figure with six standard props.")',
 'help="On: objects and motion follow the topic. Off: the generic stick figure with six standard props. "\n                          "Also used when AI pictures could not be made for every scene.")'),
],
"modules/pipeline/ui_helpers.py": [
('"bulb": "idea", "bubble": "talking"}', '"bulb": "idea", "bubble": "talking", "ai_picture": "AI picture"}'),
],
"ui/adapters.py": [
("""            visual = f"Stick-figure character {('(' + pose + ') ') if pose else ''}with a “{prop}” prop" if prop else "Stick-figure character\"""",
"""            visual = ("AI picture of the claim, animated by code (slide-in, zoom, float)" if t.get("prop") == "ai_picture" else
                      (f"Stick-figure character {('(' + pose + ') ') if pose else ''}with a “{prop}” prop" if prop else "Stick-figure character"))"""),
],
}

APPEND = {"docs/iteration-log-animation.md": """

## C. ANIMATION from AI pictures (design note, NOT yet measured)
Code: `modules/video/ai_animation.py`, tests: `tests/test_ai_animation.py` (fake provider, no network).
Each scene = one AI picture (same style prompt as the INFOGRAPHIC pictures) cut out of its plain white background
and animated by the existing Layer/Track parts: slide-in from alternating sides, pop, float, slow zoom; the Motion
Planner's energy scales the movement. Backdrop colour comes from the picture's dominant colour.

Fallback policy A (decision of the team): scenes without a picture are retried (2 rounds, circuit breaker re-opened,
another seed); if any scene still has none, the WHOLE video is drawn by the code-drawn animation and the report says why.
Reason: one video must never mix AI pictures with stick figures.

Not measured yet (fill in after running on a real provider; do not quote numbers before): share of pictures whose
background was removed cleanly, share of videos that fall back, render time per video.
Known limits: the cut-out assumes a plain background (the style prompt asks for it; FLUX schnell does not always obey);
FLUX schnell takes no seed, so consistency between scenes comes from the shared prompt only; the subject itself does not
move (the whole picture slides, floats and zooms), which is a limit of one still image per scene.
"""}

def main() -> int:
    root = Path(".")
    plan, problems = {}, []
    for rel, edits in PATCHES.items():
        p = root / rel
        if not p.exists():
            problems.append(f"{rel}: file not found (run from the repo root)")
            continue
        text = p.read_text(encoding="utf-8")
        for old, new in edits:
            if new in text:                      # already applied (also true when `new` contains `old`)
                continue
            n = text.count(old)
            if n != 1:
                problems.append(f"{rel}: anchor found {n} times (need exactly 1): {old[:70]!r}")
            else:
                text = text.replace(old, new)
        plan[rel] = text
    if problems:
        print("NOTHING WRITTEN. Problems:\n  " + "\n  ".join(problems))
        return 1
    for rel, text in plan.items():
        p = root / rel
        if text != p.read_text(encoding="utf-8"):
            p.write_text(text, encoding="utf-8")
            print("patched          ", rel)
        else:
            print("already patched  ", rel)
    for rel, extra in APPEND.items():
        p = root / rel
        if p.exists() and "ANIMATION from AI pictures" not in p.read_text(encoding="utf-8"):
            p.write_text(p.read_text(encoding="utf-8").rstrip() + extra, encoding="utf-8")
            print("appended         ", rel)
    print("Next: py -m pytest -q")
    return 0

if __name__ == "__main__":
    sys.exit(main())
