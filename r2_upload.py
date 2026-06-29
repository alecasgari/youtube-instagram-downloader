from __future__ import annotations

from pathlib import Path

import boto3
from botocore.config import Config

from config import Settings


def _client(settings: Settings):
    endpoint = f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_file(settings: Settings, local_path: Path, key: str, content_type: str) -> str:
    client = _client(settings)
    client.upload_file(
        str(local_path),
        settings.r2_bucket,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return key


def upload_video_assets(settings: Settings, video_id: str, mp4: Path, poster: Path) -> dict:
    prefix = settings.r2_prefix
    mp4_key = f"{prefix}/{video_id}.mp4"
    poster_key = f"{prefix}/{video_id}.jpg"

    upload_file(settings, mp4, mp4_key, "video/mp4")
    upload_file(settings, poster, poster_key, "image/jpeg")

    base = settings.r2_public_base_url
    return {
        "bucket": settings.r2_bucket,
        "mp4_key": mp4_key,
        "poster_key": poster_key,
        "mp4_url": f"{base}/{mp4_key}",
        "poster_url": f"{base}/{poster_key}",
    }
