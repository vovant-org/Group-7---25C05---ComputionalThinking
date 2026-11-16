"""Motion Planner for the ANIMATION format (report 5.9.10, option L2: multi-layer cut-out animation).

Decides, with fixed rules (no AI, so the same scene always gets the same motion), what the cut-out
character does in a scene and which prop is drawn next to it. The rules use only what the Scene
already knows: its position in the video, its explain_pattern and its importance.

  role     hook (first scene) | summary (last scene) | body (the rest)
  pose     wave for the hook; otherwise by explain_pattern (see POSE_BY_PATTERN)
  prop     what is drawn beside the character, by explain_pattern (see PROP_BY_PATTERN)
  energy   1.4 for the hook, the summary and scenes with importance >= 0.75; 1.0 otherwise. It scales
           the size of every movement, so the important scenes are the most lively
           (report 5.3: "scenes with high importance are prioritised for motion").
  mirror   the character stands on the right in odd scenes, so consecutive scenes do not look alike

The mapping explain_pattern -> prop is the animation counterpart of the layout lookup table of the
Scene Segmenter (report 5.2).
"""
from __future__ import annotations

from dataclasses import dataclass

from core.models import Scene

PROP_BY_PATTERN = {
    "cause_effect": "cause_effect",     # cause block -> arrow -> effect block
    "comparison": "bars",               # two bars of different height
    "step_by_step": "steps",            # stairs with a flag at the top
    "trend": "chart",                   # a line that rises step by step
    "analogy": "bulb",                  # light bulb (an idea)
}
POSE_BY_PATTERN = {
    "cause_effect": "point",
    "comparison": "shrug",
    "step_by_step": "point",
    "trend": "point",
    "analogy": "think",
}
DEFAULT_PROP, DEFAULT_POSE = "bubble", "point"
HIGH_IMPORTANCE = 0.75
ENERGY_HIGH, ENERGY_NORMAL = 1.4, 1.0

PROPS = ("cause_effect", "bars", "steps", "chart", "bulb", "bubble")
POSES = ("wave", "point", "think", "shrug")


@dataclass(frozen=True)
class MotionPlan:
    scene_id: int
    role: str
    pose: str
    prop: str
    energy: float
    mirror: bool


def plan_motion(scene: Scene, index: int, total: int) -> MotionPlan:
    """Motion of one scene. `index` is the position in the video (0-based), `total` the scene count."""
    if total < 1 or not 0 <= index < total:
        raise ValueError(f"index {index} is outside a video of {total} scenes")
    role = "hook" if index == 0 else "summary" if index == total - 1 else "body"
    pose = "wave" if role == "hook" else POSE_BY_PATTERN.get(scene.explain_pattern, DEFAULT_POSE)
    prop = PROP_BY_PATTERN.get(scene.explain_pattern, DEFAULT_PROP)
    lively = role != "body" or scene.importance >= HIGH_IMPORTANCE
    return MotionPlan(scene_id=scene.scene_id, role=role, pose=pose, prop=prop,
                      energy=ENERGY_HIGH if lively else ENERGY_NORMAL, mirror=index % 2 == 1)
