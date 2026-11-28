"""Apply step (b) 'AI director for the stick figure' to the existing files. Run from the repo root:  py apply_director_patch.py

Same rules as apply_ai_animation_patch.py: every anchor is checked FIRST; if one is missing or ambiguous nothing is written.
Safe to run twice (text that is already there is reported as 'already patched').
New files (copy them in first): modules/ai/director.py, tests/test_director.py."""
import sys
from pathlib import Path

PATCHES = {
"modules/video/stickman.py": [
('''    script: Optional[Sequence[Beat]] = None
    seed: int = 0
    color: tuple = INK
''',
'''    script: Optional[Sequence[Beat]] = None
    directions: Optional[Sequence[tuple]] = None     # [(action, from_word)] chosen by the AI director (modules/ai/director.py)
    seed: int = 0
    color: tuple = INK
'''),
('''        key = ("beats", round(dur, 3))
        if key not in self._cache:
            st = self.stage
            self._cache[key] = list(self.script) if self.script else choreograph(
                self.pose_name, dur, st.fx, st.s, self.role, st.energy)
''',
'''        key = ("beats", round(dur, 3), round(self.audio_s or 0.0, 3))
        if key not in self._cache:
            st = self.stage
            if self.script:
                beats = list(self.script)
            elif self.directions:
                audio = min(self.audio_s, dur) if self.audio_s else dur * 0.92
                beats = beats_from_directions(self.directions, self.narration, audio, dur, st.fx)
            else:
                beats = choreograph(self.pose_name, dur, st.fx, st.s, self.role, st.energy)
            self._cache[key] = beats
'''),
('''# ------------------------------------------------------------------ lip-sync
''',
'''MIN_BEAT_S = 0.7                        # a directed gesture lasts at least this long
DIRECT_LEAD_S = 0.15                    # a gesture starts this long BEFORE its word (the eye needs a moment)


def beats_from_directions(directions: Sequence[tuple], narration: str, audio_s: float, dur: float, fx: float) -> list[Beat]:
    # directions = [(action, from_word)]: the gesture starts when the narrator says that word (same word times as the mouth).
    # The figure always walks in first; a gap before the first gesture is filled with "talk"; invalid or too close beats are
    # dropped (walk / run are never directed). Covers [0, dur] without gaps.
    from modules.visual_engine import sync
    dur = max(float(dur), 0.5)
    walk = min(WALK_IN_PX / WALK_SPEED, 0.4 * dur)
    times = sync.word_times(narration or "", max(0.0, audio_s))
    starts: list[tuple[float, str]] = []
    for action, w in sorted(directions, key=lambda d: d[1]):
        if action not in ACTIONS or action in MOVING or not 0 <= w < len(times):
            continue
        t = max(walk, times[w][1] - DIRECT_LEAD_S)
        if t > dur - MIN_BEAT_S or (starts and t - starts[-1][0] < MIN_BEAT_S):
            continue
        starts.append((t, action))
    if not starts or starts[0][0] > walk + 0.3:
        starts.insert(0, (walk, "talk"))
    starts[0] = (walk, starts[0][1])
    ends = [t for t, _ in starts[1:]] + [dur]
    beats = [Beat("walk", 0.0, walk, x_to=fx)]
    beats += [Beat(a, t, e) for (t, a), e in zip(starts, ends)]
    return beats


# ------------------------------------------------------------------ lip-sync
'''),
('''                   audio_s: Optional[float] = None, script: Optional[Sequence[Beat]] = None, seed: int = 0,
                   z: int = 3) -> StickmanLayer:''',
'''                   audio_s: Optional[float] = None, script: Optional[Sequence[Beat]] = None, seed: int = 0,
                   z: int = 3, directions: Optional[Sequence[tuple]] = None) -> StickmanLayer:'''),
('''                         script=list(script) if script else None,
''',
'''                         script=list(script) if script else None, directions=list(directions) if directions else None,
'''),
],
"modules/video/animation.py": [
("audio_s: Optional[float] = None, script=None) -> list[Layer]:",
 "audio_s: Optional[float] = None, script=None, directions=None) -> list[Layer]:"),
("stickman_layer(stage, pose, role=role, narration=narration, audio_s=audio_s, script=script)",
 "stickman_layer(stage, pose, role=role, narration=narration, audio_s=audio_s, script=script,\n                               directions=directions)"),
("total: int = 1) -> AnimatedScene:", "total: int = 1, directions=None) -> AnimatedScene:"),
("layers = character_layers(stage, plan.pose, role=plan.role, narration=scene.narration) + PROP_BUILDERS[plan.prop](stage)",
 "layers = character_layers(stage, plan.pose, role=plan.role, narration=scene.narration,\n                              directions=directions) + PROP_BUILDERS[plan.prop](stage)"),
],
"modules/visual_engine/engine.py": [
('''    sync_log: list[dict] = field(default_factory=list)
    _built''',
'''    sync_log: list[dict] = field(default_factory=list)
    directions: Optional[list] = None                          # AI director: [(action, from_word)] for the figure
    _built'''),
("audio_s=min(audio_s, duration_s))", "audio_s=min(audio_s, duration_s), directions=self.directions)"),
("total: int = 1, recent: Sequence[tuple] = ()) -> TopicScene:",
 "total: int = 1, recent: Sequence[tuple] = (), directions: Optional[list] = None) -> TopicScene:"),
('''requested_layout=scene.layout)


def compose_topic_scenes(scenes: Sequence[Scene], profile: TopicProfile, st: Style = Style()) -> dict[int, TopicScene]:''',
'''requested_layout=scene.layout, directions=directions)


def compose_topic_scenes(scenes: Sequence[Scene], profile: TopicProfile, st: Style = Style(),
                         directions: Optional[dict] = None) -> dict[int, TopicScene]:'''),
("ts = compose_topic_scene(sc, sc.narration, profile, st, i, total, recent)",
 "ts = compose_topic_scene(sc, sc.narration, profile, st, i, total, recent, (directions or {}).get(sc.scene_id))"),
],
"modules/video/make_video.py": [
('''               ai_notes: Sequence[str] = (),
               on_stage:''',
'''               ai_notes: Sequence[str] = (), director=None,
               on_stage:'''),
("    total_scenes = len(res.scenes)\n", "    total_scenes = len(res.scenes)\n    director_info: dict = {}                         # AI director (modules/ai/director.py), ANIMATION only\n"),
('''        composed = None
        if art is not None and visuals:''',
'''        composed, directions = None, {}
        if director is not None and not (art is not None and visuals):      # AI pictures do not use the stick figure
            from modules.ai.director import direct_scenes
            dres = direct_scenes(director, res.scenes)
            directions, director_info = dres.directions, dres.info
        if art is not None and visuals:'''),
("composed = compose_topic_scenes(res.scenes, profile, style)", "composed = compose_topic_scenes(res.scenes, profile, style, directions)"),
("compose_animation_scene(s, s.narration, style, i, total_scenes)",
 "compose_animation_scene(s, s.narration, style, i, total_scenes,\n                                                          directions=directions.get(s.scene_id))"),
('''    if ai_notes:
        report["ai_notes"] = list(ai_notes)
''',
'''    if ai_notes:
        report["ai_notes"] = list(ai_notes)
    if director_info:
        report["director"] = director_info
'''),
("    a = ap.parse_args(argv)\n",
 '''    ap.add_argument("--ai-director", choices=["off", "auto", "pollinations", "gemini"], default="off",
                    help="ANIMATION: an LLM chooses the stick figure's gestures from the narration (online: needs --allow-online)")
    a = ap.parse_args(argv)
'''),
('''    lib = load_library()
    voice = lib.get(a.voice_id)''',
'''    director = None
    if a.ai_director != "off":
        from modules.ai.llm import make_llm
        from modules.ai.net import AIError
        if not a.allow_online:
            print("AI error: the AI director sends the narration to an online service: confirm with --allow-online", file=sys.stderr)
            return 2
        try:
            director = make_llm(a.ai_director)
        except AIError as exc:
            print(f"AI error: {exc}", file=sys.stderr)
            return 2
    lib = load_library()
    voice = lib.get(a.voice_id)'''),
('''ai_notes=ai.notes if ai else ())
    print()''',
'''ai_notes=ai.notes if ai else (), director=director)
    print()'''),
],
"ui/runner.py": [
('    content_origin: str = "user"',
 '    ai_director: str = "off"               # off | auto | pollinations | gemini: an LLM chooses the stick figure\'s gestures (ANIMATION)\n    content_origin: str = "user"'),
('''    claims = build_claims(p.source, p.pack, p.reference)
    text = request_text(p.topic, p.instructions)
    ai = None
''',
'''    director = None
    if p.ai_director != "off" and p.fmt == "ANIMATION":
        from modules.ai.llm import make_llm
        from modules.ai.net import AIError
        if not p.ai_online:
            return Outcome(False, error="AI: the AI director sends the narration to an online service: tick the confirmation first.")
        try:
            director = make_llm(p.ai_director)
        except AIError as exc:
            return Outcome(False, error=f"AI: {exc}")
    claims = build_claims(p.source, p.pack, p.reference)
    text = request_text(p.topic, p.instructions)
    ai = None
'''),
("ai_notes=ai.notes if ai else (), on_stage=on_stage)", "ai_notes=ai.notes if ai else (), on_stage=on_stage, director=director)"),
],
"ui/state.py": [
('"ai_read": "off", "ai_image": "off", "ai_online": False, "ai_folder": "",',
 '"ai_read": "off", "ai_image": "off", "ai_online": False, "ai_folder": "", "ai_director": "off",'),
],
"ui/views/create.py": [
('ai_read=ss["ai_read"], ai_image=ss["ai_image"], ai_online=bool(ss["ai_online"]), ai_folder=ss["ai_folder"].strip(),',
 'ai_read=ss["ai_read"], ai_image=ss["ai_image"], ai_online=bool(ss["ai_online"]), ai_folder=ss["ai_folder"].strip(),\n        ai_director=ss["ai_director"],'),
('needs = ss["ai_read"] != "off" or ss["ai_image"] in ("pollinations", "cloudflare")',
 'needs = (ss["ai_read"] != "off" or ss["ai_image"] in ("pollinations", "cloudflare")\n                 or (ss["fmt"] == "ANIMATION" and ss["ai_director"] != "off"))'),
('''        if ss["ai_read"] != "off" or ss["ai_image"] in ("pollinations", "cloudflare"):
            st.checkbox("I understand my text is sent to an online AI service"''',
'''        if ss["fmt"] == "ANIMATION":
            st.radio("AI director (stick figure gestures)", ["off", "auto", "pollinations", "gemini"], key=S.seed("ai_director"),
                     on_change=S.sync, args=("ai_director",), horizontal=True,
                     format_func={"off": "Off", "auto": "Auto (Gemini, then Pollinations)", "pollinations": "Pollinations (no key)",
                                  "gemini": "Gemini (free key)"}.get,
                     help="An AI reads the narration of every scene and chooses which gesture the figure makes at which word "
                          "(point, think, idea, shrug...). It only picks from a fixed list; if it fails the default gestures are used.")
        if (ss["ai_read"] != "off" or ss["ai_image"] in ("pollinations", "cloudflare")
                or (ss["fmt"] == "ANIMATION" and ss["ai_director"] != "off")):
            st.checkbox("I understand my text is sent to an online AI service"'''),
],
}

