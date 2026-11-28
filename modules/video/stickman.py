"""Jointed stick figure for the ANIMATION format: a 2D skeleton, a library of actions and lip-sync.

The older cut-out figure (`animation.character_layers(..., rig="cutout")`) is four rigid sprites: the legs never
move and each arm is one stiff piece. This module draws a figure with real joints, every frame:

  skeleton   hip (root) -> torso -> neck -> head; shoulder -> elbow -> hand; hip -> knee -> foot.
             Angles are in degrees measured from "hanging straight down", positive = towards the side the figure
             faces (s = +1 faces right, s = -1 faces left). forearm angle = shoulder + elbow, shin angle = hip - knee.
             The lowest foot always stands on the ground line, so bending the knees really crouches the figure.
  Pose       one set of joint angles + root offset + face (expression, where the eyes look)
  ACTIONS    action name -> function (t, dur, energy, ctx) -> Pose. t is seconds since the action started.
             idle, talk, walk, run, wave, point, think, idea, shrug, cheer, jump, surprised, nod
  Beat       one step of the choreography: (action, t0, t1) in seconds, plus where the figure walks to.
             `choreograph` turns the Motion Planner's pose (wave / point / think / shrug) and the scene role into
             beats; `script=` lets a caller (later: an AI director) give the beats directly.
             Between two beats the poses are blended for BLEND_S seconds, so there are no jumps.
  lip-sync   the mouth opens and closes once per syllable while a word is spoken (word times from
             visual_engine.sync, the same timing the objects use) and stays closed in the pauses.
  blink      every 2.6-4.4 s (deterministic: the same scene gives the same frames).

`StickmanLayer` is a `Layer` with a `paint(img, u, t, dur)` method; `LayerRenderer` calls it instead of pasting a
sprite. Everything is drawn by code with Pillow: no network, no GPU, no AI picture.

ASSUMPTIONS (our own choices, not measured): proportions, stride length, syllable count by vowel groups,
blend time, blink interval.
"""
from __future__ import annotations

import math
import re
import zlib
from dataclasses import dataclass, field, fields, replace
from typing import Callable, Optional, Sequence

from PIL import Image, ImageDraw

from modules.video.animation import INK, WHITE, Layer, Stage, hold, smooth

SS = 2                                  # supersampling of the figure canvas
THIGH, SHIN = 56.0, 54.0                # leg = 110 px (the cut-out figure's hip was 106 px above the ground)
TORSO, NECK_HEAD, HEAD_R = 98.0, 34.0, 30.0
SHOULDER_DROP = 10.0                    # shoulders sit this far below the neck, along the torso
UPPER_ARM, FOREARM = 50.0, 46.0
LINE_W, HAND_R = 9.0, 7.0
BLEND_S = 0.28                          # pose blend between two beats
WALK_IN_PX = 260.0                      # the figure walks in from this far off its spot (the cut-out figure slid 260 px)
WALK_SPEED = 210.0                      # px per second while walking in (1.24 s for WALK_IN_PX)
STRIDE_PX = 4 * (THIGH + SHIN) * math.sin(math.radians(26))   # ground covered by one full walk cycle (two steps)

EXPRESSIONS = ("neutral", "happy", "think", "worried", "surprised")


# ------------------------------------------------------------------ pose
@dataclass(frozen=True)
class Pose:
    lean: float = 0.0                   # torso, + = leans towards the facing side
    head: float = 0.0                   # head tilt relative to the torso
    sh_f: float = 10.0                  # front arm (the arm on the facing side): shoulder, elbow
    el_f: float = 8.0
    sh_b: float = -10.0                 # back arm
    el_b: float = -8.0
    hip_f: float = 11.0                 # legs: hip angle, knee bend (>= 0)
    kn_f: float = 0.0
    hip_b: float = -11.0
    kn_b: float = 0.0
    dx: float = 0.0                     # root offset (px); dy < 0 = in the air
    dy: float = 0.0
    expr: str = "neutral"
    look: float = 0.0                   # eyes: -1 look down .. +1 look up


