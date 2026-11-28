"""Apply step (c) 'motion capture for the stick figure' to the existing files. Run from the repo root:  py apply_mocap_patch.py

Same rules as apply_director_patch.py: every anchor is checked FIRST; if one is missing or ambiguous nothing is written.
Safe to run twice. Copy these new files in first: modules/video/mocap.py, tests/test_mocap.py, tests/test_mocap_wiring.py.
Needs the director patch (step b) to be applied already."""
import sys
from pathlib import Path

PATCHES = {
"modules/video/stickman.py": [
("    directions: Optional[Sequence[tuple]] = None     # [(action, from_word)] chosen by the AI director (modules/ai/director.py)\n",
 "    directions: Optional[Sequence[tuple]] = None     # [(action, from_word)] chosen by the AI director (modules/ai/director.py)\n"
 "    clips: Optional[dict] = None                     # action -> mocap.MocapClip: a beat of that action plays the clip (modules/video/mocap.py)\n"),
("    def pose_at(self, t: float, dur: float) -> tuple[Pose, float]:\n",
 "    def _act(self, b: Beat, t: float, st, ctx: Ctx) -> Pose:\n"
 "        clip = (self.clips or {}).get(b.action)\n"
 "        if clip is not None:\n"
 "            return clip.pose_at(max(0.0, t))\n"
 "        return ACTIONS[b.action](max(0.0, t), b.t1 - b.t0, st.energy, ctx)\n\n"
 "    def pose_at(self, t: float, dur: float) -> tuple[Pose, float]:\n"),
("cur = ACTIONS[b.action](max(0.0, t - b.t0), b.t1 - b.t0, st.energy, ctx)", "cur = self._act(b, t - b.t0, st, ctx)"),
("prev = ACTIONS[p.action](t - p.t0, p.t1 - p.t0, st.energy, ctx)", "prev = self._act(p, t - p.t0, st, ctx)"),
("z: int = 3, directions: Optional[Sequence[tuple]] = None) -> StickmanLayer:",
 "z: int = 3, directions: Optional[Sequence[tuple]] = None, clips: Optional[dict] = None) -> StickmanLayer:"),
("script=list(script) if script else None, directions=list(directions) if directions else None,",
 "script=list(script) if script else None, directions=list(directions) if directions else None, clips=clips,"),
],
"modules/video/animation.py": [
("audio_s: Optional[float] = None, script=None, directions=None) -> list[Layer]:",
 "audio_s: Optional[float] = None, script=None, directions=None, clips=None) -> list[Layer]:"),
("directions=directions)]", "directions=directions, clips=clips)]"),
("total: int = 1, directions=None) -> AnimatedScene:", "total: int = 1, directions=None, clips=None) -> AnimatedScene:"),
("directions=directions) + PROP_BUILDERS[plan.prop](stage)", "directions=directions, clips=clips) + PROP_BUILDERS[plan.prop](stage)"),
],
"modules/visual_engine/engine.py": [
("    directions: Optional[list] = None                          # AI director: [(action, from_word)] for the figure\n",
 "    directions: Optional[list] = None                          # AI director: [(action, from_word)] for the figure\n"
 "    clips: Optional[dict] = None                               # mocap clips by action (modules/video/mocap.py)\n"),
("audio_s=min(audio_s, duration_s), directions=self.directions)", "audio_s=min(audio_s, duration_s), directions=self.directions, clips=self.clips)"),
("recent: Sequence[tuple] = (), directions: Optional[list] = None) -> TopicScene:",
 "recent: Sequence[tuple] = (), directions: Optional[list] = None, clips: Optional[dict] = None) -> TopicScene:"),
("requested_layout=scene.layout, directions=directions)", "requested_layout=scene.layout, directions=directions, clips=clips)"),
("directions: Optional[dict] = None) -> dict[int, TopicScene]:", "directions: Optional[dict] = None, clips: Optional[dict] = None) -> dict[int, TopicScene]:"),
("(directions or {}).get(sc.scene_id))", "(directions or {}).get(sc.scene_id), clips)"),
],
"modules/video/make_video.py": [
("ai_notes: Sequence[str] = (), director=None,", "ai_notes: Sequence[str] = (), director=None, mocap=None,"),
("composed, directions = None, {}", "composed, directions, clips = None, {}, {}"),
("            directions, director_info = dres.directions, dres.info\n",
 "            directions, director_info = dres.directions, dres.info\n"
 "            if mocap is not None and directions:       # motion capture: one clip per DISTINCT directed action, fixed prompts only\n"
 "                clips = mocap.clips_for([a for beats in directions.values() for a, _ in beats])\n"),
("compose_topic_scenes(res.scenes, profile, style, directions)", "compose_topic_scenes(res.scenes, profile, style, directions, clips)"),
("directions=directions.get(s.scene_id))", "directions=directions.get(s.scene_id), clips=clips)"),
('        report["director"] = director_info\n',
 '        report["director"] = director_info\n    if mocap is not None and director_info:\n        report["mocap"] = mocap.summary()\n'),
('    a = ap.parse_args(argv)\n',
 '    ap.add_argument("--mocap", choices=["off", "folder", "local"], default="off",\n'
 '                    help="ANIMATION + --ai-director: stick figure gestures from motion capture: folder = <action>.npy files in --mocap-path, "\n'
 '                         "local = a clone of momask-codes in --mocap-path (CPU). Only fixed prompts are used; no narration is sent")\n'
 '    ap.add_argument("--mocap-path", type=Path, default=None)\n'
 '    a = ap.parse_args(argv)\n'),
("    director = None\n    if a.ai_director != \"off\":\n",
 "    mocap = None\n"
 "    if a.mocap != \"off\":\n"
 "        from modules.video.mocap import DirMocap, LocalMoMask, MocapError, MocapService\n"
 "        if a.mocap_path is None:\n"
 "            ap.error(\"--mocap needs --mocap-path\")\n"
 "        try:\n"
 "            provider = DirMocap(a.mocap_path) if a.mocap == \"folder\" else LocalMoMask(a.mocap_path)\n"
 "        except MocapError as exc:\n"
 "            print(f\"mocap error: {exc}\", file=sys.stderr)\n"
 "            return 2\n"
 "        mocap = MocapService(provider, OUTPUT_DIR / \"mocap_cache\")\n"
 "    director = None\n    if a.ai_director != \"off\":\n"),
("ai_notes=ai.notes if ai else (), director=director)", "ai_notes=ai.notes if ai else (), director=director, mocap=mocap)"),
],
}

