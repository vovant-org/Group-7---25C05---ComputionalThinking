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

# ---- Voice Segmenter defaults (report 4(f), 5.7). ASSUMPTION: wpm is not measured yet
# (to-do items 12/14). For Vietnamese, "words" are syllables, so wpm must be measured per language.
VOICE_WPM = 165.0          # middle of the report's 150-180 wpm range
VOICE_MIN_S = 10.0
VOICE_MAX_S = 12.0
VOICE_TARGET_S = 11.0
VOICE_MAX_SENTENCES = 2
VOICE_TOL_S = 1.0          # tolerance used by the post-TTS check (report 5.7)
