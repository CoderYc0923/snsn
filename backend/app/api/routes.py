from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile

from app.config import Settings, get_settings
from app.jobs.manager import JobManager, get_job_manager
from app.schemas import AuthVerifyRequest, AuthVerifyResponse, HealthResponse, JobInfo
from app.services.ffmpeg_svc import ffmpeg_available

router = APIRouter()


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
    if suffix not in {
        ".mp4",
        ".mov",
        ".m4v",
        ".webm",
        ".mkv",
        ".mp3",
        ".wav",
        ".m4a",
        ".aac",
        ".flac",
        ".ogg",
    }:
        raise HTTPException(status_code=400, detail=f"不支持的格式: {suffix}")

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

    return manager.create(staging)


@router.get("/jobs/{job_id}", response_model=JobInfo, dependencies=[Depends(require_token)])
def get_job(job_id: str, manager: JobManager = Depends(get_job_manager)) -> JobInfo:
    job = manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


@router.delete("/jobs/{job_id}", response_model=JobInfo, dependencies=[Depends(require_token)])
def cancel_job(job_id: str, manager: JobManager = Depends(get_job_manager)) -> JobInfo:
    job = manager.cancel(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job
