from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import Settings, get_settings
from app.jobs.manager import JobManager, get_job_manager
from app.schemas import (
    AuthVerifyRequest,
    AuthVerifyResponse,
    CreateUrlJobRequest,
    HealthResponse,
    JobInfo,
)
from app.services.ffmpeg_svc import ffmpeg_available
from app.services.ytdlp_svc import extract_bilibili_url, is_bilibili_url, ytdlp_available

router = APIRouter()

_AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
_VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
_MEDIA_SUFFIXES = _AUDIO_SUFFIXES | _VIDEO_SUFFIXES


def _media_kind_for_suffix(suffix: str) -> str:
    return "video" if suffix in _VIDEO_SUFFIXES else "audio"


def require_token(
    settings: Settings = Depends(get_settings),
    x_snsn_token: str | None = Header(default=None),
) -> None:
    if not settings.api_token:
        return
    if x_snsn_token != settings.api_token:
        raise HTTPException(status_code=401, detail="unauthorized")


@router.post("/auth/verify", response_model=AuthVerifyResponse)
def verify_access(
    body: AuthVerifyRequest,
    settings: Settings = Depends(get_settings),
) -> AuthVerifyResponse:
    if body.password != settings.app_password:
        raise HTTPException(status_code=401, detail="密码错误")
    token = settings.api_token or "ok"
    return AuthVerifyResponse(ok=True, token=token)


@router.get("/health", response_model=HealthResponse)
def health(
    settings: Settings = Depends(get_settings),
    manager: JobManager = Depends(get_job_manager),
) -> HealthResponse:
    return HealthResponse(
        ok=True,
        ffmpeg=ffmpeg_available(),
        ytdlp=ytdlp_available(),
        oss_configured=bool(
            settings.oss_access_key_id and settings.oss_access_key_secret and settings.oss_bucket
        ),
        asr_configured=bool(settings.dashscope_api_key),
        busy=manager.busy,
        detail={
            "oss_endpoint": settings.oss_endpoint,
            "asr_model": settings.asr_model,
            "tmp_dir": str(settings.tmp_dir),
        },
    )


@router.post("/jobs", response_model=JobInfo, dependencies=[Depends(require_token)])
async def create_job(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    manager: JobManager = Depends(get_job_manager),
) -> JobInfo:
    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少文件名")

    suffix = Path(file.filename).suffix.lower() or ".bin"
    if suffix not in _MEDIA_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail="不支持的格式，请上传音频（mp3/m4a/wav…）或视频（mp4/webm/mov…）",
        )

    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    staging = settings.tmp_dir / f"upload-{uuid.uuid4().hex}{suffix}"

    size = 0
    try:
        with staging.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(status_code=413, detail="文件过大")
                out.write(chunk)
    except HTTPException:
        staging.unlink(missing_ok=True)
        raise
    except Exception:
        staging.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    title = Path(file.filename).stem.strip() or None
    return manager.create(staging, title=title, media_kind=_media_kind_for_suffix(suffix))


@router.post("/jobs/url", response_model=JobInfo, dependencies=[Depends(require_token)])
def create_job_from_url(
    body: CreateUrlJobRequest,
    manager: JobManager = Depends(get_job_manager),
) -> JobInfo:
    if not ytdlp_available():
        raise HTTPException(status_code=503, detail="服务器未安装 yt-dlp，无法解析 B 站链接")
    try:
        url = extract_bilibili_url(body.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not is_bilibili_url(url):
        raise HTTPException(status_code=400, detail="仅支持 B 站链接（bilibili.com / b23.tv）")
    try:
        return manager.create_from_url(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs/{job_id}", response_model=JobInfo, dependencies=[Depends(require_token)])
def get_job(job_id: str, manager: JobManager = Depends(get_job_manager)) -> JobInfo:
    job = manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


@router.get("/jobs/{job_id}/media", dependencies=[Depends(require_token)])
def get_job_media(job_id: str, manager: JobManager = Depends(get_job_manager)):
    job = manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status.value != "succeeded":
        raise HTTPException(status_code=409, detail="任务尚未完成，无法下载音频")
    path = manager.media_path(job_id)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="音频已过期或不存在")
    media_type = {
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".opus": "audio/opus",
        ".flac": "audio/flac",
        ".mp4": "video/mp4",
        ".m4v": "video/mp4",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
        ".mov": "video/quicktime",
    }.get(path.suffix.lower(), "application/octet-stream")
    filename = f"{(job.title or 'snsn-media').strip()}{path.suffix}"
    return FileResponse(
        path,
        media_type=media_type,
        filename=filename,
        background=None,
    )


@router.delete("/jobs/{job_id}", response_model=JobInfo, dependencies=[Depends(require_token)])
def cancel_job(job_id: str, manager: JobManager = Depends(get_job_manager)) -> JobInfo:
    job = manager.cancel(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job