_NUMERIC = tuple(f.name for f in fields(Pose) if f.name != "expr")


def blend(a: Pose, b: Pose, w: float) -> Pose:
    """a -> b with weight w in [0, 1] (the expression switches half way)."""
    w = min(1.0, max(0.0, w))
    vals = {n: getattr(a, n) + (getattr(b, n) - getattr(a, n)) * w for n in _NUMERIC}
    return Pose(**vals, expr=b.expr if w >= 0.5 else a.expr)


def _dir(angle: float, s: int) -> tuple[float, float]:
    """Unit vector of a limb: 0 = straight down, +90 = towards the facing side, 180 = straight up."""
    r = math.radians(angle)
    return s * math.sin(r), math.cos(r)


def joints(pose: Pose, x: float, gy: float, s: int) -> dict[str, tuple[float, float]]:
    """Screen positions of every joint. The lowest foot stands on the ground (gy) unless dy lifts the figure."""
    legs = {}
    for side, hip_a, kn in (("f", pose.hip_f, pose.kn_f), ("b", pose.hip_b, pose.kn_b)):
        kx, ky = _dir(hip_a, s)
        fx, fy = _dir(hip_a - kn, s)
        legs[side] = ((kx * THIGH, ky * THIGH), (kx * THIGH + fx * SHIN, ky * THIGH + fy * SHIN))
    drop = max(legs["f"][1][1], legs["b"][1][1])             # how far the lowest foot is below the hip
    hip = (x + pose.dx, gy - drop + pose.dy)
    tx, ty = s * math.sin(math.radians(pose.lean)), -math.cos(math.radians(pose.lean))
    neck = (hip[0] + tx * TORSO, hip[1] + ty * TORSO)
    ha = math.radians(pose.lean + pose.head)
    head = (neck[0] + s * math.sin(ha) * NECK_HEAD, neck[1] - math.cos(ha) * NECK_HEAD)
    sh = (neck[0] - tx * SHOULDER_DROP, neck[1] - ty * SHOULDER_DROP)
    out = {"hip": hip, "neck": neck, "head": head, "shoulder": sh}
    for side, (knee, foot) in legs.items():
        out[f"knee_{side}"] = (hip[0] + knee[0], hip[1] + knee[1])
        out[f"foot_{side}"] = (hip[0] + foot[0], hip[1] + foot[1])
    for side, sa, ea in (("f", pose.sh_f, pose.el_f), ("b", pose.sh_b, pose.el_b)):
        ux, uy = _dir(sa + pose.lean, s)
        fx, fy = _dir(sa + ea + pose.lean, s)
        elbow = (sh[0] + ux * UPPER_ARM, sh[1] + uy * UPPER_ARM)
        out[f"elbow_{side}"] = elbow
        out[f"hand_{side}"] = (elbow[0] + fx * FOREARM, elbow[1] + fy * FOREARM)
    return out


# ------------------------------------------------------------------ actions
@dataclass(frozen=True)
class Ctx:
    """What an action may need besides time: the walk phase (radians), and lip-sync / talk beats."""
    phase: float = 0.0
    talking: float = 0.0                # 0..1, how much the narrator is speaking right now


def _osc(t: float, hz: float, amp: float, off: float = 0.0) -> float:
    return amp * math.sin(2 * math.pi * hz * t + off)


def act_idle(t, dur, e, c):
    return Pose(lean=_osc(t, 0.25, 1.2), head=_osc(t, 0.18, 2.0, 1.0), sh_f=10 + _osc(t, 0.25, 2.0),
                sh_b=-10 - _osc(t, 0.25, 2.0), dy=_osc(t, 0.5, 1.2))


def act_talk(t, dur, e, c):
    """Explaining: alternating palm-up gestures, bigger while the narrator is speaking."""
    k = (0.45 + 0.55 * c.talking) * e
    g1 = max(0.0, math.sin(2 * math.pi * 0.55 * t))
    g2 = max(0.0, math.sin(2 * math.pi * 0.55 * t + math.pi))
    return Pose(lean=2 + _osc(t, 0.55, 2.0 * k), head=_osc(t, 1.1, 3.0 * k),
                sh_f=18 + 30 * k * g1, el_f=20 + 55 * k * g1,
                sh_b=-14 - 18 * k * g2, el_b=-15 - 50 * k * g2, dy=_osc(t, 1.1, 1.5 * k))


