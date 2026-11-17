"""Renders the video: frames drawn by code, piped to FFmpeg with the audio track.
INFOGRAPHIC scenes use `SceneRenderer` below; ANIMATION scenes use the cut-out `LayerRenderer`
(modules/video/animation.py). Both give `frame(t)` and `dur`, so the rest of the loop is shared.

Render modes of the infographic profile (report 4(b)):
  STATIC  the finished frame, no motion
  PAN     slow zoom (Ken Burns); the zoom only enlarges text, so labels never get smaller than drawn
  REVEAL  elements fade in one by one, each when the narrator reaches its part (proportional to the
          words of each part, report 5.4)
Between scenes the first 0.3 s cross-fades from the previous scene (profile transition "fade").
Subtitles are drawn after the zoom (they never move) and also muxed as a soft track.
Everything is deterministic: the same timeline, scenes and audio give the same frames.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Mapping, Optional

import numpy as np
from PIL import Image

from modules.video.composer import ComposedScene, Style
from modules.video.subtitles import Cue, cue_band, make_cues, to_srt
from modules.video.voice import VoiceRecorder, build_audio_track, find_ffmpeg

FADE_IN_S = 0.45          # reveal fade of one element
LEAD_S = 0.15             # first element appears this long after the scene starts
CROSSFADE_S = 0.30        # transition between scenes
ZOOM_END = 1.07           # PAN: zoom goes from 1.0 to this


class RenderError(RuntimeError):
    pass


class SceneRenderer:
    """Frames of one scene as uint8 arrays (HxWx3), without subtitles."""

    def __init__(self, cs: ComposedScene, mode: str, duration_s: float, audio_s: float, index: int,
                 st: Style = Style()):
        from modules.video.composer import static_frame
        self.cs, self.mode, self.dur, self.index, self.st = cs, mode, duration_s, index, st
        self.full = static_frame(cs)
        self.starts = self._reveal_starts(audio_s) if mode == "REVEAL" else [0.0] * len(cs.elements)
        self._cache: dict[tuple, np.ndarray] = {}

    def _reveal_starts(self, audio_s: float) -> list[float]:
        words = [max(1, e.words) for e in self.cs.elements]
        total, cum, out = sum(words), 0, []
        span = max(0.5, audio_s - LEAD_S - 0.3)
        for w in words:
            out.append(min(LEAD_S + span * cum / total, max(0.0, self.dur - FADE_IN_S)))
            cum += w
        return out

    def _composite(self, alphas: tuple[float, ...]) -> np.ndarray:
        if all(a >= 1.0 for a in alphas):
            return self.full
        key = tuple(round(a, 2) for a in alphas)
        if key in self._cache:
            return self._cache[key]
        out = self.cs.base_arr.copy()
        for el, a in zip(self.cs.elements, alphas):
            if a <= 0:
                continue
            h, w = el.alpha.shape[:2]
            reg = out[el.y:el.y + h, el.x:el.x + w].astype(np.float32)
            al = el.alpha * a
            out[el.y:el.y + h, el.x:el.x + w] = (reg * (1 - al) + el.rgb * al).astype(np.uint8)
        if len(self._cache) > 64:
            self._cache.clear()
        self._cache[key] = out
        return out

    def _zoom(self, arr: np.ndarray, t: float) -> np.ndarray:
        W, H = self.st.size
        z = 1.0 + (ZOOM_END - 1.0) * min(1.0, t / max(self.dur, 1e-6))
        w, h = W / z, H / z
        ax, ay = (0.25, 0.35) if self.index % 2 == 0 else (0.75, 0.35)
        x0, y0 = (W - w) * ax, (H - h) * ay
        img = Image.fromarray(arr).resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + w, y0 + h))
        return np.asarray(img)

    def frame(self, t: float) -> np.ndarray:
        if self.mode == "REVEAL":
            arr = self._composite(tuple(min(1.0, max(0.0, (t - s) / FADE_IN_S)) for s in self.starts))
        else:
            arr = self.full
        return self._zoom(arr, t) if self.mode == "PAN" else arr


def probe_duration(path: Path, ffmpeg: Optional[str] = None) -> float:
    """Duration of a media file in seconds (parsed from `ffmpeg -i`, so ffprobe is not required)."""
    proc = subprocess.run([ffmpeg or find_ffmpeg(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
    if not m:
        raise RenderError(f"cannot read the duration of {path}")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def render_video(timeline, composed: Mapping[int, ComposedScene], recorder: VoiceRecorder, out_path: Path,
                 st: Style = Style(), fps: int = 24, burn_subtitles: bool = True, soft_subtitles: bool = True,
                 progress: Optional[Callable[[float, str], None]] = None) -> dict:
    """Write the MP4. Returns {"frames", "cues", "srt"}. Raises RenderError with FFmpeg's message."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = find_ffmpeg()
    entries = timeline.entries
    if not entries:
        raise RenderError("empty timeline")
    W, H = st.size
    n_total = int(round(timeline.total_s * fps))
    cues: list[Cue] = make_cues(entries)
    srt_path = out_path.with_suffix(".srt")
    srt_path.write_text(to_srt(cues), encoding="utf-8")

    renderers = []
    for i, e in enumerate(entries):
        cs = composed[e.scene_id]
        if hasattr(cs, "make_renderer"):                   # ANIMATION: cut-out layers (modules/video/animation.py)
            renderers.append(cs.make_renderer(e.duration_s, e.audio_duration_s, i, st))
        else:                                              # INFOGRAPHIC: STATIC / PAN / REVEAL
            renderers.append(SceneRenderer(cs, e.render_mode.value, e.duration_s, e.audio_duration_s, i, st))
    starts = [int(round(e.start_s * fps)) for e in entries] + [n_total]
    bands: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    with tempfile.TemporaryDirectory() as tmp:
        audio = build_audio_track(entries, recorder, Path(tmp) / "audio.wav", timeline.total_s)
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
               "-r", str(fps), "-i", "-", "-i", str(audio)]
        if soft_subtitles:
            cmd += ["-i", str(srt_path)]
        cmd += ["-map", "0:v", "-map", "1:a"] + (["-map", "2:s"] if soft_subtitles else [])
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k"]
        if soft_subtitles:
            cmd += ["-c:s", "mov_text"]
        cmd += ["-movflags", "+faststart", "-t", f"{timeline.total_s:.3f}", str(out_path)]
        err_file = Path(tmp) / "ffmpeg.err"
        with open(err_file, "wb") as err:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=err)
            try:
                ci, prev_last = 0, None
                for idx, r in enumerate(renderers):
                    f0, f1 = starts[idx], starts[idx + 1]
                    for f in range(f0, f1):
                        t = (f - f0) / fps
                        arr = r.frame(t)
                        if idx > 0 and prev_last is not None and t < CROSSFADE_S:
                            a = t / CROSSFADE_S
                            arr = (prev_last.astype(np.float32) * (1 - a) + arr.astype(np.float32) * a).astype(np.uint8)
                        if burn_subtitles and cues:
                            ta = f / fps
                            while ci < len(cues) and cues[ci].end_s <= ta:
                                ci += 1
                            if ci < len(cues) and cues[ci].start_s <= ta:
                                text = cues[ci].text
                                if text not in bands:
                                    bands[text] = cue_band(text, st)
                                rgb, al = bands[text]
                                arr = arr.copy()
                                reg = arr[H - st.sub_h:H].astype(np.float32)
                                arr[H - st.sub_h:H] = (reg * (1 - al) + rgb * al).astype(np.uint8)
                        proc.stdin.write(np.ascontiguousarray(arr).tobytes())
                        if progress and f % fps == 0:
                            progress(f / max(1, n_total), f"scene {idx + 1}/{len(renderers)}")
                    prev_last = r.frame(r.dur)
                proc.stdin.close()
            except BrokenPipeError:
                pass
            finally:
                if proc.stdin and not proc.stdin.closed:
                    proc.stdin.close()
            code = proc.wait()
        if code != 0:
            raise RenderError("ffmpeg failed: " + err_file.read_text(errors="replace").strip()[-600:])
    if progress:
        progress(1.0, "done")
    return {"frames": n_total, "cues": len(cues), "srt": str(srt_path)}
