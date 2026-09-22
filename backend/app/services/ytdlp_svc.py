from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

ProgressFn = Callable[[float, str], None]

_BILI_HOSTS = {"bilibili.com", "www.bilibili.com", "m.bilibili.com", "b23.tv", "www.b23.tv"}


def ytdlp_available() -> bool:
    try:
        import yt_dlp  # noqa: F401

        return True
    except ImportError:
        return False


def normalize_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        raise ValueError("链接为空")
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    return raw


def is_bilibili_url(url: str) -> bool:
    try:
        parsed = urlparse(normalize_url(url))
    except Exception:
        return False
    host = (parsed.hostname or "").lower()
    if host in _BILI_HOSTS:
        return True
    return host.endswith(".bilibili.com")


def download_bilibili_audio(
    url: str,
    out_dir: Path,
    *,
    on_progress: ProgressFn | None = None,
) -> tuple[Path, str]:
    """Download best audio from a Bilibili URL into out_dir. Returns (path, title)."""
    if not ytdlp_available():
        raise RuntimeError("未安装 yt-dlp，无法解析 B 站链接")
    if not is_bilibili_url(url):
        raise ValueError("仅支持 B 站链接（bilibili.com / b23.tv）")

    import yt_dlp

    out_dir.mkdir(parents=True, exist_ok=True)
    url = normalize_url(url)
    title_box: dict[str, str] = {"title": "B站音频"}

    def hook(d: dict) -> None:
        if not on_progress:
            return
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            if total:
                pct = max(0.0, min(1.0, done / total))
                on_progress(0.02 + 0.08 * pct, "download")
            else:
                on_progress(0.05, "download")
        elif status == "finished":
            on_progress(0.09, "download")

    opts: dict = {
        "format": "bestaudio/best",
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "progress_hooks": [hook],
        # Prefer keeping a single audio file; ffmpeg may remux if needed.
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "0",
            }
        ],
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if not info:
            raise RuntimeError("无法解析该 B 站链接")
        if "entries" in info:
            entries = [e for e in (info.get("entries") or []) if e]
            if not entries:
                raise RuntimeError("该链接没有可下载的分 P")
            info = entries[0]
        title = str(info.get("title") or title_box["title"]).strip() or "B站音频"
        title_box["title"] = title

        requested = info.get("requested_downloads") or []
        path: Path | None = None
        if requested:
            fp = requested[0].get("filepath")
            if fp:
                path = Path(fp)
        if path is None:
            prepared = Path(ydl.prepare_filename(info))
            # After FFmpegExtractAudio, extension becomes m4a.
            candidates = [
                prepared.with_suffix(".m4a"),
                prepared.with_suffix(".mp3"),
                prepared,
            ]
            for c in candidates:
                if c.exists():
                    path = c
                    break
        if path is None or not path.exists():
            # Fallback: any new media file in out_dir
            media = sorted(
                [
                    p
                    for p in out_dir.iterdir()
                    if p.suffix.lower() in {".m4a", ".mp3", ".webm", ".m4b", ".ogg", ".wav"}
                ],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not media:
                raise RuntimeError("下载完成但未找到音频文件")
            path = media[0]

    logger.info("bilibili downloaded path=%s title=%s", path, title_box["title"])
    if on_progress:
        on_progress(0.1, "download")
    return path, title_box["title"]