def _walk_pose(phase: float, amp: float, lean: float, arm: float, elbow: float, bounce: float) -> Pose:
    sw = math.sin(phase)
    knee_f = max(0.0, math.sin(phase + math.pi / 2)) * amp * 1.5   # the leg that swings forward lifts its knee
    knee_b = max(0.0, math.sin(phase - math.pi / 2)) * amp * 1.5
    return Pose(lean=lean, head=-lean * 0.5, hip_f=amp * sw, kn_f=knee_f, hip_b=-amp * sw, kn_b=knee_b,
                sh_f=-arm * sw, el_f=elbow, sh_b=arm * sw, el_b=elbow,
                dy=-bounce * abs(math.cos(phase)))


def act_walk(t, dur, e, c):
    return _walk_pose(c.phase, 26.0, 4.0, 24.0 * e, 18.0, 4.0)


def act_run(t, dur, e, c):
    return _walk_pose(c.phase, 40.0, 14.0, 50.0 * e, 85.0, 9.0)


def act_wave(t, dur, e, c):
    up = smooth(min(1.0, t / 0.35))
    swing = _osc(t, 1.6, 24.0 * e) * up
    return Pose(expr="happy", lean=-2 * up, head=-6 * up + _osc(t, 0.8, 2.0),       # head tilts away from the hand
                sh_f=10 + 108 * up, el_f=8 + (40 + swing) * up, dy=_osc(t, 0.8, 1.5))


def act_point(t, dur, e, c):
    up = smooth(min(1.0, t / 0.3))
    return Pose(lean=5 * up, head=-4 * up, sh_f=10 + 76 * up + _osc(t, 1.0, 3.0 * e) * up, el_f=8 - 6 * up,
                sh_b=-10 - 6 * up, el_b=-20 * up, hip_f=11 + 4 * up, dy=_osc(t, 0.7, 1.0))


def act_think(t, dur, e, c):
    up = smooth(min(1.0, t / 0.45))
    return Pose(expr="think", look=0.8 * up, lean=-3 * up, head=12 * up + _osc(t, 0.4, 3.0) * up,
                sh_f=10 + 30 * up, el_f=8 + 142 * up + _osc(t, 1.5, 5.0) * up,      # hand to the chin, tapping
                sh_b=-10 + 26 * up, el_b=-8 + 98 * up)                                # other arm across the belly


def act_idea(t, dur, e, c):
    """'Got it!': a small hop and one finger up."""
    up = smooth(min(1.0, t / 0.25))
    hop = max(0.0, math.sin(math.pi * min(1.0, t / 0.45))) * 14 * e
    return Pose(expr="happy", look=0.5 * up, head=-8 * up, sh_f=10 + 112 * up, el_f=8 + 42 * up,
                sh_b=-10 - 10 * up, dy=-hop)


def act_shrug(t, dur, e, c):
    up = smooth(min(1.0, t / 0.35))
    bob = _osc(t, 1.4, 4.0 * e) * up
    return Pose(expr="worried", head=14 * up, sh_f=10 + 32 * up + bob, el_f=8 + 92 * up,
                sh_b=-10 - 32 * up - bob, el_b=-8 - 92 * up, dy=-3 * up)


def act_cheer(t, dur, e, c):
    up = smooth(min(1.0, t / 0.3))
    hop = abs(math.sin(math.pi * 1.6 * t)) * 16 * e * up
    knee = (1 - abs(math.sin(math.pi * 1.6 * t))) * 20 * up
    return Pose(expr="happy", look=0.4, head=_osc(t, 1.6, 4.0), sh_f=10 + 125 * up + _osc(t, 3.2, 8.0),
                el_f=8 + 12 * up, sh_b=-10 - 125 * up - _osc(t, 3.2, 8.0), el_b=-8 - 12 * up,       # a V of both arms
                kn_f=knee, kn_b=knee, hip_f=11 + knee * 0.6, hip_b=-11 - knee * 0.6, dy=-hop)


