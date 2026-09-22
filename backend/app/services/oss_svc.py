from __future__ import annotations

from pathlib import Path

import oss2

from app.config import Settings


class OssService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._auth = oss2.Auth(settings.oss_access_key_id, settings.oss_access_key_secret)
        # Public endpoint: app server may be outside Beijing (upload over Internet).
        self._bucket = oss2.Bucket(
            self._auth,
            settings.oss_endpoint,
            settings.oss_bucket,
        )
        # Internal endpoint: only for URLs consumed by Aliyun Beijing services (Bailian).
        self._internal_bucket = oss2.Bucket(
            self._auth,
            settings.oss_internal_endpoint or settings.oss_endpoint,
            settings.oss_bucket,
            is_cname=False,
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

    def asr_file_url(self, object_key: str, expires_sec: int = 3600) -> str:
        """HTTPS URL for Paraformer to download the object.

        Prefer the Beijing *internal* endpoint so Bailian (cn-beijing) pulls over
        Aliyun intranet (no OSS 外网流出). Do not open this URL from your
        non-Beijing app server — it is only for Bailian.
        """
        if self.settings.oss_public_base_url:
            # Escape hatch: force public-endpoint signed URL (外网流出).
            return self._bucket.sign_url("GET", object_key, expires_sec)

        url = self._internal_bucket.sign_url("GET", object_key, expires_sec)
        # oss2 may return http:// for internal; normalize to https.
        if url.startswith("http://"):
            url = "https://" + url[len("http://") :]
        return url
