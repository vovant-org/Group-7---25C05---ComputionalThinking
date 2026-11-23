"""One entry point for the CLI and the UI: consent check, read the input, build the picture service."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.config import OUTPUT_DIR
from modules.ai.images import ArtService, export_kit, make_image_provider
from modules.ai.llm import make_llm
from modules.ai.net import AIError
from modules.ai.reader import ReadResult, local_visual, read_input


@dataclass
class AIPlan:
    claims: Optional[list] = None                 # None: keep the caller's own claims
    visuals: dict = field(default_factory=dict)   # claim_id -> English picture description
    art: Optional[ArtService] = None
    read: Optional[ReadResult] = None
    notes: list = field(default_factory=list)


def prepare_ai(request: str, reference: str, claims: Optional[list], *, read_kind: str = "off", image_kind: str = "off",
               folder: Optional[Path] = None, allow_online: bool = False, n_scenes: int = 14,
               cache_dir: Optional[Path] = None) -> AIPlan:
    """Raises AIError when the user did not confirm online use or a provider cannot start."""
    online = read_kind in ("auto", "pollinations", "gemini") or image_kind in ("pollinations", "cloudflare")
    if online and not allow_online:
        raise AIError("this AI option sends your text to an online service: confirm it first (--allow-online)")
    plan = AIPlan()
    if read_kind != "off":
        plan.read = read_input(request, reference, make_llm(read_kind), n_scenes)
        plan.notes += plan.read.notes
        if plan.read.claims:
            plan.claims, plan.visuals = plan.read.claims, plan.read.visuals
            plan.notes.append(f"AI claims kept: {len(plan.read.claims)} (about {len(plan.read.claims) * 18 / 165 * 60:.0f} s of narration).")
    elif claims:
        plan.visuals = {c.claim_id: local_visual(c.text) for c in claims}
    if image_kind != "off":
        provider = make_image_provider(image_kind, folder)
        plan.art = ArtService(provider, cache_dir or (OUTPUT_DIR / "ai_cache"))
        if not plan.visuals and claims:
            plan.visuals = {c.claim_id: local_visual(c.text) for c in claims}
    return plan


def write_kit(claims: list, visuals: dict, folder: Path) -> Path:
    return export_kit(claims, visuals, folder)
