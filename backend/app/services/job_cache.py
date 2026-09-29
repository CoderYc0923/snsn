from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.schemas import JobInfo, JobResult, JobStatus

logger = logging.getLogger(__name__)

# Bump when split/translate behavior changes so content hits stay coherent.
PIPELINE_CACHE_VERSION = "cue-sub-funasr-v1"

_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def today_key(now: datetime | None = None) -> str:
    return (now or datetime.now()).date().isoformat()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def content_key_for_file(digest: str) -> str:
    return f"file:{PIPELINE_CACHE_VERSION}:{digest}"


def content_key_for_bilibili(bvid: str, page: int = 1) -> str:
    return f"bili:{PIPELINE_CACHE_VERSION}:{bvid}:p{page}"


class JobCacheStore:
    """Filesystem day-cache for jobs + content hits.

    Layout:
      {cache_dir}/{YYYY-MM-DD}/jobs/{job_id}/meta.json|result.json|media.*
      {cache_dir}/{YYYY-MM-DD}/content/{safe_key}/ref.json
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def day_dir(self, day: str | None = None) -> Path:
        d = self.root / (day or today_key())
        d.mkdir(parents=True, exist_ok=True)
        return d

    def job_dir(self, job_id: str, day: str | None = None) -> Path:
        path = self.day_dir(day) / "jobs" / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def content_dir(self, key: str, day: str | None = None) -> Path:
        safe = hashlib.sha256(key.encode("utf-8")).hexdigest()
        path = self.day_dir(day) / "content" / safe
        path.mkdir(parents=True, exist_ok=True)
        return path

    def purge_before_today(self) -> list[str]:
        """Delete day folders older than today. Call at least once per calendar day."""
        keep = today_key()
        removed: list[str] = []
        if not self.root.exists():
            return removed
        for child in list(self.root.iterdir()):
            if not child.is_dir() or not _DAY_RE.match(child.name):
                continue
            if child.name < keep:
                shutil.rmtree(child, ignore_errors=True)
                removed.append(child.name)
                logger.info("purged cache day %s", child.name)
        return removed

    def save_job(
        self,
        job: JobInfo,
        *,
        day: str | None = None,
        content_key: str | None = None,
        source_url: str | None = None,
        media_path: Path | None = None,
        source_path: Path | None = None,
    ) -> Path:
        jdir = self.job_dir(job.id, day)
        payload: dict[str, Any] = {
            "job": json.loads(job.model_dump_json()),
            "content_key": content_key,
            "source_url": source_url,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        (jdir / "meta.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if job.result is not None:
            (jdir / "result.json").write_text(
                job.result.model_dump_json(indent=2),
                encoding="utf-8",
            )
        if media_path and media_path.exists():
            dest = jdir / f"media{media_path.suffix.lower() or '.bin'}"
            if media_path.resolve() != dest.resolve():
                shutil.copy2(media_path, dest)
        if source_path and source_path.exists():
            dest = jdir / f"source{source_path.suffix.lower() or '.bin'}"
            if source_path.resolve() != dest.resolve():
                shutil.copy2(source_path, dest)
        return jdir

    def load_job(self, job_id: str) -> tuple[JobInfo, dict[str, Any], Path] | None:
        """Find job in today's folder first, then any remaining day dirs."""
        days = [today_key()]
        if self.root.exists():
            for child in sorted(self.root.iterdir(), reverse=True):
                if child.is_dir() and _DAY_RE.match(child.name) and child.name not in days:
                    days.append(child.name)
        for day in days:
            jdir = self.root / day / "jobs" / job_id
            meta_path = jdir / "meta.json"
            if not meta_path.is_file():
                continue
            try:
                raw = json.loads(meta_path.read_text(encoding="utf-8"))
                job = JobInfo.model_validate(raw.get("job") or raw)
                if job.result is None and (jdir / "result.json").is_file():
                    job.result = JobResult.model_validate(
                        json.loads((jdir / "result.json").read_text(encoding="utf-8"))
                    )
                return job, raw, jdir
            except Exception:
                logger.exception("failed to load job cache %s", jdir)
                return None
        return None

    def media_in_job_dir(self, jdir: Path) -> Path | None:
        for p in sorted(jdir.glob("media.*")):
            if p.is_file():
                return p
        return None

    def source_in_job_dir(self, jdir: Path) -> Path | None:
        for p in sorted(jdir.glob("source.*")):
            if p.is_file():
                return p
        return None

    def remember_content(self, key: str, job_id: str, day: str | None = None) -> None:
        cdir = self.content_dir(key, day)
        (cdir / "ref.json").write_text(
            json.dumps(
                {
                    "key": key,
                    "job_id": job_id,
                    "pipeline": PIPELINE_CACHE_VERSION,
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def lookup_content(self, key: str) -> tuple[JobInfo, Path] | None:
        """Return (cached succeeded job, job_dir) if content hit exists today."""
        day = today_key()
        safe = hashlib.sha256(key.encode("utf-8")).hexdigest()
        ref_path = self.root / day / "content" / safe / "ref.json"
        if not ref_path.is_file():
            return None
        try:
            ref = json.loads(ref_path.read_text(encoding="utf-8"))
            if ref.get("pipeline") != PIPELINE_CACHE_VERSION:
                return None
            job_id = str(ref.get("job_id") or "")
            loaded = self.load_job(job_id)
            if not loaded:
                return None
            job, _raw, jdir = loaded
            if job.status != JobStatus.succeeded or job.result is None:
                return None
            if not self.media_in_job_dir(jdir):
                return None
            return job, jdir
        except Exception:
            logger.exception("content lookup failed key=%s", key)
            return None

    def clone_succeeded(
        self,
        *,
        source_job: JobInfo,
        source_dir: Path,
        new_job_id: str,
        title: str | None,
        source: str,
        media_kind: str,
        content_key: str | None,
    ) -> JobInfo:
        """Materialize a new succeeded job from a content-cache hit (no re-run)."""
        media = self.media_in_job_dir(source_dir)
        job = JobInfo(
            id=new_job_id,
            status=JobStatus.succeeded,
            progress=1.0,
            stage="done",
            error=None,
            result=source_job.result.model_copy(deep=True) if source_job.result else None,
            source=source,
            title=title or source_job.title,
            media_kind=media_kind or source_job.media_kind,
        )
        self.save_job(
            job,
            content_key=content_key,
            media_path=media,
            source_path=self.source_in_job_dir(source_dir),
        )
        if content_key:
            self.remember_content(content_key, job.id)
        return job

    def list_today_job_ids(self) -> list[str]:
        jobs_root = self.day_dir() / "jobs"
        if not jobs_root.exists():
            return []
        return [p.name for p in jobs_root.iterdir() if p.is_dir()]


def parse_day(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
