from __future__ import annotations

from typing import Any

import dashscope
from dashscope.audio.asr import Transcription

from app.config import Settings
from app.schemas import Cue, CueWord, JobResult


class AsrService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if settings.dashscope_api_key:
            dashscope.api_key = settings.dashscope_api_key

    @property
    def configured(self) -> bool:
        return bool(self.settings.dashscope_api_key)

    def transcribe_japanese(self, file_url: str) -> JobResult:
        """Submit Paraformer file transcription and wait for result."""
        task = Transcription.async_call(
            model=self.settings.asr_model,
            file_urls=[file_url],
            language_hints=["ja"],
        )
        if task.status_code != 200:
            raise RuntimeError(f"ASR submit failed: {task.code} {task.message}")

        status = Transcription.wait(task=task.output.task_id)
        if status.status_code != 200:
            raise RuntimeError(f"ASR wait failed: {status.code} {status.message}")
        if status.output.task_status != "SUCCEEDED":
            raise RuntimeError(f"ASR task ended: {status.output.task_status}")

        results = status.output.get("results") or []
        if not results:
            # Some SDK versions expose results as attribute
            results = getattr(status.output, "results", None) or []
        if not results:
            raise RuntimeError("ASR returned empty results")

        first = results[0]
        if isinstance(first, dict):
            sub_status = first.get("subtask_status")
            transcription_url = first.get("transcription_url")
        else:
            sub_status = getattr(first, "subtask_status", None)
            transcription_url = getattr(first, "transcription_url", None)

        if sub_status and sub_status != "SUCCEEDED":
            raise RuntimeError(f"ASR subtask failed: {first}")
        if not transcription_url:
            raise RuntimeError("ASR missing transcription_url")

        payload = self._download_json(transcription_url)
        return self._parse_transcription(payload)

    def _download_json(self, url: str) -> dict[str, Any]:
        import httpx

        with httpx.Client(timeout=60) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()

    def _parse_transcription(self, payload: dict[str, Any]) -> JobResult:
        transcripts = payload.get("transcripts") or []
        cues: list[Cue] = []
        duration_ms = 0

        for ti, block in enumerate(transcripts):
            sentences = block.get("sentences") or []
            for si, sent in enumerate(sentences):
                start_ms = int(sent.get("begin_time") or 0)
                end_ms = int(sent.get("end_time") or start_ms)
                duration_ms = max(duration_ms, end_ms)
                text = (sent.get("text") or "").strip()
                words: list[CueWord] = []
                for w in sent.get("words") or []:
                    wtext = (w.get("text") or "").strip()
                    if not wtext:
                        continue
                    words.append(
                        CueWord(
                            text=wtext,
                            start_ms=int(w["begin_time"]) if w.get("begin_time") is not None else None,
                            end_ms=int(w["end_time"]) if w.get("end_time") is not None else None,
                        )
                    )
                cues.append(
                    Cue(
                        id=f"c{ti}_{si}",
                        start_ms=start_ms,
                        end_ms=end_ms,
                        text=text,
                        words=words,
                    )
                )

        return JobResult(duration_ms=duration_ms, cues=cues)
