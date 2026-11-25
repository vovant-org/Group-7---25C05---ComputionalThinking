"""Send one sentence straight to edge-tts (no app code) several times per voice and report what happens.

Run from the project root (needs internet):  py -m evaluation.diagnose_edge_text
Optional:  py -m evaluation.diagnose_edge_text "your own sentence"
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
import time
from pathlib import Path

import edge_tts

DEFAULT = "Giấc ngủ là lúc não sắp xếp ký ức và dọn sạch chất thải tích tụ trong ngày."
VOICES = ["vi-VN-NamMinhNeural", "vi-VN-HoaiMyNeural", "en-US-AriaNeural"]
TRIES = 3


async def once(text: str, voice: str, path: Path) -> str:
    t0 = time.time()
    try:
        await asyncio.wait_for(edge_tts.Communicate(text, voice, rate="+0%").save(str(path)), 30)
        return f"OK   {path.stat().st_size / 1024:5.1f} KB {time.time() - t0:4.1f}s"
    except Exception as exc:
        return f"FAIL {type(exc).__name__} {time.time() - t0:4.1f}s"


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="edgetxt_"))
    texts = [" ".join(sys.argv[1:])] if len(sys.argv) > 1 else [DEFAULT, "Giấc ngủ rất quan trọng.", "Hello, sleep is important."]
    for text in texts:
        print(f"\n{text!r}")
        for voice in VOICES:
            results = [asyncio.run(once(text, voice, tmp / f"{voice}-{i}.mp3")) for i in range(TRIES)]
            print(f"  {voice:<22} " + " | ".join(results))


if __name__ == "__main__":
    main()
