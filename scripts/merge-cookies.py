#!/usr/bin/env python3
"""Merge Netscape cookie exports into cookies/cookies.txt for giv-ytdlp."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COOKIES_DIR = ROOT / "cookies"
OUT = COOKIES_DIR / "cookies.txt"

SOURCES = (
    COOKIES_DIR / "youtube.export.txt",
    COOKIES_DIR / "instagram.export.txt",
)

HEADER = """# Netscape HTTP Cookie File
# https://curl.haxx.se/rfc/cookie_spec.html
# This is a generated file! Do not edit.
# Merged by scripts/merge-cookies.py — YouTube + Instagram
"""


def parse_lines(path: Path) -> dict[tuple[str, str, str], str]:
    """Key: (domain, path, name) -> full tab-separated line."""
    rows: dict[tuple[str, str, str], str] = {}
    if not path.is_file():
        raise SystemExit(f"Missing {path} — export cookies from browser first.")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, _flag, cpath, _secure, expiry, name, value = parts[:7]
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
        rows[key] = line
    return rows


def main() -> int:
    merged: dict[tuple[str, str, str], str] = {}
    for src in SOURCES:
        merged.update(parse_lines(src))

    youtube = sum(1 for k in merged if k[0].endswith("youtube.com"))
    instagram = sum(1 for k in merged if k[0].endswith("instagram.com"))
    if youtube < 5:
        raise SystemExit(f"Too few YouTube cookies ({youtube}) — re-export from youtube.com")
    if instagram < 3:
        raise SystemExit(f"Too few Instagram cookies ({instagram}) — re-export from instagram.com")

    COOKIES_DIR.mkdir(parents=True, exist_ok=True)
    body = "\n".join(merged[k] for k in sorted(merged)) + "\n"
    OUT.write_text(HEADER + "\n" + body, encoding="utf-8")
    print(f"Wrote {OUT} ({youtube} YouTube + {instagram} Instagram cookies)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
