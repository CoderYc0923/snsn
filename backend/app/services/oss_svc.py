from __future__ import annotations

import time
from pathlib import Path

import oss2

from app.config import Settings


class OssService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._auth = oss2.Auth(settings.oss_access_key_id, settings.oss_access_key_secret)
        # Public endpoint: works even when the app server is not in Beijing.
        self._bucket = oss2.Bucket(
            self._auth,
            settings.oss_endpoint,
            settings.oss_bucket,
        )

    @property
    def configured(self) -> bool:
        s = self.settings
        return bool(s.oss_access_key_id and s.oss_access_key_secret and s.oss_bucket)

    def object_key(self, job_id: str, filename: str = "audio.wav") -> str:
        prefix = self.settings.oss_prefix.rstrip("/") + "/"
        return f"{prefix}{job_id}/{filename}"

    def upload_file(self, local_path: Path, object_key: str) -> str:
        self._bucket.put_object_from_file(object_key, str(local_path))
        return object_key

    def delete(self, object_key: str) -> None:
        try:
            self._bucket.delete_object(object_key)
        except Exception:
            pass

    def signed_get_url(self, object_key: str, expires_sec: int = 3600) -> str:
        if self.settings.oss_public_base_url:
            base = self.settings.oss_public_base_url.rstrip("/")
            return f"{base}/{object_key}?t={int(time.time())}"
        return self._bucket.sign_url("GET", object_key, expires_sec)

    def public_http_url(self, object_key: str) -> str:
        """HTTPS URL for DashScope. Keep Bucket in cn-beijing for in-region pull."""
        return self.signed_get_url(object_key, expires_sec=3600)
