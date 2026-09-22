from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class CueWord(BaseModel):
    text: str
    furigana: str | None = None
    romaji: str | None = None
    tone: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None


class Cue(BaseModel):
    id: str
    start_ms: int
    end_ms: int
    text: str
    translation: str = ""
    words: list[CueWord] = Field(default_factory=list)


class JobResult(BaseModel):
    version: int = 1
    source_lang: str = "ja"
    target_lang: str = "zh-CN"
    duration_ms: int = 0
    title: str | None = None
    cues: list[Cue] = Field(default_factory=list)


class JobInfo(BaseModel):
    id: str
    status: JobStatus
    progress: float = 0.0
    stage: str = "queued"
    error: str | None = None
    result: JobResult | None = None
    source: str = "upload"  # upload | bilibili
    title: str | None = None


class CreateUrlJobRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)


class AuthVerifyRequest(BaseModel):
    password: str = Field(min_length=6, max_length=6)


class AuthVerifyResponse(BaseModel):
    ok: bool = True
    token: str = ""


class HealthResponse(BaseModel):
    ok: bool = True
    ffmpeg: bool = False
    ytdlp: bool = False
    oss_configured: bool = False
    asr_configured: bool = False
    busy: bool = False
    detail: dict[str, Any] = Field(default_factory=dict)
