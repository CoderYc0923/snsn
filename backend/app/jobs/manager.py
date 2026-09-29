from __future__ import annotations

import logging
import shutil
import threading
import time
from pathlib import Path

from app.config import Settings, get_settings
from app.schemas import JobInfo, JobStatus
from app.services.job_cache import (
    JobCacheStore,
    content_key_for_bilibili,
    content_key_for_file,
    sha256_file,
)
from app.services.pipeline import TranscribePipeline, new_job_id
from app.services.ytdlp_svc import (
    download_bilibili_video,
    expand_bilibili_url,
    extract_bilibili_url,
    is_bilibili_url,
    parse_bvid_and_page,
)

logger = logging.getLogger(__name__)


class JobManager:
    """Single-worker queue with day-folder disk cache (purge yesterday on new day)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.cache = JobCacheStore(self.settings.cache_dir)
        self._jobs: dict[str, JobInfo] = {}
        self._uploads: dict[str, Path] = {}
        self._urls: dict[str, str] = {}
        self._media: dict[str, Path] = {}
        self._content_keys: dict[str, str] = {}
        self._job_days: dict[str, str] = {}
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._queue: list[str] = []
        self._running_id: str | None = None
        self.settings.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.settings.cache_dir.mkdir(parents=True, exist_ok=True)

        self.cache.purge_before_today()
        self._restore_today()

        self._worker = threading.Thread(target=self._loop, daemon=True, name="snsn-jobs")
        self._worker.start()
        self._janitor = threading.Thread(target=self._janitor_loop, daemon=True, name="snsn-cache-janitor")
        self._janitor.start()

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._running_id is not None or bool(self._queue)

    def _janitor_loop(self) -> None:
        while True:
            try:
                self.cache.purge_before_today()
            except Exception:
                logger.exception("cache purge failed")
            time.sleep(3600)

    def _restore_today(self) -> None:
        for job_id in self.cache.list_today_job_ids():
            loaded = self.cache.load_job(job_id)
            if not loaded:
                continue
            job, raw, jdir = loaded
            with self._lock:
                self._jobs[job_id] = job
                media = self.cache.media_in_job_dir(jdir)
                if media:
                    self._media[job_id] = media
                if raw.get("content_key"):
                    self._content_keys[job_id] = str(raw["content_key"])
                if raw.get("source_url"):
                    self._urls[job_id] = str(raw["source_url"])
                source = self.cache.source_in_job_dir(jdir)
                if source:
                    self._uploads[job_id] = source

            if job.status in {JobStatus.queued, JobStatus.running}:
                # Mid-flight jobs cannot resume pipeline safely after process restart.
                if job.status == JobStatus.running:
                    job.status = JobStatus.failed
                    job.stage = "failed"
                    job.error = "服务器重启，任务中断，请重试"
                    self._persist(job_id)
                    continue
                with self._cv:
                    if job_id not in self._queue:
                        self._queue.append(job_id)
                        self._cv.notify()
                logger.info("restored queued job %s", job_id)

    def _persist(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            media = self._media.get(job_id)
            upload = self._uploads.get(job_id)
            url = self._urls.get(job_id)
            content_key = self._content_keys.get(job_id)
            snapshot = job.model_copy(deep=True)
        try:
            self.cache.save_job(
                snapshot,
                content_key=content_key,
                source_url=url,
                media_path=media,
                source_path=upload if snapshot.source == "upload" else None,
            )
        except Exception:
            logger.exception("persist job failed id=%s", job_id)

    def get(self, job_id: str) -> JobInfo | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                return job.model_copy(deep=True)
        loaded = self.cache.load_job(job_id)
        if not loaded:
            return None
        job, raw, jdir = loaded
        with self._lock:
            self._jobs[job_id] = job
            media = self.cache.media_in_job_dir(jdir)
            if media:
                self._media[job_id] = media
            if raw.get("content_key"):
                self._content_keys[job_id] = str(raw["content_key"])
        return job.model_copy(deep=True)

    def _hit_content(
        self,
        content_key: str,
        *,
        title: str | None,
        source: str,
        media_kind: str,
    ) -> JobInfo | None:
        hit = self.cache.lookup_content(content_key)
        if not hit:
            return None
        cached_job, cached_dir = hit
        job_id = new_job_id()
        job = self.cache.clone_succeeded(
            source_job=cached_job,
            source_dir=cached_dir,
            new_job_id=job_id,
            title=title,
            source=source,
            media_kind=media_kind,
            content_key=content_key,
        )
        jdir = self.cache.job_dir(job_id)
        media = self.cache.media_in_job_dir(jdir)
        with self._lock:
            self._jobs[job_id] = job
            self._content_keys[job_id] = content_key
            if media:
                self._media[job_id] = media
        logger.info("content cache hit key=%s -> job %s", content_key, job_id)
        return job.model_copy(deep=True)

    def create(self, upload_path: Path, *, title: str | None = None, media_kind: str = "audio") -> JobInfo:
        digest = sha256_file(upload_path)
        content_key = content_key_for_file(digest)
        hit = self._hit_content(
            content_key,
            title=title,
            source="upload",
            media_kind=media_kind,
        )
        if hit:
            upload_path.unlink(missing_ok=True)
            return hit

        job_id = new_job_id()
        # Keep a durable copy under today's job folder.
        jdir = self.cache.job_dir(job_id)
        durable = jdir / f"source{upload_path.suffix.lower() or '.bin'}"
        if upload_path.resolve() != durable.resolve():
            shutil.copy2(upload_path, durable)
            upload_path.unlink(missing_ok=True)
        upload_path = durable

        job = JobInfo(
            id=job_id,
            status=JobStatus.queued,
            stage="queued",
            progress=0.0,
            source="upload",
            title=title,
            media_kind=media_kind,
        )
        with self._cv:
            self._jobs[job_id] = job
            self._uploads[job_id] = upload_path
            self._content_keys[job_id] = content_key
            self._queue.append(job_id)
            self._cv.notify()
        self._persist(job_id)
        return job.model_copy(deep=True)

    def create_from_url(self, url: str) -> JobInfo:
        url = extract_bilibili_url(url)
        if not is_bilibili_url(url):
            raise ValueError("仅支持 B 站链接（bilibili.com / b23.tv）")
        expanded = expand_bilibili_url(url)
        token, page = parse_bvid_and_page(expanded)
        content_key = content_key_for_bilibili(token, page)
        hit = self._hit_content(
            content_key,
            title=None,
            source="bilibili",
            media_kind="video",
        )
        if hit:
            return hit

        job_id = new_job_id()
        job = JobInfo(
            id=job_id,
            status=JobStatus.queued,
            stage="queued",
            progress=0.0,
            source="bilibili",
            title=None,
            media_kind="video",
        )
        with self._cv:
            self._jobs[job_id] = job
            self._urls[job_id] = expanded
            self._content_keys[job_id] = content_key
            self._queue.append(job_id)
            self._cv.notify()
        self._persist(job_id)
        return job.model_copy(deep=True)

    def media_path(self, job_id: str) -> Path | None:
        with self._lock:
            path = self._media.get(job_id)
            if path and path.exists():
                return path
        loaded = self.cache.load_job(job_id)
        if not loaded:
            return None
        _job, _raw, jdir = loaded
        media = self.cache.media_in_job_dir(jdir)
        if media:
            with self._lock:
                self._media[job_id] = media
        return media

    def pop_media(self, job_id: str) -> Path | None:
        # Keep file on disk for the day; only drop the in-memory pointer.
        with self._lock:
            return self._media.get(job_id)

    def cancel(self, job_id: str) -> JobInfo | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                loaded = None
            else:
                loaded = job
        if loaded is None:
            disk = self.cache.load_job(job_id)
            if not disk:
                return None
            job, _raw, _jdir = disk
            with self._lock:
                self._jobs[job_id] = job
                loaded = job
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
            self._uploads.pop(job_id, None)
            self._urls.pop(job_id, None)
            snapshot = job.model_copy(deep=True)
        self._persist(job_id)
        return snapshot

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
            self._persist(job_id)

            try:

                def on_progress(progress: float, stage: str) -> None:
                    with self._lock:
                        current = self._jobs.get(job_id)
                        if current and current.status == JobStatus.running:
                            current.progress = progress
                            current.stage = stage
                    # Persist sparingly: stage changes matter for resume UI.
                    if stage in {"download", "extract", "asr", "translate", "done"}:
                        self._persist(job_id)

                title: str | None = None
                if url:
                    on_progress(0.02, "download")
                    dl_dir = self.settings.tmp_dir / f"dl-{job_id}"
                    dl_dir.mkdir(parents=True, exist_ok=True)
                    upload, title = download_bilibili_video(url, dl_dir, on_progress=on_progress)
                    # Copy into job cache as durable source/media precursor.
                    jdir = self.cache.job_dir(job_id)
                    durable = jdir / f"source{upload.suffix.lower() or '.mp4'}"
                    shutil.copy2(upload, durable)
                    upload = durable
                    with self._lock:
                        current = self._jobs.get(job_id)
                        if current:
                            current.title = title
                        self._uploads[job_id] = upload
                    self._persist(job_id)

                if upload is None or not upload.exists():
                    raise FileNotFoundError("媒体文件已丢失")

                # Pipeline may delete its input; feed a disposable copy.
                run_src = self.settings.tmp_dir / f"run-{job_id}{upload.suffix.lower() or '.bin'}"
                shutil.copy2(upload, run_src)
                result, media_path = pipeline.run(
                    job, run_src, on_progress, title=title or job.title
                )
                # Keep retained media under job day folder.
                jdir = self.cache.job_dir(job_id)
                final_media = jdir / f"media{media_path.suffix.lower() or '.bin'}"
                if media_path.resolve() != final_media.resolve():
                    shutil.copy2(media_path, final_media)
                    media_path.unlink(missing_ok=True)
                media_path = final_media

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
                        content_key = self._content_keys.get(job_id)
                self._persist(job_id)
                with self._lock:
                    content_key = self._content_keys.get(job_id)
                if content_key:
                    try:
                        self.cache.remember_content(content_key, job_id)
                    except Exception:
                        logger.exception("remember content failed job=%s", job_id)
            except Exception as exc:  # noqa: BLE001 — surface to client
                with self._lock:
                    current = self._jobs[job_id]
                    if current.status != JobStatus.cancelled:
                        current.status = JobStatus.failed
                        current.stage = "failed"
                        current.error = str(exc)
                self._persist(job_id)
            finally:
                with self._lock:
                    self._running_id = None
                dl_dir = self.settings.tmp_dir / f"dl-{job_id}"
                if dl_dir.exists():
                    shutil.rmtree(dl_dir, ignore_errors=True)


_manager: JobManager | None = None


def get_job_manager() -> JobManager:
    global _manager
    if _manager is None:
        _manager = JobManager()
    return _manager
