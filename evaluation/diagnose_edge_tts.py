"""Try every built-in Edge voice through the same code path the app uses, and say which ones work.

Run from the project root (needs internet):  py -m evaluation.diagnose_edge_tts
"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

from modules.video.voice import EdgeEngine
from modules.voice_library.library import BUILTIN_VOICES

TEXT = {"en": "Sleep helps the brain store memories. Adults need seven to nine hours a night.",
        "vi": "Giấc ngủ giúp não bộ lưu giữ ký ức. Người lớn cần ngủ từ bảy đến chín giờ mỗi đêm."}


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="edgediag_"))
    for v in BUILTIN_VOICES:
        t0 = time.time()
        try:
            out = EdgeEngine(v, 1.0).synthesize(TEXT[v.language], tmp / v.voice_id)
            print(f"OK    {v.engine_voice:<26} {out.stat().st_size / 1024:6.1f} KB  {time.time() - t0:4.1f}s")
        except Exception as exc:
            print(f"FAIL  {v.engine_voice:<26} {type(exc).__name__}: {str(exc)[:110]}")


if __name__ == "__main__":
    main()
