"""Core data models (Part 4 of the report: Scene, Render Mode, Format Profile)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RenderMode(str, Enum):
    STATIC = "STATIC"
    PAN = "PAN"
    REVEAL = "REVEAL"
    LAYERED = "LAYERED"
    CLIP = "CLIP"


# STATIC is the only mode without motion (used for min_motion_ratio, S11).
MOTION_MODES = frozenset(
    {RenderMode.PAN, RenderMode.REVEAL, RenderMode.LAYERED, RenderMode.CLIP}
)


class OutputFormat(str, Enum):
    INFOGRAPHIC = "INFOGRAPHIC"
    ANIMATION = "ANIMATION"
    HYBRID = "HYBRID"


@dataclass
class Label:
    text: str
    claim_id: str


@dataclass
class Scene:
    scene_id: int
    narration: str = ""
    importance: float = 0.5            # in [0, 1]
    explain_pattern: str = "cause_effect"
    claim_ids: list[str] = field(default_factory=list)
    facet: str = "science"
    visual_type: str = "infographic"
    layout: Optional[str] = None
    labels: list[Label] = field(default_factory=list)
    start_s: float = 0.0
    duration_s: float = 0.0
    audio_asset_id: Optional[str] = None
    render_mode: Optional[RenderMode] = None   # filled by the Budget Optimizer
    cost_credit: int = 0
    transition_in: str = "cut"
    asset_id: Optional[str] = None


@dataclass(frozen=True)
class FormatProfile:
    format: OutputFormat
    allowed_modes: tuple[RenderMode, ...]
    min_motion_ratio: float = 0.0
    t_min: float = 4.0
    t_max: float = 10.0
    t_total_min: int = 60
    t_total_max: int = 120
    max_input_words: int = 1500
    text_by_code: bool = True


@dataclass
class OptimizeResult:
    feasible: bool
    plan: dict[int, RenderMode] = field(default_factory=dict)  # scene_id -> mode
    total_cost: int = 0
    total_value: float = 0.0
    motion_ratio: float = 0.0
    reason: str = ""
    suggestion: str = ""
    algorithm: str = ""


@dataclass
class TimelineEntry:
    """One placed scene on the timeline (report 5.5). Times are in seconds."""
    scene_id: int
    start_s: float
    duration_s: float                  # on-screen length = max(audio + pad, t_min)
    audio_duration_s: float            # real (or simulated) narration length
    pad_s: float = 0.0
    render_mode: Optional[RenderMode] = None
    transition_in: str = "cut"
    claim_ids: list[str] = field(default_factory=list)
    narration: str = ""
 
 
@dataclass
class Timeline:
    """Output of the Timeline Assembler. `codes` empty means S12/S13 and the scene rules hold."""
    entries: list[TimelineEntry] = field(default_factory=list)
    total_s: float = 0.0
    t_target: float = 0.0
    deviation: float = 0.0             # |total - t_target| / t_target   (S13 threshold: 0.05)
    codes: set[str] = field(default_factory=set)
    stretched: list[int] = field(default_factory=list)   # scene_ids lengthened up to t_min
    too_long: list[int] = field(default_factory=list)    # scene_ids longer than t_max
 
    @property
    def ok(self) -> bool:
        return not self.codes