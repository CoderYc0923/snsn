from __future__ import annotations

from app.schemas import Cue, CueWord
from app.services.cue_split import split_cues_for_shadowing


def _w(text: str, start: int, end: int) -> CueWord:
    return CueWord(text=text, start_ms=start, end_ms=end)


def test_keeps_complete_short_sentence() -> None:
    cue = Cue(
        id="c0",
        start_ms=0,
        end_ms=4000,
        text="台風は接近しています。",
        words=[
            _w("台風", 0, 800),
            _w("は", 800, 1000),
            _w("接近", 1000, 2500),
            _w("しています。", 2500, 4000),
        ],
    )
    out = split_cues_for_shadowing([cue])
    assert len(out) == 1
    assert out[0].text.endswith("。")


def test_splits_on_sentence_boundary_first() -> None:
    words = [
        _w("今日", 0, 1200),
        _w("は", 1200, 1500),
        _w("晴れ", 1500, 3500),
        _w("です。", 3500, 5000),
        _w("明日", 5200, 6400),
        _w("は", 6400, 6800),
        _w("雨", 6800, 8500),
        _w("です。", 8500, 10000),
    ]
    cue = Cue(
        id="c0",
        start_ms=0,
        end_ms=10000,
        text="今日は晴れです。明日は雨です。",
        words=words,
    )
    out = split_cues_for_shadowing([cue])
    assert len(out) == 2
    assert out[0].text.endswith("。")
    assert out[1].text.endswith("。")


def test_splits_on_strong_pause_inside_sentence() -> None:
    # One ASR blob, but a long talk gap in the middle (~700ms).
    words = [
        _w("まず", 0, 600),
        _w("準備", 600, 1400),
        _w("します", 1400, 2200),
        _w("次に", 3000, 3600),
        _w("練習", 3600, 4500),
        _w("します", 4500, 5200),
    ]
    cue = Cue(
        id="c0",
        start_ms=0,
        end_ms=5200,
        text="まず準備します次に練習します",
        words=words,
    )
    out = split_cues_for_shadowing([cue])
    assert len(out) == 2
    assert "準備" in out[0].text
    assert "練習" in out[1].text


def test_long_sentence_gets_subtitle_sized() -> None:
    # ~12s continuous talk without 。 — should not stay as one huge cue.
    words = []
    t = 0
    parts = [
        "今日",
        "は",
        "とても",
        "いい",
        "天気",
        "なので",
        "公園",
        "へ",
        "散歩",
        "に",
        "行き",
        "ました",
    ]
    for p in parts:
        words.append(_w(p, t, t + 1000))
        t += 1000
    cue = Cue(
        id="c0",
        start_ms=0,
        end_ms=t,
        text="".join(parts),
        words=words,
    )
    out = split_cues_for_shadowing([cue])
    assert len(out) >= 2
    assert max(c.end_ms - c.start_ms for c in out) <= 9000