def act_jump(t, dur, e, c):
    """Crouch, jump, land (one jump per 1.1 s)."""
    p = (t % 1.1) / 1.1
    if p < 0.3:                                               # crouch
        k = smooth(p / 0.3)
        return Pose(lean=8 * k, sh_f=10 - 30 * k, sh_b=-10 - 30 * k, hip_f=11 + 40 * k, kn_f=70 * k,
                    hip_b=-11 + 30 * k, kn_b=60 * k)
    if p < 0.8:                                               # in the air
        k = math.sin(math.pi * (p - 0.3) / 0.5)
        return Pose(expr="happy", sh_f=130, el_f=10, sh_b=-130, el_b=-10, hip_f=20, kn_f=30, hip_b=-5, kn_b=40,
                    dy=-70 * e * k)
    k = 1 - smooth((p - 0.8) / 0.2)                           # land
    return Pose(lean=5 * k, hip_f=11 + 25 * k, kn_f=45 * k, hip_b=-11 + 20 * k, kn_b=40 * k)


def act_surprised(t, dur, e, c):
    up = smooth(min(1.0, t / 0.18))
    return Pose(expr="surprised", look=0.3, lean=-9 * up, head=-6 * up, sh_f=10 + 70 * up, el_f=8 + 60 * up,
                sh_b=-10 - 70 * up, el_b=-8 - 60 * up, dy=-8 * up * max(0.0, 1 - t / 0.5) + _osc(t, 6.0, 1.5) * up)


def act_nod(t, dur, e, c):
    return Pose(expr="happy", head=-8 - _osc(t, 1.8, 9.0 * e), sh_f=12, el_f=18, sh_b=-12, el_b=-18)


ACTIONS: dict[str, Callable[[float, float, float, Ctx], Pose]] = {
    "idle": act_idle, "talk": act_talk, "walk": act_walk, "run": act_run, "wave": act_wave, "point": act_point,
    "think": act_think, "idea": act_idea, "shrug": act_shrug, "cheer": act_cheer, "jump": act_jump,
    "surprised": act_surprised, "nod": act_nod,
}
MOVING = frozenset({"walk", "run"})                          # actions that carry the figure along the ground


# ------------------------------------------------------------------ choreography
@dataclass(frozen=True)
class Beat:
    action: str
    t0: float
    t1: float
    x_to: Optional[float] = None        # walk / run: where the figure arrives (absolute x); None = stays

    def __post_init__(self):
        if self.action not in ACTIONS:
            raise ValueError(f"unknown action {self.action!r}; known: {', '.join(ACTIONS)}")
        if self.t1 <= self.t0:
            raise ValueError(f"beat {self.action!r} must end after it starts ({self.t0} .. {self.t1})")


MAIN_ACTION = {"wave": "wave", "point": "point", "think": "think", "shrug": "shrug"}


def choreograph(pose: str, dur: float, fx: float, s: int, role: str = "body", energy: float = 1.0) -> list[Beat]:
    """Default beats for a Motion Planner pose. Times in seconds; the whole scene [0, dur] is covered.

      walk in  from WALK_IN_PX off its spot at WALK_SPEED (1.24 s; at most 40 % of a very short scene)
      main     the pose itself (wave / point / think -> idea / shrug), 1.6-2.6 s
      talk     explaining gestures for the rest, the summary scene ends with a cheer (lively) or a nod
    """
    if pose not in MAIN_ACTION:
        raise ValueError(f"unknown pose {pose!r}")
    dur = max(float(dur), 0.5)
    walk = min(WALK_IN_PX / WALK_SPEED, 0.4 * dur)            # same walking speed in every scene
    beats = [Beat("walk", 0.0, walk, x_to=fx)]
    t = walk
    main = min(2.6 if pose == "think" else 2.0, max(0.6, 0.3 * dur))
    if pose == "think" and dur - t > main + 1.2:
        beats += [Beat("think", t, t + main), Beat("idea", t + main, t + main + 0.9)]
        t += main + 0.9
    else:
        beats.append(Beat(MAIN_ACTION[pose], t, min(dur, t + main)))
        t = min(dur, t + main)
    end_beat = None
    if role == "summary" and dur - t > 2.0:
        end_beat = "cheer" if energy >= 1.2 else "nod"
    rest_end = dur - 1.4 if end_beat else dur
    if pose == "point" and rest_end - t > 3.0:                # point again at the prop half way through the talk
        mid = t + (rest_end - t) / 2
        beats += [Beat("talk", t, mid - 0.6), Beat("point", mid - 0.6, mid + 0.8)]
        t = mid + 0.8
    if rest_end - t > 0.05:
        beats.append(Beat("talk", t, rest_end))
        t = rest_end
    if end_beat:
        beats.append(Beat(end_beat, t, dur))
    return beats


