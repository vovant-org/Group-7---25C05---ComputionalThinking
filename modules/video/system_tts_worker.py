"""Standalone worker: speak ONE text with the operating-system voice (pyttsx3) into a wav file.

Why a separate process: pyttsx3 (SAPI5 on Windows) must run on a process's MAIN thread. Inside Streamlit the
script runs in a worker thread, and pyttsx3 keeps ONE engine per process, so after an interrupted rerun the
engine stays "in a run loop" and `runAndWait()` blocks forever. A fresh process per text has neither problem,
and the parent can kill it after a timeout.

Protocol: stdin = UTF-8 JSON {"text", "path", "speed", "voice_hint"}; exit code 0 = file written.
Do not import anything from the project here: it runs as a plain script (python system_tts_worker.py).
"""
import json
import sys


def main() -> int:
    req = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    import pyttsx3

    engine = pyttsx3.init()
    engine.setProperty("rate", int(engine.getProperty("rate") * float(req.get("speed", 1.0))))
    hint = (req.get("voice_hint") or "").lower()
    if hint:
        for v in engine.getProperty("voices"):
            if hint in f"{v.id} {v.name}".lower():
                engine.setProperty("voice", v.id)
                break
    engine.save_to_file(req["text"], req["path"])
    engine.runAndWait()
    engine.stop()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:                       # the parent shows stderr to the user
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)