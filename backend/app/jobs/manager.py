from __future__ import annotations

import threading
from pathlib import Path

from app.config import Settings, get_settings
from app.schemas import JobInfo, JobStatus
from app.services.pipeline import TranscribePipeline, new_job_id
from app.services.ytdlp_svc import download_bilibili_audio, is_bilibili_url, normalize_url


class JobManager:
    """In-memory single-worker queue for 2GB box."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._jobs: dict[str, JobInfo] = {}
        self._uploads: dict[str, Path] = {}
        self._urls: dict[str, str] = {}
        self._media: dict[str, Path] = {}
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._queue: list[str] = []
        self._running_id: str | None = None
        self._worker = threading.Thread(target=self._loop, daemon=True)
        self._worker.start()
        self.settings.tmp_dir.mkdir(parents=True, exist_ok=True)

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._running_id is not None or bool(self._queue)

    def get(self, job_id: str) -> JobInfo | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    def create(self, upload_path: Path, *, title: str | None = None) -> JobInfo:
        job_id = new_job_id()
        job = JobInfo(
            id=job_id,
            status=JobStatus.queued,
            stage="queued",
            progress=0.0,
            source="upload",
            title=title,
        )
        with self._cv:
            self._jobs[job_id] = job
            self._uploads[job_id] = upload_path
            self._queue.append(job_id)
            self._cv.notify()
        return job.model_copy(deep=True)

    def create_from_url(self, url: str) -> JobInfo:
        url = normalize_url(url)
        if not is_bilibili_url(url):
            raise ValueError("仅支持 B 站链接（bilibili.com / b23.tv）")
        job_id = new_job_id()
        job = JobInfo(
            id=job_id,
            status=JobStatus.queued,
            stage="queued",
            progress=0.0,
            source="bilibili",
            title=None,
        )
        with self._cv:
            self._jobs[job_id] = job
            self._urls[job_id] = url
            self._queue.append(job_id)
            self._cv.notify()
        return job.model_copy(deep=True)

    def media_path(self, job_id: str) -> Path | None:
        with self._lock:
            path = self._media.get(job_id)
            if path and path.exists():
                return path
            return None

    def pop_media(self, job_id: str) -> Path | None:
        with self._lock:
            return self._media.pop(job_id, None)

    def cancel(self, job_id: str) -> JobInfo | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            if job.status in {JobStatus.succeeded, JobStatus.failed, JobStatus.cancelled}:
                return job.model_copy(deep=True)
            if job_id in self._queue:
                self._queue.remove(job_id)
            job.status = JobStatus.cancelled
            job.stage = "cancelled"
            path = self._uploads.pop(job_id, None)
            self._urls.pop(job_id, None)
            media = self._media.pop(job_id, None)
            if path:
                path.unlink(missing_ok=True)
            if media:
                media.unlink(missing_ok=True)
            return job.model_copy(deep=True)

    def _loop(self) -> None:
        pipeline = TranscribePipeline(self.settings)
        while True:
            with self._cv:
                while not self._queue:
                    self._cv.wait()
                job_id = self._queue.pop(0)
                job = self._jobs[job_id]
                if job.status == JobStatus.cancelled:
                    continue
                job.status = JobStatus.running
                job.stage = "starting"
                job.progress = 0.02
                self._running_id = job_id
                upload = self._uploads.get(job_id)
                url = self._urls.get(job_id)

            try:

                def on_progress(progress: float, stage: str) -> None:
                    with self._lock:
                        current = self._jobs.get(job_id)
                        if current and current.status == JobStatus.running:
                            current.progress = progress
                            current.stage = stage

                title: str | None = None
                if url:
                    on_progress(0.02, "download")
                    dl_dir = self.settings.tmp_dir / f"dl-{job_id}"
                    dl_dir.mkdir(parents=True, exist_ok=True)
                    upload, title = download_bilibili_audio(url, dl_dir, on_progress=on_progress)
                    with self._lock:
                        current = self._jobs.get(job_id)
                        if current:
                            current.title = title
                        self._uploads[job_id] = upload

                if upload is None or not upload.exists():
                    raise FileNotFoundError("音频文件已丢失")

                result, media_path = pipeline.run(
                    job, upload, on_progress, title=title or job.title
                )
                with self._lock:
                    current = self._jobs[job_id]
                    if current.status != JobStatus.cancelled:
                        current.status = JobStatus.succeeded
                        current.progress = 1.0
                        current.stage = "done"
                        current.result = result
                        if title:
                            current.title = title
                        self._media[job_id] = media_path
            except Exception as exc:  # noqa: BLE001 — surface to client
                with self._lock:
                    current = self._jobs[job_id]
                    if current.status != JobStatus.cancelled:
                        current.status = JobStatus.failed
                        current.stage = "failed"
                        current.error = str(exc)
                    media = self._media.pop(job_id, None)
                    if media:
                        media.unlink(missing_ok=True)
            finally:
                with self._lock:
                    self._uploads.pop(job_id, None)
                    self._urls.pop(job_id, None)
                    self._running_id = None
                # Clean download dir leftovers
                dl_dir = self.settings.tmp_dir / f"dl-{job_id}"
                if dl_dir.exists():
                    import shutil

                    shutil.rmtree(dl_dir, ignore_errors=True)


_manager: JobManager | None = None


def get_job_manager() -> JobManager:
    global _manager
    if _manager is None:
        _manager = JobManager()
    return _manager
