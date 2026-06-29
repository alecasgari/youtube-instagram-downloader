from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from config import Settings, resolve_cookies_file


def detect_source(url: str) -> str:
    u = url.lower()
    if "instagram.com" in u:
        return "instagram"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    return "other"


def download_video(url: str, work_id: str, settings: Settings) -> dict:
    work_dir = settings.data_dir / f"giv-video-{work_id}"
    if work_dir.exists():
        shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    source = detect_source(url)

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--remote-components",
        "ejs:github",
        "-f",
        "bv*+ba/b",
        "--merge-output-format",
        "mp4",
        "-o",
        str(work_dir / "%(id)s.%(ext)s"),
        "--write-info-json",
        "--write-thumbnail",
        "--convert-thumbnails",
        "jpg",
    ]
    cookies_file = resolve_cookies_file(settings)
    if cookies_file:
        cmd.extend(["--cookies", str(cookies_file)])
    elif source == "youtube":
        raise RuntimeError(
            "YouTube needs cookies on this server. Export cookies.txt from your browser "
            "(logged into YouTube) and copy to /data/cookies.txt in the container. "
            "See README.md"
        )

    cmd.append(url)

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "yt-dlp failed")

    info_files = sorted(work_dir.glob("*.info.json"))
    if not info_files:
        raise RuntimeError("yt-dlp did not write an info.json file")

    meta = json.loads(info_files[0].read_text(encoding="utf-8"))
    video_id = meta.get("id")
    if not video_id:
        raise RuntimeError("Missing video id in yt-dlp metadata")

    mp4 = work_dir / f"{video_id}.mp4"
    poster = work_dir / f"{video_id}.jpg"
    if not mp4.is_file():
        raise RuntimeError(f"Expected mp4 not found: {mp4}")
    if not poster.is_file():
        raise RuntimeError(f"Expected poster jpg not found: {poster}")

    return {
        "video_id": video_id,
        "work_dir": work_dir,
        "source": detect_source(url),
        "video_meta": meta,
        "mp4": mp4,
        "poster": poster,
    }


def cleanup_work_dir(work_dir: Path) -> None:
    if work_dir.is_dir():
        shutil.rmtree(work_dir, ignore_errors=True)
