from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from app.config import Settings
from app.schemas import JobInfo, JobResult, JobStatus
from app.services.asr_svc import AsrService
from app.services.cue_split import split_cues_for_shadowing
from app.services.ffmpeg_svc import extract_wav_16k_mono, probe_duration_sec
from app.services.oss_svc import OssService
from app.services.translate_svc import TranslateService


class PipelineError(Exception):
    pass


class TranscribePipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.oss = OssService(settings)
        self.asr = AsrService(settings)
        self.translate = TranslateService(settings)

    def run(self, job: JobInfo, upload_path: Path, on_progress) -> JobResult:
        work = self.settings.tmp_dir / job.id
        work.mkdir(parents=True, exist_ok=True)
        object_key: str | None = None
        try:
            on_progress(0.1, "extract")
            duration = probe_duration_sec(upload_path)
            if duration > self.settings.max_duration_sec:
                raise PipelineError(
                    f"素材过长：{duration:.0f}s，上限 {self.settings.max_duration_sec}s"
                )

            wav_path = work / "audio.wav"
            extract_wav_16k_mono(upload_path, wav_path)

            # Drop original upload ASAP to save disk.
            try:
                upload_path.unlink(missing_ok=True)
            except OSError:
                pass

            on_progress(0.35, "upload_oss")
            if not self.oss.configured:
                raise PipelineError("OSS 未配置")
            object_key = self.oss.object_key(job.id)
            self.oss.upload_file(wav_path, object_key)
            # Internal-endpoint signed URL → Bailian pulls via Beijing intranet.
            file_url = self.oss.asr_file_url(object_key)

            on_progress(0.55, "asr")
            if not self.asr.configured:
                raise PipelineError("DashScope API Key 未配置")
            result = self.asr.transcribe_japanese(file_url)
            if result.duration_ms <= 0 and duration > 0:
                result.duration_ms = int(duration * 1000)

            on_progress(0.72, "split")
            result.cues = split_cues_for_shadowing(result.cues)

            on_progress(0.85, "translate")
            result.cues = self.translate.fill_zh(result.cues, on_progress=on_progress)

            on_progress(0.95, "cleanup")
            return result
        finally:
            if object_key:
                self.oss.delete(object_key)
            shutil.rmtree(work, ignore_errors=True)


def new_job_id() -> str:
    return uuid.uuid4().hex
