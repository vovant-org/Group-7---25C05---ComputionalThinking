"""The engine: topic profile + scene -> a drawn, moving, synchronised scene.

  select_objects   which objects explain THIS scene: the concepts its narration mentions (in order), topped up
                   from the domain pool, never the same set as the last two scenes (no repeated pictures)
  TopicScene       what `compose_topic_scene` returns. It has the interface that render.py and the report expect
                   from an animated scene (base, layers via make_renderer, plan, layout "cutout:<objects>").
                   Its layers are built when the real durations are known, so each object can appear at the
                   moment the narrator says its word (sync.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

from PIL import Image, ImageDraw

from core.models import Scene
from modules.video.animation import (GROUND_Y, AnimatedScene, Layer, LayerRenderer, Stage, character_layers)
from modules.video.composer import Style
from modules.video.motion_planner import MotionPlan, plan_motion
from modules.visual_engine import sync
from modules.visual_engine.kits import POOLS, draw_backdrop
from modules.visual_engine.objects import OBJECTS, Ctx
from modules.visual_engine.topic import CONCEPT_DOMAINS, TopicProfile, find_concepts, trend_of

MAX_OBJECTS = 3
MAX_OBJECTS_WITH_WIDE = 2
RECENT = 2                                       # a scene may not repeat the object set of the last RECENT scenes
STAGE_MARGIN = 100
RELAX_REPEAT = True                              # v3: when no fresh object exists, differing from the LAST scene is enough


@dataclass(frozen=True)
class Choice:
    key: str
    word_index: Optional[int]                    # first word of the narration that mentions it (None: filler)


def _wide(keys) -> bool:
    return any(OBJECTS[k].wide for k in keys)


def _normalise(found: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """Planets bring their own sun; Earth next to 'planet' is the same system."""
    keys = {k for k, _ in found}
    drop = set()
    if keys & {"planet", "earth"}:
        drop.add("sun")
    if {"planet", "earth"} <= keys:
        drop.add("planet")
    return [(k, i) for k, i in found if k not in drop]


def select_objects(narration: str, claim_text: str, profile: TopicProfile, index: int, explain_pattern: str,
                   recent: Sequence[tuple]) -> list[Choice]:
    found = _normalise(find_concepts(narration or claim_text, profile.vietnamese))
    if not found and claim_text and claim_text != narration:
        found = [(k, None) for k, _ in _normalise(find_concepts(claim_text, profile.vietnamese))]
    # concepts of the video's domain win: two of them are enough, so a stray "rises" cannot add a chart to a sleep scene
    indomain = [h for h in found if profile.domain in CONCEPT_DOMAINS[h[0]]]
    if profile.domain != "generic" and len(indomain) >= 2:
        found = indomain
    found.sort(key=lambda h: (profile.domain not in CONCEPT_DOMAINS[h[0]], 9999 if h[1] is None else h[1]))
    chosen = [Choice(k, i) for k, i in found if k in OBJECTS]
    cap = MAX_OBJECTS_WITH_WIDE if _wide([c.key for c in chosen[:MAX_OBJECTS]]) else MAX_OBJECTS
    chosen = sorted(chosen[:MAX_OBJECTS], key=lambda c: 9999 if c.word_index is None else c.word_index)
    while len(chosen) > cap:                                   # keep the wide object, drop the latest other one
        chosen.pop(max(range(len(chosen)), key=lambda i: (not OBJECTS[chosen[i].key].wide, i)))
    pool = [k for k in POOLS[profile.domain] if k in OBJECTS]
    keys = [c.key for c in chosen]
    want = 1 if _wide(keys) else 2
    if explain_pattern == "trend" and "bars_up" in pool and "bars_up" not in keys and len(chosen) < cap and not _wide(keys):
        chosen.append(Choice("bars_up", None))
    avoid = {k for sig in recent for k in sig}
    i = 0
    while len(chosen) < want and i < 2 * len(pool):             # top up from the domain pool, rotating with the scene index
        k = pool[(index * 2 + i) % len(pool)]
        i += 1
        if k in [c.key for c in chosen] or (k in avoid and i <= len(pool)) or (_wide([c.key for c in chosen] + [k]) and chosen):
            continue
        chosen.append(Choice(k, None))
    sig = tuple(sorted(c.key for c in chosen))
    if sig in recent:                                          # same picture as a recent scene: change it
        used = {c.key for c in chosen}
        for k in pool:
            if k in used or k in avoid or OBJECTS[k].wide:
                continue
            if len(chosen) == 1:                               # a lone wide object (a planet system): add a companion
                chosen.append(Choice(k, None))
            else:                                              # swap the last filler (or the last object)
                victim = max(range(len(chosen)), key=lambda j: (chosen[j].word_index is None, j))
                chosen[victim] = Choice(k, None)
            break
    if RELAX_REPEAT and recent and tuple(sorted(c.key for c in chosen)) == recent[-1]:
        used, last = {c.key for c in chosen}, set(recent[-1])
        for k in pool:                                         # every fresh object was used in the last two scenes
            if k in used or k in last or OBJECTS[k].wide:
                continue
            if len(chosen) == 1:
                chosen.append(Choice(k, None))
            else:
                victim = max(range(len(chosen)), key=lambda j: (chosen[j].word_index is None, j))
                chosen[victim] = Choice(k, None)
            break
    return chosen


def _variant(key: str, narration: str) -> str:
    low = narration.lower()
    return "elephant" if key == "animal" and ("elephant" in low or " voi " in f" {low} ") else ""


@dataclass
class TopicScene:
    """A scene of the ANIMATION format drawn by the topic-aware engine (same interface as AnimatedScene)."""
    scene_id: int
    plan: MotionPlan
    base: Image.Image
    claim_text: str
    narration: str
    domain: str
    choices: list[Choice]
    actor: bool
    mirror: bool
    accent: tuple
    accent2: tuple
    trend: int = 1
    vietnamese: bool = False
    layout: str = ""
    requested_layout: Optional[str] = None
    labels: list = field(default_factory=list)                 # nothing is drawn as text
    min_font_used: int = 0
    warnings: list[str] = field(default_factory=list)
    overflow: bool = False
    sync_log: list[dict] = field(default_factory=list)
    directions: Optional[list] = None                          # AI director: [(action, from_word)] for the figure
    _built: dict = field(default_factory=dict, repr=False)

    @property
    def objects(self) -> tuple[str, ...]:
        return tuple(c.key for c in self.choices)

    @property
    def signature(self) -> tuple:
        return tuple(sorted(self.objects))

    def region(self, st: Style) -> tuple[float, float]:
        w = st.size[0]
        if not self.actor:
            return STAGE_MARGIN, w - STAGE_MARGIN
        return (STAGE_MARGIN, w - 520) if self.mirror else (520, w - STAGE_MARGIN)

    def build_layers(self, duration_s: float, audio_s: float, st: Style) -> list[Layer]:
        key = (round(duration_s, 3), round(audio_s, 3))
        if key in self._built:
            return self._built[key]
        D = max(duration_s, 1e-6)
        times = sync.word_times(self.narration, min(audio_s, duration_s))
        x0, x1 = self.region(st)
        n = max(1, len(self.choices))
        slot_w = (x1 - x0) / n
        xs = [x0 + slot_w * (i + 0.5) for i in range(n)]
        layers: list[Layer] = []
        self.sync_log = []
        for i, ch in enumerate(self.choices):
            tm = sync.mention_time(times, ch.word_index)
            ta = sync.appear_time(tm, D, i)
            ctx = Ctx(x=xs[i], gy=GROUND_Y, u0=min(sync.LATEST, max(0.03, ta / D)), accent=self.accent, accent2=self.accent2,
                      energy=self.plan.energy, slot_w=slot_w, x0=x0, x1=x1, variant=_variant(ch.key, self.narration),
                      trend=self.trend, partners=tuple(x for j, x in enumerate(xs) if j != i),
                      rain=ch.key == "cloud" and self.domain == "weather")
            layers += OBJECTS[ch.key].build(ctx)
            self.sync_log.append({"object": ch.key, "mention_s": None if tm is None else round(tm, 3),
                                  "appear_s": round(ctx.u0 * D, 3), "word": None if ch.word_index is None else times[ch.word_index][0]})
        if self.actor:
            s = -1 if self.mirror else 1
            stage = Stage(fx=st.size[0] - 300 if self.mirror else 300, cx=(x0 + x1) / 2, s=s, gy=GROUND_Y,
                          accent=self.accent, accent2=self.accent2, energy=self.plan.energy)
            layers += character_layers(stage, self.plan.pose, role=self.plan.role, narration=self.narration,
                                       audio_s=min(audio_s, duration_s), directions=self.directions)
        layers.sort(key=lambda l: l.z)
        self._built[key] = layers
        return layers

    def make_renderer(self, duration_s: float, audio_s: float, index: int, st: Style) -> LayerRenderer:
        layers = self.build_layers(duration_s, audio_s, st)
        return LayerRenderer(AnimatedScene(scene_id=self.scene_id, plan=self.plan, base=self.base, layers=layers,
                                           claim_text=self.claim_text, layout=self.layout), duration_s, st)


def compose_topic_scene(scene: Scene, claim_text: str, profile: TopicProfile, st: Style = Style(), index: int = 0,
                        total: int = 1, recent: Sequence[tuple] = (), directions: Optional[list] = None) -> TopicScene:
    base_plan = plan_motion(scene, index, total)
    choices = select_objects(scene.narration, claim_text, profile, index, scene.explain_pattern, recent)
    actor = profile.actor
    plan = MotionPlan(scene_id=scene.scene_id, role=base_plan.role, pose=base_plan.pose if actor else "none",
                      prop="+".join(c.key for c in choices), energy=base_plan.energy, mirror=base_plan.mirror)
    accent, accent2 = st.accent(scene.facet), st.accent(scene.facet, 2)
    base = draw_backdrop(profile.domain, st, scene.facet, scene.scene_id, index, total, accent)
    if actor:
        d = ImageDraw.Draw(base, "RGBA")
        fx = st.size[0] - 300 if plan.mirror else 300
        d.ellipse((fx - 70, GROUND_Y - 2, fx + 70, GROUND_Y + 12), fill=(60, 60, 90, 80))
    trend = trend_of(scene.narration or claim_text) or profile.trend or 1
    return TopicScene(scene_id=scene.scene_id, plan=plan, base=base, claim_text=claim_text, narration=scene.narration,
                      domain=profile.domain, choices=choices, actor=actor, mirror=plan.mirror, accent=accent,
                      accent2=accent2, trend=trend, vietnamese=profile.vietnamese, layout=f"cutout:{plan.prop}",
                      requested_layout=scene.layout, directions=directions)


def compose_topic_scenes(scenes: Sequence[Scene], profile: TopicProfile, st: Style = Style(),
                         directions: Optional[dict] = None) -> dict[int, TopicScene]:
    """All scenes of a video, in order, so a scene can avoid repeating the pictures of the previous ones."""
    out: dict[int, TopicScene] = {}
    recent: list[tuple] = []
    total = len(scenes)
    for i, sc in enumerate(scenes):
        ts = compose_topic_scene(sc, sc.narration, profile, st, i, total, recent, (directions or {}).get(sc.scene_id))
        out[sc.scene_id] = ts
        recent = (recent + [ts.signature])[-RECENT:]
    return out
