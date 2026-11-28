"""Motion capture for the jointed stick figure (ANIMATION, step c): a text-to-motion model (MoMask) gives a 3D
skeleton for a FIXED prompt such as "A person points forward with the right arm."; this module turns the joints
into the 2D `stickman.Pose` the figure already draws.

Why FIXED prompts: the director (modules/ai/director.py) only chooses an ACTION per beat. Each action has one
English prompt in ACTION_PROMPTS, so the narration never leaves the computer for this step and a clip is made once
per action and cached (not once per scene).

Input skeleton = HumanML3D, 22 joints, y up, the person faces +z, metres, 20 fps (what MoMask's gen_t2m.py saves
as joints .npy). Retargeting is by ANGLES, so the proportions of our figure do not matter:
    limb angle = atan2(z + 0.7 |x|, -y)   0 = straight down, +90 = towards the facing side, 180 = straight up
(the figure is drawn in profile, so a sideways arm raise is counted as "forward" instead of vanishing).
Front arm / front leg = the person's RIGHT side, back = LEFT. The elbow is the forearm angle minus the upper-arm
angle; the knee is thigh angle minus shin angle, never negative. dy lifts the figure only while the ankles are
off the ground; the figure does not travel (dx = 0).

Providers (all return an array (T, 22, 3)):
  LocalMoMask  runs gen_t2m.py of a local clone on the CPU            (NOT verified here: see the class)
  DirMocap     pictures-like folder: <action>.npy made elsewhere (Colab, a teammate's machine). Offline.
`MocapService.get` never raises: a failure gives None and the figure keeps its hand-coded action.
ASSUMPTIONS (not measured): PX_PER_M, the 0.7 sideways weight, smoothing window 5, ping-pong looping.
"""
from __future__ import annotations

import hashlib
import math
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional, Protocol, Sequence

import numpy as np

from modules.video.stickman import _NUMERIC, Pose, blend

FPS = 20.0
PX_PER_M = 122.0                  # our leg is 110 px; a HumanML3D pelvis-to-ankle is about 0.9 m
SIDE_W = 0.7
SMOOTH = 5
MAX_FAILS_IN_A_ROW = 2

J = dict(pelvis=0, l_hip=1, r_hip=2, spine1=3, l_knee=4, r_knee=5, spine2=6, l_ankle=7, r_ankle=8, spine3=9,
         l_foot=10, r_foot=11, neck=12, l_collar=13, r_collar=14, head=15, l_sho=16, r_sho=17, l_elb=18, r_elb=19,
         l_wri=20, r_wri=21)

# One prompt per director action. Gestures use the RIGHT arm because the right side is the figure's front arm.
ACTION_PROMPTS = {
    "talk": "A person explains something, moving both hands while talking.",
    "wave": "A person waves with the right hand.",
    "point": "A person points forward with the right arm.",
    "think": "A person puts the right hand on the chin and thinks.",
    "idea": "A person raises the right index finger in the air and jumps a little.",
    "shrug": "A person shrugs both shoulders and spreads both hands.",
    "surprised": "A person steps back with both hands raised in surprise.",
    "nod": "A person nods the head slowly.",
    "cheer": "A person raises both arms and cheers.",
    "jump": "A person jumps in the air.",
    "idle": "A person stands still and breathes.",
}


class MocapError(RuntimeError):
    pass


def _angle(v: np.ndarray) -> np.ndarray:
    """(T,3) -> degrees in (-100, 260]: 0 down, +90 towards the facing side, 180 up."""
    a = np.degrees(np.arctan2(v[:, 2] + SIDE_W * np.abs(v[:, 0]), -v[:, 1]))
    return np.where(a <= -100.0, a + 360.0, a)


def _check(joints: np.ndarray) -> np.ndarray:
    j = np.asarray(joints, dtype=np.float32)
    if j.ndim == 4 and j.shape[0] == 1:
        j = j[0]
    if j.ndim != 3 or j.shape[1:] != (22, 3) or j.shape[0] < 2 or not np.isfinite(j).all():
        raise MocapError(f"expected joints of shape (T, 22, 3) with T >= 2, got {getattr(j, 'shape', None)}")
    return j