MIN_BEAT_S = 0.7                        # a directed gesture lasts at least this long
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
_VOWELS = re.compile(r"[aeiouyàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]+",
                     re.IGNORECASE)


def syllables(word: str) -> int:
    """Rough syllable count: groups of vowels (Vietnamese words are one syllable each: one group)."""
    return max(1, len(_VOWELS.findall(word)))


def speech_spans(narration: str, audio_s: float) -> list[tuple[float, float, int]]:
    """[(start, end, syllables)] of the SPOKEN part of every word (the pause after punctuation is cut off)."""
    from modules.visual_engine import sync
    spans = []
    for w, a, b in sync.word_times(narration or "", max(0.0, audio_s)):
        core = w.strip(".,;:!?…\"'()[]")
        wt = 1.0 + 0.45 * len(core)
        pause = sync.PAUSE_SOFT if w[-1:] in ",;:" else sync.PAUSE_HARD if w[-1:] in ".?!…" else 0.0
        spoken = (b - a) * wt / (wt + pause)
        spans.append((a, a + spoken * 0.92, syllables(core)))
    return spans


def mouth_open(spans: Sequence[tuple[float, float, int]], t: float) -> float:
    """0 (closed) .. 1 (wide open) at time t: one open-close per syllable inside a word, closed in pauses."""
    for a, b, n in spans:
        if a <= t < b:
            return abs(math.sin(math.pi * n * (t - a) / (b - a)))
        if a > t:
            break
    return 0.0


def talking(spans: Sequence[tuple[float, float, int]], t: float, window: float = 0.35) -> float:
    """1 while words are being spoken around t, fading to 0 in long pauses (drives the talk gestures)."""
    best = 0.0
    for a, b, _ in spans:
        if a - window <= t <= b + window:
            d = 0.0 if a <= t <= b else min(abs(t - a), abs(t - b))
            best = max(best, 1.0 - d / window)
        elif a > t + window:
            break
    return best


def blinking(t: float, seed: int) -> bool:
    """Eyes shut for 0.12 s at deterministic moments 2.6-4.4 s apart."""
    k, start = 0, 0.8 + (seed % 7) * 0.2
    while start <= t:
        if t < start + 0.12:
            return True
        k += 1
        start += 2.6 + ((seed * 31 + k * 17) % 19) / 10.0
    return False


