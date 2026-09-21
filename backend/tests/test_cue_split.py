from __future__ import annotations

from app.schemas import Cue, CueWord
from app.services.cue_split import split_cues_for_shadowing


def _w(text: str, start: int, end: int) -> CueWord:
    return CueWord(text=text, start_ms=start, end_ms=end)


def test_keeps_complete_short_sentence() -> None:
    cue = Cue(
        id="c0",
        start_ms=0,
        end_ms=8000,
        text="台風は接近しています。",
        words=[
            _w("台風", 0, 2000),
            _w("は", 2000, 2500),
            _w("接近", 2500, 5500),
            _w("しています。", 5500, 8000),
        ],
    )
    out = split_cues_for_shadowing([cue])
    assert len(out) == 1
    assert out[0].text.endswith("。")


def test_splits_on_sentence_boundary_first() -> None:
    words = [
        _w("今日は晴れです。", 0, 5000),
        _w("明日は雨です。", 5200, 10000),
    ]
    # Expand to word-ish tokens
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
