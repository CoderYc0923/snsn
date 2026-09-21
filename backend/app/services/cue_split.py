from __future__ import annotations

from app.schemas import Cue, CueWord

# Prefer keeping a full sentence. Only mid-split when a sentence is too long.
_SOFT_MAX_MS = 16_000
_HARD_MAX_MS = 22_000
_MIN_CUE_MS = 500
_PAUSE_SPLIT_MS = 420
_SENTENCE_ENDS = set("。！？!?")
_CLAUSE_BREAKS = set("、，,；;：:")
_NO_CUT_AFTER = {
    "は",
    "が",
    "を",
    "に",
    "で",
    "と",
    "も",
    "の",
    "へ",
    "や",
    "か",
    "ね",
    "よ",
    "な",
    "て",
    "し",
    "ば",
}


def split_cues_for_shadowing(cues: list[Cue]) -> list[Cue]:
    """Semantic-first split: complete sentences, then mid-clause only if oversized."""
    out: list[Cue] = []
    for cue in cues:
        out.extend(_split_one(cue) or [cue])
    return [_reindex(i, c) for i, c in enumerate(_merge_tiny(out))]


def _reindex(i: int, cue: Cue) -> Cue:
    return cue.model_copy(update={"id": f"c{i}"})


def _merge_tiny(cues: list[Cue]) -> list[Cue]:
    if not cues:
        return cues
    merged: list[Cue] = [cues[0]]
    for cue in cues[1:]:
        prev = merged[-1]
        dur = cue.end_ms - cue.start_ms
        chars = len((cue.text or "").strip())
        # Only glue fragments; never glue two complete sentences if already readable.
        prev_ends = (prev.text or "").rstrip().endswith(tuple(_SENTENCE_ENDS))
        if (dur < 500 or chars <= 3) and not prev_ends:
            merged[-1] = Cue(
                id=prev.id,
                start_ms=prev.start_ms,
                end_ms=max(prev.end_ms, cue.end_ms),
                text=(prev.text + cue.text).strip(),
                translation="",
                words=list(prev.words) + list(cue.words),
            )
        else:
            merged.append(cue)
    return merged


def _split_one(cue: Cue) -> list[Cue]:
    text = (cue.text or "").strip()
    if not text:
        return []

    words = [w for w in cue.words if (w.text or "").strip()]
    if len(words) < 2:
        return [cue]

    # Pass 1: always cut on sentence terminators.
    sentence_cuts = _cuts_on_sentence_ends(words)
    sentences = _materialize_slices(cue, words, sentence_cuts)

    # Pass 2: only oversized sentences get mid-clause splits.
    out: list[Cue] = []
    for sent in sentences:
        dur = max(0, sent.end_ms - sent.start_ms)
        if dur <= _SOFT_MAX_MS:
            out.append(sent)
            continue
        sw = [w for w in sent.words if (w.text or "").strip()]
        if len(sw) < 4:
            out.append(sent)
            continue
        mid_cuts = _cuts_oversized(sw, sent.start_ms)
        pieces = _materialize_slices(sent, sw, mid_cuts)
        out.extend(pieces or [sent])
    return out


def _cuts_on_sentence_ends(words: list[CueWord]) -> list[int]:
    cuts: list[int] = []
    for i, w in enumerate(words[:-1]):
        text = (w.text or "").strip()
        if text and text[-1] in _SENTENCE_ENDS:
            cuts.append(i)
    return cuts


def _cuts_oversized(words: list[CueWord], cue_start: int) -> list[int]:
    n = len(words)
    cuts: list[int] = []
    seg_start = 0

    def start_ms(i: int) -> int:
        return words[i].start_ms if words[i].start_ms is not None else cue_start

    def end_ms(i: int) -> int:
        return words[i].end_ms if words[i].end_ms is not None else (
            words[i].start_ms or cue_start
        )

    for i in range(n - 1):
        w = words[i]
        nxt = words[i + 1]
        text = (w.text or "").strip()
        last_ch = text[-1] if text else ""
        bare = text.rstrip("。！？!?、，,；;：:")
        pause = 0
        if nxt.start_ms is not None and w.end_ms is not None:
            pause = max(0, nxt.start_ms - w.end_ms)
        dur = end_ms(i) - start_ms(seg_start)

        if bare in _NO_CUT_AFTER and last_ch not in _SENTENCE_ENDS and dur < _HARD_MAX_MS:
            continue

        clause = last_ch in _CLAUSE_BREAKS
        pause_break = pause >= _PAUSE_SPLIT_MS
        soft = dur >= _SOFT_MAX_MS
        hard = dur >= _HARD_MAX_MS

        should = False
        if hard and (clause or pause_break or bare not in _NO_CUT_AFTER):
            should = True
        elif soft and clause and dur >= _MIN_CUE_MS:
            should = True
        elif soft and pause_break and dur >= _MIN_CUE_MS:
            should = True

        if should:
            cuts.append(i)
            seg_start = i + 1

    if not cuts and n > 4:
        # Last resort: midpoint near a clause/pause.
        mid_t = (start_ms(0) + end_ms(n - 1)) / 2
        best_i = None
        best = -1.0
        for i in range(1, n - 1):
            w = words[i]
            text = (w.text or "").strip()
            last_ch = text[-1] if text else ""
            score = 0.0
            if last_ch in _CLAUSE_BREAKS:
                score += 800
            nxt = words[i + 1]
            if nxt.start_ms is not None and w.end_ms is not None:
                score += min(400, max(0, nxt.start_ms - w.end_ms))
            score -= abs(end_ms(i) - mid_t) / 10
            if score > best:
                best = score
                best_i = i
        if best_i is not None and best > 0:
            cuts = [best_i]
    return cuts


def _materialize_slices(
    cue: Cue, words: list[CueWord], cut_after: list[int]
) -> list[Cue]:
    if not cut_after:
        return [cue]
    slices: list[Cue] = []
    start_idx = 0
    ends = cut_after + [len(words) - 1]
    for end_idx in ends:
        if end_idx < start_idx:
            continue
        chunk = words[start_idx : end_idx + 1]
        if not chunk:
            continue
        text = "".join((w.text or "") for w in chunk).strip()
        if not text:
            start_idx = end_idx + 1
            continue
        start_ms = chunk[0].start_ms if chunk[0].start_ms is not None else cue.start_ms
        end_ms = chunk[-1].end_ms if chunk[-1].end_ms is not None else cue.end_ms
        if end_ms < start_ms:
            end_ms = start_ms
        slices.append(
            Cue(
                id=cue.id,
                start_ms=int(start_ms),
                end_ms=int(end_ms),
                text=text,
                translation="",
                words=list(chunk),
            )
        )
        start_idx = end_idx + 1
    return slices or [cue]
