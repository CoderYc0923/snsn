from __future__ import annotations

import threading
from pathlib import Path

from app.config import Settings, get_settings
from app.schemas import JobInfo, JobStatus
from app.services.pipeline import TranscribePipeline, new_job_id


class JobManager:
    """In-memory single-worker queue for 2GB box."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._jobs: dict[str, JobInfo] = {}
        self._uploads: dict[str, Path] = {}
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

    def create(self, upload_path: Path) -> JobInfo:
        job_id = new_job_id()
        job = JobInfo(id=job_id, status=JobStatus.queued, stage="queued", progress=0.0)
        with self._cv:
            if self._running_id is not None or self._queue:
                # Still accept but queue; one at a time.
                pass
            self._jobs[job_id] = job
            self._uploads[job_id] = upload_path
            self._queue.append(job_id)
            self._cv.notify()
        return job.model_copy(deep=True)

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
            if path:
                path.unlink(missing_ok=True)
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
                job.progress = 0.05
                self._running_id = job_id
                upload = self._uploads.get(job_id)

            try:
                if upload is None or not upload.exists():
                    raise FileNotFoundError("上传文件已丢失")

                def on_progress(progress: float, stage: str) -> None:
                    with self._lock:
                        current = self._jobs.get(job_id)
                        if current and current.status == JobStatus.running:
                            current.progress = progress
                            current.stage = stage

                result = pipeline.run(job, upload, on_progress)
                with self._lock:
                    current = self._jobs[job_id]
                    if current.status != JobStatus.cancelled:
                        current.status = JobStatus.succeeded
                        current.progress = 1.0
                        current.stage = "done"
                        current.result = result
            except Exception as exc:  # noqa: BLE001 — surface to client
                with self._lock:
                    current = self._jobs[job_id]
                    if current.status != JobStatus.cancelled:
                        current.status = JobStatus.failed
                        current.stage = "failed"
                        current.error = str(exc)
            finally:
                with self._lock:
                    self._uploads.pop(job_id, None)
                    self._running_id = None


_manager: JobManager | None = None


def get_job_manager() -> JobManager:
    global _manager
    if _manager is None:
        _manager = JobManager()
    return _manager
