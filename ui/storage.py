"""Reads and writes the project files that already live in `outputs/videos/`.

A "project" is a rendered video. The backend writes three files per video:

    <id>.mp4          the video            (modules/video/render.py)
    <id>.srt          subtitle cues        (modules/video/render.py)
    <id>.report.json  checks and timeline  (modules/video/make_video.py)

This module adds ONE optional file, `<id>.project.json`, written by the UI after a successful run. It stores
what the report does not: the title, the voice, the budget the user asked for, which claim belongs to which
scene and the stage log. Projects made before this UI existed (for example the bundled sleep.mp4) have no
such file and are shown with what the report contains; missing details are labelled, not invented.
No database and no new storage location: deleting a project means deleting its files.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Optional

from core.config import OUTPUT_DIR
from ui.adapters import parse_srt, short_title

RECORD_SUFFIX = ".project.json"
REPORT_SUFFIX = ".report.json"


def videos_dir() -> Path:
    return Path(OUTPUT_DIR) / "videos"


def project_key(*parts: object) -> str:
    """Stable id from the inputs: the same settings give the same file (as the original page did)."""
    return "sf-" + hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:10]


def _read_json(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def save_record(project_id: str, record: dict, folder: Optional[Path] = None) -> Path:
    folder = Path(folder) if folder else videos_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{project_id}{RECORD_SUFFIX}"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _summary(report_path: Path) -> Optional[dict]:
    report = _read_json(report_path)
    if report is None or "timeline" not in report:
        return None
    pid = report_path.name[: -len(REPORT_SUFFIX)]
    folder = report_path.parent
    record = _read_json(folder / f"{pid}{RECORD_SUFFIX}")
    mp4 = folder / f"{pid}.mp4"
    crit = report.get("criteria", {})
    passed = sum(1 for v in crit.values() if v.get("pass"))
    try:
        mtime = max(report_path.stat().st_mtime, mp4.stat().st_mtime if mp4.exists() else 0)
    except OSError:
        mtime = time.time()
    voice = (record or {}).get("voice", {}) or {}
    return {
        "id": pid, "title": short_title((record or {}).get("title") or report.get("request", pid), 90),
        "format": report.get("format", ""), "total_s": report.get("total_s"), "mtime": mtime,
        "has_video": mp4.exists(), "checks": (passed, len(crit)) if crit else None,
        "voice": voice.get("name") or ("silent" if report.get("voice_is_silent") else report.get("voice_engine", "")),
        "made_with_ui": record is not None, "scenes": report.get("scenes"),
    }


def list_projects(folder: Optional[Path] = None) -> list[dict]:
    """All rendered projects, newest first. Unreadable reports are skipped."""
    folder = Path(folder) if folder else videos_dir()
    if not folder.is_dir():
        return []
    items = [s for p in folder.glob(f"*{REPORT_SUFFIX}") if (s := _summary(p)) is not None]
    return sorted(items, key=lambda s: s["mtime"], reverse=True)


def load_project(project_id: str, folder: Optional[Path] = None) -> Optional[dict]:
    """Everything the Video Studio needs for one project, or None when the report is missing/unreadable."""
    folder = Path(folder) if folder else videos_dir()
    report = _read_json(folder / f"{project_id}{REPORT_SUFFIX}")
    if report is None or "timeline" not in report:
        return None
    record = _read_json(folder / f"{project_id}{RECORD_SUFFIX}")
    mp4, srt = folder / f"{project_id}.mp4", folder / f"{project_id}.srt"
    cues = []
    if srt.exists():
        try:
            cues = parse_srt(srt.read_text(encoding="utf-8"))
        except OSError:
            cues = []
    return {"id": project_id, "report": report, "record": record, "cues": cues,
            "video_path": mp4 if mp4.exists() else None, "srt_path": srt if srt.exists() else None,
            "report_path": folder / f"{project_id}{REPORT_SUFFIX}"}
