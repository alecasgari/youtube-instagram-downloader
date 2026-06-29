from __future__ import annotations

import json
import mimetypes
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote

from config import Settings, load_settings, resolve_cookies_file
from download import cleanup_work_dir, download_video
from r2_upload import upload_video_assets

_download_lock = threading.Lock()

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


class Handler(BaseHTTPRequestHandler):
    settings: Settings

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("invalid json") from exc

    def _serve_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, rel_path: str) -> None:
        static_root = self.settings.static_dir.resolve()
        target = (static_root / rel_path).resolve()
        if not str(target).startswith(str(static_root)) or not target.is_file():
            self._json(404, {"ok": False, "error": "not found"})
            return
        ext = target.suffix.lower()
        content_type = CONTENT_TYPES.get(ext) or mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self._serve_bytes(200, target.read_bytes(), content_type)

    def _check_api_token(self, data: dict) -> bool:
        token = self.settings.token
        if not token:
            return True
        return data.get("token") == token

    def _check_ui_password(self, data: dict) -> bool:
        pwd = self.settings.ui_password
        if not pwd:
            return False
        supplied = str(data.get("password", "")).strip()
        if not supplied:
            supplied = str(self.headers.get("X-UI-Password", "")).strip()
        return supplied == pwd

    def _parse_upload_r2(self, data: dict, default: bool = True) -> bool:
        upload_r2 = data.get("upload_r2", default)
        if isinstance(upload_r2, str):
            return upload_r2.lower() not in ("0", "false", "no")
        return bool(upload_r2)

    def _run_download(self, data: dict, default_upload_r2: bool = True) -> None:
        url = str(data.get("url", "")).strip()
        work_id = str(data.get("work_id", "manual")).strip() or "manual"
        if not url:
            self._json(400, {"ok": False, "error": "url required"})
            return

        upload_r2 = self._parse_upload_r2(data, default_upload_r2)
        if upload_r2 and not self.settings.r2_configured:
            self._json(
                500,
                {
                    "ok": False,
                    "error": "R2 not configured — set R2_* env vars or pass upload_r2: false",
                },
            )
            return

        if not _download_lock.acquire(blocking=False):
            self._json(503, {"ok": False, "error": "another download is in progress"})
            return

        work_dir = None
        try:
            result = download_video(url, work_id, self.settings)
            work_dir = result["work_dir"]
            video_id = result["video_id"]

            payload: dict = {
                "ok": True,
                "video_id": video_id,
                "source": result["source"],
                "video_meta": {
                    "title": result["video_meta"].get("title", ""),
                    "description": result["video_meta"].get("description", ""),
                    "duration_string": result["video_meta"].get("duration_string", ""),
                    "upload_date": result["video_meta"].get("upload_date", ""),
                    "webpage_url": result["video_meta"].get("webpage_url", url),
                },
            }

            if upload_r2:
                payload["r2"] = upload_video_assets(
                    self.settings,
                    video_id,
                    result["mp4"],
                    result["poster"],
                )
                cleanup_work_dir(work_dir)
                work_dir = None
                payload["work_dir"] = None
            else:
                payload["work_dir"] = str(work_dir)
                payload["mp4_path"] = str(result["mp4"])
                payload["poster_path"] = str(result["poster"])

            self._json(200, payload)
        except Exception as exc:
            if work_dir is not None:
                cleanup_work_dir(work_dir)
            self._json(500, {"ok": False, "error": str(exc)})
        finally:
            _download_lock.release()

    def do_GET(self) -> None:
        path = unquote(self.path.split("?", 1)[0])

        if path == "/health":
            s = self.settings
            self._json(
                200,
                {
                    "ok": True,
                    "service": "giv-ytdlp",
                    "r2_configured": s.r2_configured,
                    "ui_enabled": s.ui_enabled,
                    "cookies_file": str(resolve_cookies_file(s) or ""),
                    "data_dir": str(s.data_dir),
                },
            )
            return

        if path in ("/", "/ui"):
            self._serve_static("index.html")
            return

        if path.startswith("/static/"):
            self._serve_static(path[len("/static/") :])
            return

        self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        path = unquote(self.path.split("?", 1)[0])

        try:
            data = self._read_json_body()
        except ValueError:
            self._json(400, {"ok": False, "error": "invalid json"})
            return

        if path == "/download":
            if not self._check_api_token(data):
                self._json(401, {"ok": False, "error": "unauthorized"})
                return
            self._run_download(data, default_upload_r2=True)
            return

        if path == "/api/ui-download":
            if not self.settings.ui_enabled:
                self._json(503, {"ok": False, "error": "UI password not configured on server"})
                return
            if not self._check_ui_password(data):
                self._json(401, {"ok": False, "error": "wrong password"})
                return
            self._run_download(data, default_upload_r2=self._parse_upload_r2(data, True))
            return

        self._json(404, {"ok": False, "error": "not found"})


def run_server(settings: Settings | None = None) -> int:
    settings = settings or load_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    class BoundHandler(Handler):
        pass

    BoundHandler.settings = settings

    server = HTTPServer((settings.host, settings.port), BoundHandler)
    print(
        f"giv-ytdlp on http://{settings.host}:{settings.port} "
        f"(r2={'yes' if settings.r2_configured else 'no'}, "
        f"ui={'yes' if settings.ui_enabled else 'no'}, data={settings.data_dir})",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
    return 0
