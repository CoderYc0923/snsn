from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse

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

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com",
    "Origin": "https://www.bilibili.com",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def ytdlp_available() -> bool:
    """True when Bilibili import can run (httpx is enough; yt-dlp optional)."""
    try:
        import httpx  # noqa: F401

        return True
    except ImportError:
        return False


def normalize_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        raise ValueError("链接为空")
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    return raw.rstrip(".,;，。；!！?？、\"'")


def extract_bilibili_url(text: str) -> str:
    """Pull a playable Bilibili URL out of App share paste / short links / BV id."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("链接为空")

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


def _is_short_host(host: str) -> bool:
    host = host.lower()
    return host in {
        "b23.tv",
        "www.b23.tv",
        "bili2233.cn",
        "bili22.cn",
        "bili23.cn",
        "bili33.cn",
        "bili2233.com",
    }


def expand_bilibili_url(url: str) -> str:
    """Follow b23.tv / share short links to a canonical bilibili.com/video/... URL."""
    url = extract_bilibili_url(url)
    host = (urlparse(url).hostname or "").lower()
    if not _is_short_host(host) and "bilibili.com" in host:
        return url

    try:
        import httpx

        with httpx.Client(
            follow_redirects=True,
            timeout=20.0,
            headers=_BROWSER_HEADERS,
        ) as client:
            resp = client.get(url)
            final = str(resp.url)
            logger.info("expanded bilibili short url %s -> %s", url, final)
            bv = _BV_RE.search(final)
            if bv:
                qs = urlparse(final).query
                p = parse_qs(qs).get("p", [None])[0]
                base = f"https://www.bilibili.com/video/{bv.group(1)}"
                return f"{base}?p={p}" if p and p != "1" else base
            return final
    except Exception as exc:
        logger.warning("expand short url failed (%s), keep original: %s", exc, url)
        return url


def parse_bvid_and_page(url: str) -> tuple[str, int]:
    """Public wrapper: return (BVxxx|avN, page)."""
    return _parse_bvid_and_page(url)


def _parse_bvid_and_page(url: str) -> tuple[str, int]:
    url = expand_bilibili_url(url)
    parsed = urlparse(url)
    bv_m = _BV_RE.search(url)
    av_m = _AV_RE.search(url)
    page = 1
    qs = parse_qs(parsed.query)
    if qs.get("p"):
        try:
            page = max(1, int(qs["p"][0]))
        except ValueError:
            page = 1

    if bv_m:
        return bv_m.group(1), page
    if av_m:
        # Resolve avid -> bvid via cards-compatible endpoint later; store as avN token.
        return f"av{av_m.group(1)}", page
    raise ValueError("链接中未找到 BV/AV 号")


def _cookie_file() -> str | None:
    try:
        from app.config import get_settings

        raw = (get_settings().bilibili_cookie_file or "").strip()
    except Exception:
        return None
    if not raw:
        return None
    path = Path(raw)
    if not path.is_file():
        logger.warning("SNSN_BILIBILI_COOKIE_FILE not found: %s", path)
        return None
    return str(path)


def _load_netscape_cookies(path: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    try:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        logger.warning("read cookie file failed: %s", exc)
        return cookies
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, _flag, _path, _secure, _expiry, name, value = parts[:7]
        if "bilibili" not in domain.lower():
            continue
        cookies[name] = value
    return cookies


def _bili_session():
    import httpx

    client = httpx.Client(
        headers=_BROWSER_HEADERS,
        follow_redirects=True,
        timeout=httpx.Timeout(30.0, connect=15.0),
    )
    # Warm up + anonymous buvid (needed by playurl / cards).
    try:
        client.get("https://www.bilibili.com")
        spi = client.get("https://api.bilibili.com/x/frontend/finger/spi")
        if spi.status_code == 200:
            data = (spi.json() or {}).get("data") or {}
            if data.get("b_3"):
                client.cookies.set("buvid3", data["b_3"], domain=".bilibili.com")
            if data.get("b_4"):
                client.cookies.set("buvid4", data["b_4"], domain=".bilibili.com")
    except Exception as exc:
        logger.warning("bilibili session warmup failed: %s", exc)

    cookie_path = _cookie_file()
    if cookie_path:
        for name, value in _load_netscape_cookies(cookie_path).items():
            client.cookies.set(name, value, domain=".bilibili.com")
        logger.info("loaded bilibili cookies from %s", cookie_path)
    return client


_LOGIN_HINT = (
    "该链接需要登录或大会员才能下载。"
    "请换公开可播的稿件，或在服务器配置 SNSN_BILIBILI_COOKIE_FILE（含 SESSDATA）后重试。"
)

_LOGIN_MSG_RE = re.compile(
    r"登录|登入|大会员|会员专享|付费|充电专属|权限不足|access.?denied|login|vip|premium",
    re.I,
)


def _looks_like_login_wall(code: object, message: object) -> bool:
    if code in (-403, 403, -10403, 87007, 87008, -105):
        return True
    return bool(_LOGIN_MSG_RE.search(str(message or "")))


def _api_get(client, url: str, *, params: dict | None = None) -> dict:
    resp = client.get(url, params=params)
    if resp.status_code == 412:
        raise RuntimeError(_LOGIN_HINT)
    resp.raise_for_status()
    # Some risk-control pages return HTML 200 with challenge body.
    ctype = (resp.headers.get("content-type") or "").lower()
    if "json" not in ctype and not resp.text.lstrip().startswith("{"):
        raise RuntimeError("B站接口返回异常页面，请稍后重试或配置 Cookie")
    payload = resp.json()
    code = payload.get("code")
    message = payload.get("message") or ""
    if _looks_like_login_wall(code, message):
        raise RuntimeError(_LOGIN_HINT)
    if code not in (0, None):
        raise RuntimeError(f"B站接口错误 code={code}: {message or payload}")
    return payload


def _fetch_title_via_cards(client, *, bvid: str | None = None, aid: str | None = None) -> str | None:
    """Best-effort title from cards API."""
    try:
        if bvid:
            cards = _api_get(
                client,
                "https://api.bilibili.com/x/article/cards",
                params={"ids": bvid, "from": "bvid"},
            )
            data = (cards.get("data") or {}).get(bvid) or {}
            return (data.get("title") or "").strip() or None
        if aid:
            cards = _api_get(
                client,
                "https://api.bilibili.com/x/article/cards",
                params={"ids": aid},
            )
            data = (cards.get("data") or {}).get(str(aid)) or {}
            return (data.get("title") or "").strip() or None
    except Exception as exc:
        logger.warning("cards API failed (non-fatal): %s", exc)
    return None


def _resolve_meta(client, token: str, page: int) -> tuple[str, int, str, dict]:
    """Return (file_id, cid, title, play_ids) where play_ids is {bvid|aid} for playurl."""
    play_ids: dict[str, str]
    title: str | None = None

    if token.lower().startswith("av"):
        aid = token[2:]
        play_ids = {"aid": aid}
        title = _fetch_title_via_cards(client, aid=aid)
        file_id = f"av{aid}"
        pages_payload = _api_get(
            client,
            "https://api.bilibili.com/x/player/pagelist",
            params={"aid": aid},
        )
    else:
        bvid = token
        play_ids = {"bvid": bvid}
        title = _fetch_title_via_cards(client, bvid=bvid)
        file_id = bvid
        pages_payload = _api_get(
            client,
            "https://api.bilibili.com/x/player/pagelist",
            params={"bvid": bvid},
        )

    pages = pages_payload.get("data") or []
    if not pages:
        raise RuntimeError("该视频没有可播放分 P")
    idx = min(max(page, 1), len(pages)) - 1
    part = pages[idx]
    cid = int(part["cid"])
    part_title = (part.get("part") or "").strip()
    if not title:
        title = part_title or file_id
    elif len(pages) > 1 and part_title:
        title = f"{title} - P{idx + 1} {part_title}"
    return file_id, cid, title, play_ids


def _pick_play_url(client, play_ids: dict[str, str], cid: int) -> tuple[str, int]:
    """Prefer single-file mp4 ≤720p (qn=64). Returns (media_url, size_hint)."""
    last_err: Exception | None = None
    saw_login_wall = False
    last_api_msg = ""

    for qn in (64, 32, 16):
        try:
            resp = client.get(
                "https://api.bilibili.com/x/player/playurl",
                params={
                    **play_ids,
                    "cid": cid,
                    "qn": qn,
                    "fnval": 1,
                    "fourk": 0,
                },
            )
            if resp.status_code == 412:
                raise RuntimeError(_LOGIN_HINT)
            resp.raise_for_status()
            if not resp.text.lstrip().startswith("{"):
                raise RuntimeError("B站接口返回异常页面，请稍后重试或配置 Cookie")
            payload = resp.json()
            code = payload.get("code")
            message = payload.get("message") or ""
            last_api_msg = str(message)
            if _looks_like_login_wall(code, message):
                saw_login_wall = True
                last_err = RuntimeError(_LOGIN_HINT)
                continue
            if code not in (0, None):
                last_err = RuntimeError(f"B站接口错误 code={code}: {message or payload}")
                continue
            data = payload.get("data") or {}
            durl = data.get("durl") or []
            if not durl:
                # code=0 but no stream is typical for login/paywalled playback.
                saw_login_wall = True
                continue
            item = durl[0]
            url = item.get("url") or (item.get("backup_url") or [None])[0]
            if not url:
                saw_login_wall = True
                continue
            size = int(item.get("size") or 0)
            logger.info("bilibili playurl qn=%s size=%s", data.get("quality") or qn, size)
            return url, size
        except RuntimeError as exc:
            last_err = exc
            if _LOGIN_MSG_RE.search(str(exc)) or "412" in str(exc):
                saw_login_wall = True
            logger.warning("playurl qn=%s failed: %s", qn, exc)
        except Exception as exc:
            last_err = exc
            logger.warning("playurl qn=%s failed: %s", qn, exc)

    if saw_login_wall:
        raise RuntimeError(_LOGIN_HINT)
    if last_err:
        msg = str(last_err)
        if _LOGIN_MSG_RE.search(msg) or "412" in msg:
            raise RuntimeError(_LOGIN_HINT) from last_err
        raise last_err
    hint = f"（{last_api_msg}）" if last_api_msg else ""
    raise RuntimeError(f"无法获取视频播放地址{hint}。{_LOGIN_HINT}")


def _download_stream(
    client,
    url: str,
    dest: Path,
    *,
    size_hint: int = 0,
    on_progress: ProgressFn | None = None,
) -> None:
    with client.stream("GET", url, headers={**_BROWSER_HEADERS, "Referer": "https://www.bilibili.com"}) as resp:
        if resp.status_code == 412:
            raise RuntimeError(_LOGIN_HINT)
        if resp.status_code in (401, 403):
            raise RuntimeError(_LOGIN_HINT)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length") or size_hint or 0)
        done = 0
        with dest.open("wb") as f:
            for chunk in resp.iter_bytes(chunk_size=256 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                done += len(chunk)
                if on_progress and total > 0:
                    pct = max(0.0, min(1.0, done / total))
                    on_progress(0.02 + 0.08 * pct, "download")
                elif on_progress:
                    on_progress(0.05, "download")


def download_bilibili_video(
    url: str,
    out_dir: Path,
    *,
    on_progress: ProgressFn | None = None,
) -> tuple[Path, str]:
    """Download a Bilibili video (≤720p mp4 when possible). Returns (path, title).

    Uses official playurl/cards APIs (avoids webpage 412 that breaks yt-dlp).
    """
    if not ytdlp_available():
        raise RuntimeError("缺少 httpx，无法解析 B 站链接")

    if not is_bilibili_url(url):
        raise ValueError("仅支持 B 站链接（bilibili.com / b23.tv）")

    token, page = _parse_bvid_and_page(url)
    out_dir.mkdir(parents=True, exist_ok=True)

    if on_progress:
        on_progress(0.02, "download")

    client = _bili_session()
    try:
        file_id, cid, title, play_ids = _resolve_meta(client, token, page)
        if on_progress:
            on_progress(0.03, "download")
        media_url, size_hint = _pick_play_url(client, play_ids, cid)
        dest = out_dir / f"{file_id}_p{page}.mp4"
        _download_stream(
            client,
            media_url,
            dest,
            size_hint=size_hint,
            on_progress=on_progress,
        )
    finally:
        client.close()

    if not dest.exists() or dest.stat().st_size < 1024:
        raise RuntimeError("下载完成但视频文件无效")

    logger.info("bilibili video downloaded path=%s title=%s", dest, title)
    if on_progress:
        on_progress(0.1, "download")
    return dest, title


# Back-compat alias
download_bilibili_audio = download_bilibili_video
