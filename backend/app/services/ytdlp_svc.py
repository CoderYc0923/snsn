from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

ProgressFn = Callable[[float, str], None]

_BILI_HOSTS = {
    "bilibili.com",
    "www.bilibili.com",
    "m.bilibili.com",
    "b23.tv",
    "www.b23.tv",
    "bili2233.cn",
    "bili22.cn",
    "bili23.cn",
    "bili33.cn",
    "bili2233.com",
}

# Full URL in share text (App often wraps Chinese + link).
_URL_RE = re.compile(
    r"https?://(?:(?:www|m)\.)?(?:bilibili\.com|b23\.tv|bili2233\.cn|bili22\.cn|bili23\.cn|bili33\.cn)/[^\s<>\"'】）\]【（(]+",
    re.I,
)
_BARE_RE = re.compile(
    r"(?:(?:www|m)\.)?(?:bilibili\.com|b23\.tv)/[^\s<>\"'】）\]【（(]+",
    re.I,
)
_BV_RE = re.compile(r"\b(BV[\w]+)\b")
_AV_RE = re.compile(r"\b[Aa][Vv](\d+)\b")


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
    # Strip trailing punctuation common in share text.
    return raw.rstrip(".,;，。；!！?？、\"'")


def extract_bilibili_url(text: str) -> str:
    """Pull a playable Bilibili URL out of App share paste / short links / BV id."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("链接为空")

    # bilibili://video/<aid or bvid>
    deep = re.search(r"bilibili://video/([\w]+)", raw, re.I)
    if deep:
        token = deep.group(1)
        if token.upper().startswith("BV"):
            return f"https://www.bilibili.com/video/{token}"
        if token.isdigit():
            return f"https://www.bilibili.com/video/av{token}"

    m = _URL_RE.search(raw)
    if m:
        return normalize_url(m.group(0))

    m = _BARE_RE.search(raw)
    if m:
        return normalize_url(m.group(0))

    bv = _BV_RE.search(raw)
    if bv:
        return f"https://www.bilibili.com/video/{bv.group(1)}"

    av = _AV_RE.search(raw)
    if av:
        return f"https://www.bilibili.com/video/av{av.group(1)}"

    # Entire field is already a URL.
    if "bilibili" in raw.lower() or "b23.tv" in raw.lower():
        return normalize_url(raw.split()[0] if " " in raw else raw)

    raise ValueError("未识别到 B 站链接，请粘贴 bilibili.com / b23.tv 或含 BV 号的分享内容")


def is_bilibili_url(url: str) -> bool:
    try:
        parsed = urlparse(extract_bilibili_url(url))
    except Exception:
        return False
    host = (parsed.hostname or "").lower()
    if host in _BILI_HOSTS:
        return True
    return host.endswith(".bilibili.com") or host.endswith(".b23.tv")


def download_bilibili_video(
    url: str,
    out_dir: Path,
    *,
    on_progress: ProgressFn | None = None,
) -> tuple[Path, str]:
    """Download a Bilibili video (≤720p mp4 when possible). Returns (path, title)."""
    if not ytdlp_available():
        raise RuntimeError("未安装 yt-dlp，无法解析 B 站链接")

    url = extract_bilibili_url(url)
    if not is_bilibili_url(url):
        raise ValueError("仅支持 B 站链接（bilibili.com / b23.tv）")

    import yt_dlp

    out_dir.mkdir(parents=True, exist_ok=True)
    title_box: dict[str, str] = {"title": "B站视频"}

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
        # Prefer merged mp4 around 720p to keep size reasonable on light VMs.
        "format": (
            "bv*[height<=720][ext=mp4]+ba[ext=m4a]/"
            "bv*[height<=720]+ba/"
            "b[height<=720][ext=mp4]/"
            "b[height<=720]/best"
        ),
        "merge_output_format": "mp4",
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "progress_hooks": [hook],
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
        title = str(info.get("title") or title_box["title"]).strip() or "B站视频"
        title_box["title"] = title

        requested = info.get("requested_downloads") or []
        path: Path | None = None
        if requested:
            fp = requested[-1].get("filepath") or requested[0].get("filepath")
            if fp:
                path = Path(fp)
        if path is None:
            prepared = Path(ydl.prepare_filename(info))
            candidates = [
                prepared.with_suffix(".mp4"),
                prepared.with_suffix(".mkv"),
                prepared.with_suffix(".webm"),
                prepared.with_suffix(".flv"),
                prepared,
            ]
            for c in candidates:
                if c.exists():
                    path = c
                    break
        if path is None or not path.exists():
            media = sorted(
                [
                    p
                    for p in out_dir.iterdir()
                    if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".flv", ".m4v"}
                ],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not media:
                raise RuntimeError("下载完成但未找到视频文件")
            path = media[0]

    logger.info("bilibili video downloaded path=%s title=%s", path, title_box["title"])
    if on_progress:
        on_progress(0.1, "download")
    return path, title_box["title"]


# Back-compat alias
download_bilibili_audio = download_bilibili_video
