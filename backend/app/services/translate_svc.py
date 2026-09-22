from __future__ import annotations

import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

import dashscope
from dashscope import Generation

from app.config import Settings
from app.schemas import Cue, CueWord

logger = logging.getLogger(__name__)

_TONES = {"yellow", "blue", "pink", "orange", "mint", "none"}
_SYSTEM_PROMPT = """你是日语新闻/播客字幕的校对、分词注音与翻译专家，目标水准不低于 JLPT N1。
对每条字幕完成：
1. text：校对明显听写错误，保持口播原意；禁止扩写/摘要/合并相邻条。
2. translation：准确自然的简体中文。
3. words：按语义词/词组切开（不要一字一词），每项含：
   - text：词面（可含标点单独一项）
   - furigana：汉字读音假名；纯假名/片假名/标点可省略或空
   - romaji：训令/通行罗马字，小写
   - tone：实词轮流用 yellow|blue|pink|orange|mint；助词/助动词/标点用 none
words 拼接后应与 text 基本一致（允许去掉多余空白）。

严格只返回 JSON 数组，长度=输入条数；每项：
{"text":"...","translation":"...","words":[{"text":"...","furigana":"...","romaji":"...","tone":"yellow"}]}
不要 Markdown，不要解释。"""

ProgressFn = Callable[[float, str], None]


class TranslateService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if settings.dashscope_api_key:
            dashscope.api_key = settings.dashscope_api_key

    def fill_zh(self, cues: list[Cue], on_progress: ProgressFn | None = None) -> list[Cue]:
        if not cues or not self.settings.enable_translate:
            return cues
        if not self.settings.dashscope_api_key:
            return cues

        batches = list(
            _iter_batches(
                cues,
                max_items=self.settings.translate_batch_items,
                max_chars=self.settings.translate_batch_chars,
            )
        )
        workers = max(1, min(self.settings.translate_concurrency, len(batches) or 1))
        logger.info(
            "translate start cues=%s batches=%s workers=%s model=%s",
            len(cues),
            len(batches),
            workers,
            self.settings.translate_model,
        )

        done = 0
        lock = threading.Lock()

        def _report() -> None:
            if not on_progress or not batches:
                return
            # Keep stage=translate while moving bar 0.85 → 0.94
            p = 0.85 + 0.09 * (done / len(batches))
            on_progress(min(p, 0.94), "translate")

        def _run(item: tuple[int, list[Cue]]) -> None:
            nonlocal done
            batch_start, batch = item
            self._apply_batch(batch, batch_start)
            with lock:
                done += 1
                logger.info("translate batch %s/%s (offset=%s size=%s)", done, len(batches), batch_start, len(batch))
                _report()

        if workers == 1:
            for item in batches:
                _run(item)
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_run, item) for item in batches]
                for fut in as_completed(futures):
                    fut.result()

        missing = [
            c
            for c in cues
            if not (c.translation or "").strip() or not _has_rich_words(c)
        ]
        if missing:
            logger.info("translate retry missing=%s", len(missing))
            for cue in missing:
                self._apply_batch([cue], -1)
        return cues

    def _apply_batch(self, batch: list[Cue], batch_start: int) -> None:
        try:
            rows = self._polish_and_translate([c.text for c in batch])
        except Exception:
            logger.exception("translate batch failed at offset %s size=%s", batch_start, len(batch))
            if len(batch) > 1:
                mid = len(batch) // 2
                self._apply_batch(batch[:mid], batch_start)
                self._apply_batch(
                    batch[mid:],
                    batch_start + mid if batch_start >= 0 else -1,
                )
            return
        if len(rows) != len(batch):
            logger.warning(
                "translate size mismatch: got %s want %s (offset %s)",
                len(rows),
                len(batch),
                batch_start,
            )
            if len(batch) > 1:
                mid = len(batch) // 2
                self._apply_batch(batch[:mid], batch_start)
                self._apply_batch(
                    batch[mid:],
                    batch_start + mid if batch_start >= 0 else -1,
                )
            return
        for cue, row in zip(batch, rows):
            polished = str(row.get("text") or cue.text).strip()
            zh = str(row.get("translation") or "").strip()
            if polished:
                cue.text = polished
            if zh:
                cue.translation = zh
            words = _parse_words(row.get("words"), cue)
            if words:
                cue.words = words

    def _polish_and_translate(self, lines: list[str]) -> list[dict[str, Any]]:
        payload = [{"id": i, "text": line} for i, line in enumerate(lines)]
        user = "请处理下列字幕条目（JSON）。\n" + json.dumps(payload, ensure_ascii=False)
        content = self._call_model(user)
        rows = _parse_rows(content, expected=len(lines))
        if rows is not None:
            return rows
        content = self._call_model(
            user + "\n再次确认：只输出 JSON 数组，元素个数=" + str(len(lines))
        )
        rows = _parse_rows(content, expected=len(lines))
        if rows is None:
            raise RuntimeError("failed to parse translate JSON")
        return rows

    def _call_model(self, user: str) -> str:
        resp = Generation.call(
            model=self.settings.translate_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            result_format="message",
            temperature=0.2,
            top_p=0.8,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"LLM {resp.code}: {resp.message}")
        content = resp.output.choices[0].message.content
        if not isinstance(content, str):
            raise RuntimeError("LLM empty content")
        return content


