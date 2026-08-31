"""Parse, merge, and save Netscape cookies for YouTube + Instagram."""

from __future__ import annotations

import time
from pathlib import Path

HEADER = """# Netscape HTTP Cookie File
# https://curl.haxx.se/rfc/cookie_spec.html
# This is a generated file! Do not edit.
# Updated via giv-ytdlp UI
"""


def parse_netscape(text: str) -> dict[tuple[str, str, str], str]:
    rows: dict[tuple[str, str, str], str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, _flag, cpath, _secure, expiry, name, _value = parts[:7]
        key = (domain, cpath, name)
        try:
            new_exp = int(expiry)
        except ValueError:
            new_exp = 0
        if key in rows:
            old_parts = rows[key].split("\t")
            try:
                old_exp = int(old_parts[4])
            except (ValueError, IndexError):
                old_exp = 0
            if new_exp < old_exp:
                continue
        rows[key] = "\t".join(parts[:7])
    return rows


def _is_youtube(domain: str) -> bool:
    d = domain.lstrip(".").lower()
    return d == "youtube.com" or d.endswith(".youtube.com") or d == "google.com" or d.endswith(".google.com")


def _is_instagram(domain: str) -> bool:
    d = domain.lstrip(".").lower()
    return d == "instagram.com" or d.endswith(".instagram.com") or d == "facebook.com" or d.endswith(".facebook.com")


def count_platform(rows: dict[tuple[str, str, str], str]) -> tuple[int, int]:
    youtube = sum(1 for k in rows if _is_youtube(k[0]))
    instagram = sum(1 for k in rows if _is_instagram(k[0]))
    return youtube, instagram


def load_file(path: Path) -> dict[tuple[str, str, str], str]:
    if not path.is_file():
        return {}
    return parse_netscape(path.read_text(encoding="utf-8", errors="replace"))


def merge_exports(
    existing: dict[tuple[str, str, str], str],
    youtube_text: str,
    instagram_text: str,
) -> dict[tuple[str, str, str], str]:
    merged = dict(existing)
    yt = youtube_text.strip()
    ig = instagram_text.strip()
    if yt:
        incoming = parse_netscape(yt)
        if not incoming:
            raise ValueError("متن کوکی یوتیوب معتبر نیست (فرمت Netscape / Get cookies.txt LOCALLY).")
        merged = {k: v for k, v in merged.items() if not _is_youtube(k[0])}
        merged.update(incoming)
    if ig:
        incoming = parse_netscape(ig)
        if not incoming:
            raise ValueError("متن کوکی اینستاگرام معتبر نیست (فرمت Netscape / Get cookies.txt LOCALLY).")
        merged = {k: v for k, v in merged.items() if not _is_instagram(k[0])}
        merged.update(incoming)
    youtube, instagram = count_platform(merged)
    if youtube < 5:
        raise ValueError(f"کوکی یوتیوب ناکافی است ({youtube}). از youtube.com دوباره export کن.")
    if instagram < 3:
        raise ValueError(f"کوکی اینستاگرام ناکافی است ({instagram}). از instagram.com دوباره export کن.")
    return merged


def write_cookies(path: Path, rows: dict[tuple[str, str, str], str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(rows[k] for k in sorted(rows)) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(HEADER + "\n" + body, encoding="utf-8")
    tmp.replace(path)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def cookie_status(path: Path | None) -> dict:
    if path is None or not path.is_file():
        return {
            "present": False,
            "youtube": 0,
            "instagram": 0,
            "updated_at": None,
            "bytes": 0,
        }
    rows = load_file(path)
    youtube, instagram = count_platform(rows)
    mtime = path.stat().st_mtime
    return {
        "present": True,
        "youtube": youtube,
        "instagram": instagram,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(mtime)),
        "bytes": path.stat().st_size,
    }