APPEND = {"docs/iteration-log-animation.md": """

## F. Motion capture for the jointed figure (design note, NOT yet measured, NOT yet run on real MoMask output)
Code: `modules/video/mocap.py` + `clips=` in `stickman.py`, tests: `tests/test_mocap.py` (pure maths, fake provider) and
`tests/test_mocap_wiring.py`. A text-to-motion model (MoMask) gives a 22-joint 3D skeleton; the code turns it into the 2D
`Pose` angles the figure already draws (limb angle = atan2(z + 0.7|x|, -y), right side = front arm), smooths it and plays it
back (ping-pong when the beat is longer than the clip). The director still decides WHICH action starts at which word; a beat
whose action has a clip plays the clip instead of the hand-coded movement; walk-in and lip-sync are unchanged.
Privacy: each action has ONE fixed English prompt (`ACTION_PROMPTS`), so the narration is never sent and a clip is made once
per action, then cached in `outputs/mocap_cache/` (not once per scene). A failing provider changes nothing (hand-coded action).
Providers: `DirMocap` (<action>.npy made elsewhere, offline) and `LocalMoMask` (runs gen_t2m.py of a local clone on the CPU;
the command line and output folder are from the README and NOT verified). The public Hugging Face Space is NOT used: it returns
HTML with a BVH link instead of a documented API, and it logs the prompts on the owner's side.
Not measured: clip time per action on the team's laptops, whether the retargeted gestures look better than the hand-coded ones
(watch test planned), how often the 3D->2D projection hides an arm movement. Known limits: one fixed clip per action (no variety
inside a video), the figure does not travel (dx = 0), expressions stay as in the hand-coded actions.
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
            if new in text:
                continue
            n = text.count(old)
            if n != 1:
                problems.append(f"{rel}: anchor found {n} times (need exactly 1): {old[:70]!r}")
            else:
                text = text.replace(old, new)
        plan[rel] = text
    for rel in ("modules/video/mocap.py", "tests/test_mocap.py"):
        if not (root / rel).exists():
            problems.append(f"{rel}: copy this new file into the repo first")
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
        if p.exists() and "Motion capture for the jointed figure" not in p.read_text(encoding="utf-8"):
            p.write_text(p.read_text(encoding="utf-8").rstrip() + extra, encoding="utf-8")
            print("appended         ", rel)
    print("Next: py -m pytest -q")
    return 0


if __name__ == "__main__":
    sys.exit(main())