def retarget(joints: np.ndarray) -> np.ndarray:
    """(T,22,3) HumanML3D joints -> (T, len(_NUMERIC)) pose values, in the order of stickman._NUMERIC."""
    j = _check(joints)
    P = lambda name: j[:, J[name]]
    cols = {n: np.zeros(len(j)) for n in _NUMERIC}
    for side, key in (("r", "f"), ("l", "b")):
        up, fore = P(f"{side}_elb") - P(f"{side}_sho"), P(f"{side}_wri") - P(f"{side}_elb")
        a_up, a_fore = _angle(up), _angle(fore)
        thigh, shin = P(f"{side}_knee") - P(f"{side}_hip"), P(f"{side}_ankle") - P(f"{side}_knee")
        a_th, a_sh = _angle(thigh), _angle(shin)
        cols[f"sh_{key}"], cols[f"el_{key}"] = a_up, a_fore - a_up
        cols[f"hip_{key}"], cols[f"kn_{key}"] = a_th, np.maximum(0.0, a_th - a_sh)
    torso = P("neck") - P("pelvis")
    lean = np.degrees(np.arctan2(torso[:, 2], torso[:, 1]))
    head_v = P("head") - P("neck")
    head = np.degrees(np.arctan2(head_v[:, 2], head_v[:, 1])) - lean
    cols["lean"], cols["head"] = np.clip(lean, -40, 40), np.clip(0.5 * head, -30, 30)
    cols["sh_f"] = cols["sh_f"] - cols["lean"]                 # the rig adds the lean to every arm angle
    cols["sh_b"] = cols["sh_b"] - cols["lean"]
    ankle_y = np.minimum(P("l_ankle")[:, 1], P("r_ankle")[:, 1])
    air = ankle_y - ankle_y.min()                              # the lowest the ankles ever get is "the ground"
    cols["dy"] = -np.clip(np.where(air > 0.03, air, 0.0) * PX_PER_M, 0.0, 120.0)
    arr = np.stack([cols[n] for n in _NUMERIC], axis=1)
    if SMOOTH > 1 and len(arr) >= SMOOTH:
        pad = SMOOTH // 2
        ext = np.pad(arr, ((pad, pad), (0, 0)), mode="edge")
        arr = np.stack([np.convolve(ext[:, c], np.ones(SMOOTH) / SMOOTH, mode="valid") for c in range(arr.shape[1])], axis=1)
    return arr


@dataclass
class MocapClip:
    name: str
    values: np.ndarray                      # (T, len(_NUMERIC))
    fps: float = FPS
    expr: str = "neutral"

    @property
    def duration(self) -> float:
        return (len(self.values) - 1) / self.fps

    def pose_at(self, t: float) -> Pose:
        """Pose t seconds after the clip starts. Longer beats play the clip back and forth (ping-pong)."""
        d = self.duration
        t = max(0.0, t)
        if t > d:
            k = t / d
            t = d * (k % 1.0 if int(k) % 2 == 0 else 1.0 - k % 1.0)
        f = t * self.fps
        i = min(int(f), len(self.values) - 2)
        a, b = (Pose(**dict(zip(_NUMERIC, row)), expr=self.expr) for row in self.values[i:i + 2])
        return blend(a, b, f - i)


def clip_from_joints(name: str, joints: np.ndarray, expr: str = "neutral") -> MocapClip:
    return MocapClip(name, retarget(joints), FPS, expr)


# ------------------------------------------------------------------ providers
class MocapProvider(Protocol):
    name: str
    online: bool

    def fetch(self, key: str, prompt: str) -> Optional[np.ndarray]: ...


class DirMocap:
    """Offline: joints made elsewhere and saved as <action>.npy in a folder (None when the file is not there)."""
    name, online = "mocap-folder", False

    def __init__(self, folder: Path):
        self.folder = Path(folder)

    def fetch(self, key: str, prompt: str) -> Optional[np.ndarray]:
        p = self.folder / f"{key}.npy"
        return np.load(p) if p.is_file() else None


