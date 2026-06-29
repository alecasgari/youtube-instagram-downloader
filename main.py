#!/usr/bin/env python3
"""Entry point for the giv-ytdlp HTTP service."""

from server import run_server

if __name__ == "__main__":
    raise SystemExit(run_server())
