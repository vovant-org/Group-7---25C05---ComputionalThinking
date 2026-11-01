from pathlib import Path

from core.models import FormatProfile, OutputFormat, RenderMode as M

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

DEFAULT_FORMAT = OutputFormat.INFOGRAPHIC   # Router default (report 5.1)
DEFAULT_T_TARGET = 90                        # seconds

# ASSUMPTION (not measured yet): relative credit cost / quality per render mode.
# Replace with measured values after to-do item 11 (provider cost measurement).
MODE_COST = {M.STATIC: 1, M.PAN: 2, M.REVEAL: 3, M.LAYERED: 4, M.CLIP: 14}
MODE_QUALITY = {M.STATIC: 0.2, M.PAN: 0.4, M.REVEAL: 0.7, M.LAYERED: 0.6, M.CLIP: 1.0}

PROFILES = {
    OutputFormat.INFOGRAPHIC: FormatProfile(
        OutputFormat.INFOGRAPHIC, (M.STATIC, M.PAN, M.REVEAL), min_motion_ratio=0.5
    ),
    OutputFormat.ANIMATION: FormatProfile(
        OutputFormat.ANIMATION, (M.LAYERED, M.CLIP), min_motion_ratio=1.0,
        text_by_code=False,
    ),
    # ASSUMPTION: HYBRID min_motion_ratio is a [TODO] in the report; 0.5 chosen.
    OutputFormat.HYBRID: FormatProfile(
        OutputFormat.HYBRID, (M.PAN, M.REVEAL, M.LAYERED, M.CLIP), min_motion_ratio=0.5
    ),
}