class LocalMoMask:
    """Runs gen_t2m.py of a local clone of https://github.com/EricGuo5513/momask-codes on the CPU.

    NOT VERIFIED: written from the project's README (`--gpu_id -1 --ext <name> --text_prompt "..."`, joints saved
    as .npy under generation/<ext>/). Checkpoints must already be downloaded (prepare/download_models.sh). If a flag
    or the output folder differs in your clone, the error says what was found; adjust ARGS / the glob below."""
    name, online = "momask-local", False
    ARGS = ("--gpu_id", "-1")

    def __init__(self, repo: Path, python: str = sys.executable, timeout_s: float = 600.0):
        self.repo, self.python, self.timeout = Path(repo), python, timeout_s
        if not (self.repo / "gen_t2m.py").is_file():
            raise MocapError(f"{self.repo} has no gen_t2m.py (clone momask-codes and download its checkpoints)")

    def fetch(self, key: str, prompt: str) -> Optional[np.ndarray]:
        ext = f"sf_{key}"
        out_dir = self.repo / "generation" / ext
        for old in out_dir.rglob("*.npy") if out_dir.exists() else []:
            old.unlink()
        cmd = [self.python, "gen_t2m.py", *self.ARGS, "--ext", ext, "--text_prompt", prompt]
        try:
            proc = subprocess.run(cmd, cwd=self.repo, capture_output=True, text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            raise MocapError(f"gen_t2m.py did not finish within {self.timeout:g} s") from None
        found = sorted(out_dir.rglob("*.npy")) if out_dir.exists() else []
        if proc.returncode != 0 or not found:
            raise MocapError(f"gen_t2m.py gave no joints (exit {proc.returncode}): {(proc.stderr or proc.stdout)[-300:].strip()}")
        return np.load(found[0])


# ------------------------------------------------------------------ service
class MocapService:
    """`get(action)` -> MocapClip or None. Disk cache by prompt, circuit breaker after two failures in a row. Never raises."""

    def __init__(self, provider: MocapProvider, cache_dir: Path, prompts: Mapping[str, str] = ACTION_PROMPTS):
        self.provider, self.cache_dir, self.prompts = provider, Path(cache_dir), prompts
        self.used: dict[str, str] = {}
        self.errors: list[str] = []
        self._fails = 0

    def _path(self, prompt: str) -> Path:
        return self.cache_dir / (hashlib.sha1(f"{self.provider.name}|{prompt}".encode()).hexdigest()[:16] + ".npy")

    def get(self, action: str) -> Optional[MocapClip]:
        prompt = self.prompts.get(action)
        if prompt is None:
            return None
        cached = self._path(prompt)
        try:
            if cached.is_file():
                joints, src = np.load(cached), "cache"
            else:
                if self._fails >= MAX_FAILS_IN_A_ROW:
                    self.errors.append(f"{action}: skipped (provider failed twice in a row)")
                    return None
                joints = self.provider.fetch(action, prompt)
                if joints is None:
                    self.errors.append(f"{action}: no motion available")
                    return None
                joints, src = _check(joints), self.provider.name
            clip = clip_from_joints(action, joints)
        except Exception as exc:                       # provider, file or shape problems must never stop the video
            self._fails += 1
            self.errors.append(f"{action}: {exc}")
            return None
        self._fails = 0
        if src != "cache":
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            np.save(cached, joints)
        self.used[action] = src
        return clip

    def clips_for(self, actions: Sequence[str]) -> dict:
        """Clips for the distinct actions (in the order first needed); actions without a clip are simply absent."""
        out = {}
        for a in dict.fromkeys(actions):
            c = self.get(a)
            if c is not None:
                out[a] = c
        return out

    def summary(self) -> dict:
        return {"provider": self.provider.name, "online": self.provider.online, "clips": dict(self.used), "errors": list(self.errors)}
