from __future__ import annotations

from app.schemas import Cue, CueWord

# Subtitle-style targets (beginner-friendly), not long shadowing blocks.
_SOFT_MAX_MS = 5_500
_HARD_MAX_MS = 8_000
_MIN_CUE_MS = 400
# Video talk often has long gaps — treat these as hard boundaries.
_PAUSE_STRONG_MS = 480
# Softer breath / comma-like pause inside a sentence.
_PAUSE_SOFT_MS = 280
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
    """Split ASR cues into subtitle-sized lines.

    Priority: sentence end → long pause → soft length at clause/pause → hard cap.
    Avoids half-sentence leftovers better than the old long-block logic.
    """
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
        gap = max(0, cue.start_ms - prev.end_ms)
        prev_ends = (prev.text or "").rstrip().endswith(tuple(_SENTENCE_ENDS))
        # Never glue across a real talk gap or a finished sentence.
        if gap >= _PAUSE_STRONG_MS or prev_ends:
            merged.append(cue)
            continue
        if (dur < _MIN_CUE_MS or chars <= 2) and not prev_ends:
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

    # 1) Always cut on sentence terminators (never leave "一句半").
    sentences = _materialize_slices(cue, words, _cuts_on_sentence_ends(words))

    # 2) Inside each sentence: pause-first, then length caps.
    out: list[Cue] = []
    for sent in sentences:
        sw = [w for w in sent.words if (w.text or "").strip()]
        if len(sw) < 2:
            out.append(sent)
            continue
        dur = max(0, sent.end_ms - sent.start_ms)
        if dur <= _SOFT_MAX_MS and not _has_strong_pause(sw):
            out.append(sent)
            continue
        cuts = _cuts_subtitle(sw, sent.start_ms)
        out.extend(_materialize_slices(sent, sw, cuts) or [sent])
    return out


def _has_strong_pause(words: list[CueWord]) -> bool:
    for i in range(len(words) - 1):
        w, nxt = words[i], words[i + 1]
        if nxt.start_ms is None or w.end_ms is None:
            continue
        if nxt.start_ms - w.end_ms >= _PAUSE_STRONG_MS:
            return True
    return False


def _cuts_on_sentence_ends(words: list[CueWord]) -> list[int]:
    cuts: list[int] = []
    for i, w in enumerate(words[:-1]):
        text = (w.text or "").strip()
        if text and text[-1] in _SENTENCE_ENDS:
            cuts.append(i)
    return cuts


def _cuts_subtitle(words: list[CueWord], cue_start: int) -> list[int]:
    """Pause-first cuts; only force mid-cuts when a segment is still too long."""
    n = len(words)
    cuts: list[int] = []
    seg_start = 0

    def start_ms(i: int) -> int:
        return words[i].start_ms if words[i].start_ms is not None else cue_start

    def end_ms(i: int) -> int:
        return words[i].end_ms if words[i].end_ms is not None else (
            words[i].start_ms or cue_start
        )

    def pause_after(i: int) -> int:
        w, nxt = words[i], words[i + 1]
        if nxt.start_ms is None or w.end_ms is None:
            return 0
        return max(0, nxt.start_ms - w.end_ms)

    for i in range(n - 1):
        w = words[i]
        text = (w.text or "").strip()
        last_ch = text[-1] if text else ""
        bare = text.rstrip("。！？!?、，,；;：:")
        pause = pause_after(i)
        dur = end_ms(i) - start_ms(seg_start)
        clause = last_ch in _CLAUSE_BREAKS
        particle = bare in _NO_CUT_AFTER and last_ch not in _SENTENCE_ENDS

        should = False
        # Strong silence between talk turns — always a subtitle boundary.
        if pause >= _PAUSE_STRONG_MS and dur >= _MIN_CUE_MS:
            should = True
        # Soft length: prefer clause marks or a softer pause; avoid cutting after は/が/を.
        elif dur >= _SOFT_MAX_MS:
            if clause:
                should = True
            elif pause >= _PAUSE_SOFT_MS and not particle:
                should = True
            elif not particle and dur >= _HARD_MAX_MS:
                should = True
        # Hard length: cut even mid-phrase if needed (still prefer non-particle).
        elif dur >= _HARD_MAX_MS and not particle:
            should = True

        if should:
            cuts.append(i)
            seg_start = i + 1

    # Last resort: still one oversized blob — split near midpoint at best pause/clause.
    final_dur = end_ms(n - 1) - start_ms(seg_start)
    if final_dur >= _HARD_MAX_MS and n - seg_start > 3:
        mid_t = (start_ms(seg_start) + end_ms(n - 1)) / 2
        best_i = None
        best = -1.0
        for i in range(seg_start + 1, n - 1):
            w = words[i]
            text = (w.text or "").strip()
            last_ch = text[-1] if text else ""
            bare = text.rstrip("。！？!?、，,；;：:")
            if bare in _NO_CUT_AFTER and last_ch not in _SENTENCE_ENDS:
                continue
            score = 0.0
            if last_ch in _CLAUSE_BREAKS:
                score += 900
            score += min(500, pause_after(i))
            score -= abs(end_ms(i) - mid_t) / 8
            if score > best:
                best = score
                best_i = i
        if best_i is not None:
            cuts.append(best_i)

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
