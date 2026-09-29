from functools import lru_cache
from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SNSN_",
        extra="ignore",
    )

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    tmp_dir: Path = Path(__file__).resolve().parents[1] / "data" / "tmp"
    # Day-folder job/content cache (yesterday dirs purged on the new day).
    cache_dir: Path = Path(__file__).resolve().parents[1] / "data" / "cache"
    max_upload_mb: int = 200
    max_duration_sec: int = 1800
    api_token: str = ""
    app_password: str = "090114"

    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_endpoint: str = "https://oss-cn-beijing.aliyuncs.com"
    oss_internal_endpoint: str = "https://oss-cn-beijing-internal.aliyuncs.com"
    oss_bucket: str = ""
    oss_prefix: str = "tmp/snsn/"
    oss_public_base_url: str = ""

    dashscope_api_key: str = ""
    asr_model: str = "fun-asr"
    # Flash: word-level JSON is output-heavy; plus/thinking modes are too slow.
    translate_model: str = "deepseek-v4-flash"
    enable_translate: bool = True
    # Contiguous mini-batches keep local context for natural CN;
    # concurrency parallelizes across batches (not one isolated cue).
    translate_batch_items: int = 6
    translate_batch_chars: int = 420
    translate_concurrency: int = 6
    translate_timeout_sec: int = 90
    # Optional Netscape cookies.txt (with SESSDATA) to bypass Bilibili 412 / login walls.
    bilibili_cookie_file: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