APPEND = {"docs/iteration-log-animation.md": """

## E. AI director for the jointed figure (design note, NOT yet measured on viewers)
Code: `modules/ai/director.py` + `stickman.beats_from_directions`, tests: `tests/test_director.py` (fake LLM, no network).
One LLM call per video: the narration of every scene with numbered words goes in; per scene a short list of
`{"from_word", "action"}` comes out, and the figure starts that gesture when the narrator says that word (same word times
as the lip-sync). The model only picks from a fixed menu (no walk/run); invalid actions, out-of-range words and beats closer
than 0.7 s are dropped; a scene without a valid answer keeps the default choreography; a provider error changes nothing and
the report (`report["director"]`) says so. The figure still walks in first. Online: needs the user's consent (`--allow-online`,
UI checkbox). Domains without a presenter figure (nature, space, tech) ignore the directions.

Not measured yet (do not quote numbers before): share of scenes with a valid answer on a real provider, whether viewers find
the directed gestures better than the Motion Planner's fixed ones, call time. Known limits: word times are estimated (H1),
so a gesture can start a little early or late against the real voice; the prompt and MAX_BEATS = 5 are our own choice.
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
    for rel in ("modules/ai/director.py", "tests/test_director.py"):
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
        if p.exists() and "AI director for the jointed figure" not in p.read_text(encoding="utf-8"):
            p.write_text(p.read_text(encoding="utf-8").rstrip() + extra, encoding="utf-8")
            print("appended         ", rel)
    print("Next: py -m pytest -q")
    return 0


if __name__ == "__main__":
    sys.exit(main())
