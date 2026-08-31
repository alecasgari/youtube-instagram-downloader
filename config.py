from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    token: str
    ui_username: str
    ui_password: str
    ui_secret: str
    data_dir: Path
    cookies_file: Path | None
    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket: str
    r2_prefix: str
    r2_public_base_url: str
    static_dir: Path

    @property
    def r2_configured(self) -> bool:
        return bool(
            self.r2_account_id
            and self.r2_access_key_id
            and self.r2_secret_access_key
            and self.r2_bucket
        )

    @property
    def ui_enabled(self) -> bool:
        return bool(self.ui_username and self.ui_password)


def load_settings() -> Settings:
    data_dir = Path(os.environ.get("GIV_YTDLP_DATA_DIR", "/data"))
    cookies_raw = os.environ.get("GIV_YTDLP_COOKIES_FILE", "").strip()
    cookies_file = Path(cookies_raw) if cookies_raw else None
    if cookies_file is None:
        default_cookies = data_dir / "cookies.txt"
        if default_cookies.is_file():
            cookies_file = default_cookies

    app_dir = Path(__file__).resolve().parent
    static_dir = app_dir / "static"

    return Settings(
        host=os.environ.get("GIV_YTDLP_HOST", "0.0.0.0"),
        port=int(os.environ.get("GIV_YTDLP_PORT", "9876")),
        token=os.environ.get("GIV_YTDLP_TOKEN", "").strip(),
        ui_username=os.environ.get("GIV_YTDLP_UI_USERNAME", "").strip(),
        ui_password=os.environ.get("GIV_YTDLP_UI_PASSWORD", "").strip(),
        ui_secret=os.environ.get("GIV_YTDLP_UI_SECRET", "").strip(),
        data_dir=data_dir,
        cookies_file=cookies_file,
        r2_account_id=os.environ.get("R2_ACCOUNT_ID", "").strip(),
        r2_access_key_id=os.environ.get("R2_ACCESS_KEY_ID", "").strip(),
        r2_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY", "").strip(),
        r2_bucket=os.environ.get("R2_BUCKET", "givsharifi-videos").strip(),
        r2_prefix=os.environ.get("R2_PREFIX", "library").strip().strip("/"),
        r2_public_base_url=os.environ.get(
            "R2_PUBLIC_BASE_URL", "https://media.givsharifi.com"
        ).rstrip("/"),
        static_dir=static_dir,
    )


def resolve_cookies_file(settings: Settings) -> Path | None:
    """Find cookies at request time (file may be copied after container start)."""
    if settings.cookies_file and settings.cookies_file.is_file():
        return settings.cookies_file
    default = settings.data_dir / "cookies.txt"
    if default.is_file():
        return default
    return None
