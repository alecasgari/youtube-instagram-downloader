from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import sys
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote

from config import Settings, load_settings, resolve_cookies_file
from cookies_store import cookie_status, load_file, merge_exports, write_cookies
from download import cleanup_work_dir, download_video
from r2_upload import upload_video_assets

_download_lock = threading.Lock()
_login_attempts: dict[str, list[float]] = {}
_login_lock = threading.Lock()

SESSION_COOKIE = "giv_ytdlp_session"
SESSION_TTL = 7 * 24 * 3600
MAX_BODY = 512_000
LOGIN_WINDOW = 15 * 60
LOGIN_MAX_FAILS = 8

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def make_session_token(username: str, secret: str) -> str:
    payload = _b64url(json.dumps({"u": username, "exp": int(time.time()) + SESSION_TTL}).encode("utf-8"))
    return f"{payload}.{_sign(payload, secret)}"


def read_session_token(token: str, secret: str, username: str) -> bool:
    if not token or "." not in token or not secret or not username:
        return False
    payload, sig = token.rsplit(".", 1)
    expected = _sign(payload, secret)
    if not hmac.compare_digest(sig, expected):
        return False
    try:
        data = json.loads(_b64url_decode(payload).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return False
    if data.get("u") != username:
        return False
    try:
        exp = int(data.get("exp", 0))
    except (TypeError, ValueError):
        return False
    return exp >= int(time.time())


class Handler(BaseHTTPRequestHandler):
    settings: Settings
    timeout = 600

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _client_ip(self) -> str:
        forwarded = self.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return self.address_string()

    def _is_https(self) -> bool:
        proto = self.headers.get("X-Forwarded-Proto", "").split(",")[0].strip().lower()
        return proto == "https"

    def _session_secret(self) -> str:
        s = self.settings
        if s.ui_secret:
            return s.ui_secret
        raw = f"{s.ui_username}:{s.ui_password}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length > MAX_BODY:
            raise ValueError("body too large")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("invalid json") from exc
        if not isinstance(data, dict):
            raise ValueError("invalid json")
        return data

    def _serve_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
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

    def _cookie_header(self) -> SimpleCookie:
        jar = SimpleCookie()
        raw = self.headers.get("Cookie", "")
        if raw:
            jar.load(raw)
        return jar

    def _session_valid(self) -> bool:
        s = self.settings
        if not s.ui_enabled:
            return False
        morsel = self._cookie_header().get(SESSION_COOKIE)
        if not morsel:
            return False
        return read_session_token(morsel.value, self._session_secret(), s.ui_username)

    def _set_session_headers(self, token: str | None) -> list[str]:
        attrs = [f"Path=/", "HttpOnly", "SameSite=Strict"]
        if self._is_https():
            attrs.append("Secure")
        if token:
            attrs.append(f"Max-Age={SESSION_TTL}")
            return [f"{SESSION_COOKIE}={token}; " + "; ".join(attrs)]
        attrs.append("Max-Age=0")
        return [f"{SESSION_COOKIE}=; " + "; ".join(attrs)]

    def _json_with_cookies(self, status: int, payload: dict, set_cookies: list[str] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        for cookie in set_cookies or []:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _login_blocked(self, ip: str) -> bool:
        now = time.time()
        with _login_lock:
            fails = [t for t in _login_attempts.get(ip, []) if now - t < LOGIN_WINDOW]
            _login_attempts[ip] = fails
            return len(fails) >= LOGIN_MAX_FAILS

    def _register_login_fail(self, ip: str) -> None:
        with _login_lock:
            _login_attempts.setdefault(ip, []).append(time.time())

    def _clear_login_fails(self, ip: str) -> None:
        with _login_lock:
            _login_attempts.pop(ip, None)

    def _parse_upload_r2(self, data: dict, default: bool = True) -> bool:
        upload_r2 = data.get("upload_r2", default)
        if isinstance(upload_r2, str):
            return upload_r2.lower() not in ("0", "false", "no")
        return bool(upload_r2)

    def _cookies_path(self) -> Path:
        current = resolve_cookies_file(self.settings)
        if current:
            return current
        return self.settings.data_dir / "cookies.txt"

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

    def _handle_login(self, data: dict) -> None:
        s = self.settings
        ip = self._client_ip()
        if not s.ui_enabled:
            self._json(503, {"ok": False, "error": "UI login is not configured on the server"})
            return
        if self._login_blocked(ip):
            self._json(429, {"ok": False, "error": "too many failed logins — wait 15 minutes"})
            return
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", "")).strip()
        user_ok = hmac.compare_digest(
            hashlib.sha256(username.encode("utf-8")).digest(),
            hashlib.sha256(s.ui_username.encode("utf-8")).digest(),
        )
        pass_ok = hmac.compare_digest(
            hashlib.sha256(password.encode("utf-8")).digest(),
            hashlib.sha256(s.ui_password.encode("utf-8")).digest(),
        )
        if not (user_ok and pass_ok):
            self._register_login_fail(ip)
            time.sleep(0.4)
            self._json(401, {"ok": False, "error": "wrong username or password"})
            return
        self._clear_login_fails(ip)
        token = make_session_token(s.ui_username, self._session_secret())
        self._json_with_cookies(200, {"ok": True, "username": s.ui_username}, self._set_session_headers(token))

    def _handle_logout(self) -> None:
        self._json_with_cookies(200, {"ok": True}, self._set_session_headers(None))

    def _handle_me(self) -> None:
        if not self._session_valid():
            self._json(401, {"ok": False, "error": "unauthorized"})
            return
        path = resolve_cookies_file(self.settings)
        self._json(
            200,
            {
                "ok": True,
                "username": self.settings.ui_username,
                "cookies": cookie_status(path),
            },
        )

    def _handle_save_cookies(self, data: dict) -> None:
        if not self._session_valid():
            self._json(401, {"ok": False, "error": "unauthorized"})
            return
        youtube = str(data.get("youtube", "") or "")
        instagram = str(data.get("instagram", "") or "")
        if not youtube.strip() and not instagram.strip():
            self._json(400, {"ok": False, "error": "paste YouTube and/or Instagram cookies.txt"})
            return
        dest = self._cookies_path()
        try:
            merged = merge_exports(load_file(dest), youtube, instagram)
            write_cookies(dest, merged)
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return
        self._json(200, {"ok": True, "cookies": cookie_status(dest)})

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

        if path == "/api/ui-me":
            self._handle_me()
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
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
            return

        if path == "/download":
            if not self._check_api_token(data):
                self._json(401, {"ok": False, "error": "unauthorized"})
                return
            self._run_download(data, default_upload_r2=True)
            return

        if path == "/api/ui-login":
            self._handle_login(data)
            return

        if path == "/api/ui-logout":
            self._handle_logout()
            return

        if path == "/api/ui-cookies":
            self._handle_save_cookies(data)
            return

        if path == "/api/ui-download":
            if not self.settings.ui_enabled:
                self._json(503, {"ok": False, "error": "UI password not configured on server"})
                return
            if not self._session_valid():
                self._json(401, {"ok": False, "error": "unauthorized"})
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