# ------------------------------------------------------------------ the figure as a layer
@dataclass
class StickmanLayer(Layer):
    """A jointed figure. `paint` draws it straight onto the frame; the sprite field is not used."""
    stage: Optional[Stage] = None
    pose_name: str = "point"
    role: str = "body"
    narration: str = ""
    audio_s: Optional[float] = None
    script: Optional[Sequence[Beat]] = None
    directions: Optional[Sequence[tuple]] = None     # [(action, from_word)] chosen by the AI director (modules/ai/director.py)
    seed: int = 0
    color: tuple = INK
    _cache: dict = field(default_factory=dict, repr=False)

    # ---- timing
    def beats(self, dur: float) -> list[Beat]:
        key = ("beats", round(dur, 3), round(self.audio_s or 0.0, 3))
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
        return self._cache[key]

    def spans(self, dur: float) -> list[tuple[float, float, int]]:
        audio = min(self.audio_s, dur) if self.audio_s else dur * 0.92
        key = ("spans", round(audio, 3))
        if key not in self._cache:
            self._cache[key] = speech_spans(self.narration, audio)
        return self._cache[key]

    def _x_and_phase(self, beats: list[Beat], t: float) -> tuple[float, float]:
        """Where the figure stands at t, and the walk phase (from the distance walked, so feet do not slide much)."""
        st = self.stage
        first_move = next((b for b in beats if b.action in MOVING and b.x_to is not None), None)
        x = (first_move.x_to - WALK_IN_PX * st.s) if first_move and first_move.t0 <= 0.0 else float(st.fx)
        walked = 0.0
        for b in beats:
            if b.t0 > t:
                break
            if b.action in MOVING and b.x_to is not None:
                f = min(1.0, (t - b.t0) / (b.t1 - b.t0))
                k = smooth(f) * 0.6 + f * 0.4                  # ease in/out, but not to a dead stop
                nx = x + (b.x_to - x) * k
                walked += abs(nx - x)
                x = nx if f < 1.0 else b.x_to
        return x, 2 * math.pi * walked / STRIDE_PX

    def pose_at(self, t: float, dur: float) -> tuple[Pose, float]:
        """(pose, x) at time t."""
        beats = self.beats(dur)
        x, phase = self._x_and_phase(beats, t)
        st = self.stage
        ctx = Ctx(phase=phase, talking=talking(self.spans(dur), t))
        i = 0
        for j, b in enumerate(beats):
            if b.t0 <= t:
                i = j
        b = beats[i]
        cur = ACTIONS[b.action](max(0.0, t - b.t0), b.t1 - b.t0, st.energy, ctx)
        if i > 0 and t - b.t0 < BLEND_S:
            p = beats[i - 1]
            prev = ACTIONS[p.action](t - p.t0, p.t1 - p.t0, st.energy, ctx)
            cur = blend(prev, cur, smooth((t - b.t0) / BLEND_S))
        return cur, x

    # ---- drawing
    def paint(self, img: Image.Image, u: float, t: float, dur: float) -> None:
        a = self.alpha(u)
        if a <= 0.01:
            return
        st = self.stage
        pose, x = self.pose_at(t, dur)
        gy = self.y(u) if self.y is not None else st.gy
        j = joints(pose, x, gy, st.s)
        pts = list(j.values())
        m = HEAD_R + LINE_W + 4
        x0, y0 = int(min(p[0] for p in pts) - m), int(min(p[1] for p in pts) - m)
        x1, y1 = int(max(p[0] for p in pts) + m), int(max(p[1] for p in pts) + m)
        w, h = x1 - x0, y1 - y0
        canvas = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
        d = ImageDraw.Draw(canvas)
        k = SS
        P = {n: ((p[0] - x0) * k, (p[1] - y0) * k) for n, p in j.items()}
        lw = int(LINE_W * k)

        def seg(*names):
            for p0, p1 in zip(names, names[1:]):
                d.line([P[p0], P[p1]], fill=self.color, width=lw)
            for n in names:
                r = lw / 2
                d.ellipse((P[n][0] - r, P[n][1] - r, P[n][0] + r, P[n][1] + r), fill=self.color)

        def hand(n):
            r = HAND_R * k
            d.ellipse((P[n][0] - r, P[n][1] - r, P[n][0] + r, P[n][1] + r), fill=WHITE, outline=self.color,
                      width=int(4.5 * k))

        seg("shoulder", "elbow_b", "hand_b")                  # back arm behind the body
        hand("hand_b")
        seg("hip", "knee_b", "foot_b")
        seg("hip", "knee_f", "foot_f")
        seg("hip", "neck")
        self._head(d, P["head"], pose, k, t, dur)
        seg("shoulder", "elbow_f", "hand_f")                  # front arm in front of the body
        hand("hand_f")
        fig = canvas.resize((w, h), Image.LANCZOS)
        if a < 1.0:
            fig.putalpha(fig.getchannel("A").point(lambda v: int(v * a)))
        img.paste(fig, (x0, y0), fig)

    def _head(self, d: ImageDraw.ImageDraw, c, pose: Pose, k: float, t: float, dur: float) -> None:
        s = self.stage.s
        r = HEAD_R * k
        d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=WHITE, outline=self.color, width=int(6.5 * k))
        tilt = math.radians(-s * (pose.lean + pose.head))

        def at(px, py):                                       # a face point (1x units, head centre = 0) on the canvas
            px += 5 * s                                       # the face turns a little towards the facing side
            return (c[0] + (px * math.cos(tilt) - py * math.sin(tilt)) * k,
                    c[1] + (px * math.sin(tilt) + py * math.cos(tilt)) * k)

        ink, ex = self.color, pose.expr
        ey = -4 - 3 * pose.look
        if blinking(t, self.seed) and ex != "surprised":
            for sx in (-9, 9):
                d.line([at(sx - 4, ey), at(sx + 4, ey)], fill=ink, width=int(3 * k))
        else:
            er = (4.6 if ex == "surprised" else 3.4) * k
            for sx in (-9, 9):
                ec = at(sx, ey)
                d.ellipse((ec[0] - er, ec[1] - er, ec[0] + er, ec[1] + er), fill=ink)
        brows = {"worried": ((-13, -13, -5, -15), (5, -15, 13, -13)),
                 "think": ((-13, -14, -5, -14), (5, -18, 13, -16)),
                 "surprised": ((-13, -18, -5, -19), (5, -19, 13, -18))}.get(ex)
        if brows:
            for bx0, by0, bx1, by1 in brows:
                d.line([at(bx0, by0), at(bx1, by1)], fill=ink, width=int(3 * k))
        o = mouth_open(self.spans(dur), t)
        if ex == "surprised":
            o = max(o, 0.8)
        if o > 0.08:                                          # open mouth: dark oval, taller when wider open
            mh, mw = 2.0 + 8.0 * o, 6.5 + 2.0 * o
            p0, p1 = at(-mw, 10 - mh / 2), at(mw, 10 + mh / 2)
            cx, cy = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
            d.ellipse((cx - mw * k, cy - mh / 2 * k, cx + mw * k, cy + mh / 2 * k), fill=ink)
        elif ex in ("happy", "neutral"):
            depth = 7 if ex == "happy" else 4
            pts = [at(-8 + 16 * i / 8, 8 + depth * math.sin(math.pi * i / 8)) for i in range(9)]
            d.line(pts, fill=ink, width=int(3.2 * k), joint="curve")
        elif ex == "worried":
            pts = [at(-7 + 14 * i / 8, 12 - 3 * math.sin(math.pi * i / 8)) for i in range(9)]
            d.line(pts, fill=ink, width=int(3.2 * k), joint="curve")
        else:                                                 # think: a short flat line to one side
            d.line([at(-3, 11), at(7, 10)], fill=ink, width=int(3.2 * k))


def stickman_layer(stage: Stage, pose: str, *, role: str = "body", narration: str = "",
                   audio_s: Optional[float] = None, script: Optional[Sequence[Beat]] = None, seed: int = 0,
                   z: int = 3, directions: Optional[Sequence[tuple]] = None) -> StickmanLayer:
    """One jointed figure standing at stage.fx on stage.gy, facing stage.s."""
    if script is None and pose not in MAIN_ACTION:
        raise ValueError(f"unknown pose {pose!r}")
    blank = Image.new("RGBA", (2, 2), (0, 0, 0, 0))
    return StickmanLayer(name="stickman", sprite=blank, x=hold(stage.fx), y=hold(stage.gy), z=z, stage=stage,
                         pose_name=pose, role=role, narration=narration, audio_s=audio_s,
                         script=list(script) if script else None, directions=list(directions) if directions else None,
                         seed=seed if seed else zlib.crc32(f"{pose}|{narration}".encode()) % 1000)