def _has_rich_words(cue: Cue) -> bool:
    if not cue.words:
        return False
    return any(
        (w.furigana or w.romaji or (w.text and len(w.text) > 1)) for w in cue.words
    )


def _iter_batches(cues: list[Cue], max_items: int, max_chars: int):
    batch: list[Cue] = []
    chars = 0
    start = 0
    for i, cue in enumerate(cues):
        tlen = len(cue.text or "")
        overflow = batch and (len(batch) >= max_items or chars + tlen > max_chars)
        if overflow:
            yield start, batch
            start = i
            batch = []
            chars = 0
        batch.append(cue)
        chars += tlen
    if batch:
        yield start, batch


def _parse_rows(content: str, expected: int) -> list[dict[str, Any]] | None:
    data = _extract_json(content)
    if data is None:
        return None
    if isinstance(data, dict) and "items" in data:
        data = data["items"]
    if not isinstance(data, list) or len(data) != expected:
        return None

    rows: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, str):
            rows.append({"text": "", "translation": item.strip(), "words": []})
            continue
        if not isinstance(item, dict):
            return None
        text = item.get("text")
        translation = item.get("translation")
        if translation is None:
            translation = item.get("zh") or item.get("cn") or ""
        rows.append(
            {
                "text": "" if text is None else str(text),
                "translation": "" if translation is None else str(translation),
                "words": item.get("words") or [],
            }
        )
    return rows


def _parse_words(raw: Any, cue: Cue) -> list[CueWord] | None:
    if not isinstance(raw, list) or not raw:
        return None
    out: list[CueWord] = []
    # Distribute original timestamps roughly across new semantic words.
    src = [w for w in cue.words if (w.text or "").strip()]
    src_i = 0
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        tone = str(item.get("tone") or "none").lower()
        if tone not in _TONES:
            tone = "none"
        furigana = item.get("furigana")
        romaji = item.get("romaji")
        start_ms = None
        end_ms = None
        if src:
            # Consume source char/word timestamps covering this token length.
            need = max(1, len(text))
            taken = 0
            first = src[min(src_i, len(src) - 1)]
            start_ms = first.start_ms
            while src_i < len(src) and taken < need:
                piece = src[src_i]
                taken += len(piece.text or "")
                end_ms = piece.end_ms
                src_i += 1
            if start_ms is None:
                start_ms = cue.start_ms
            if end_ms is None:
                end_ms = cue.end_ms
        out.append(
            CueWord(
                text=text,
                furigana=str(furigana).strip() if furigana else None,
                romaji=str(romaji).strip() if romaji else None,
                tone=tone,
                start_ms=start_ms,
                end_ms=end_ms,
            )
        )
    return out or None


def _extract_json(content: str) -> Any | None:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    start = content.find("[")
    end = content.rfind("]")
    if start >= 0 and end > start:
        try:
            return json.loads(content[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None
