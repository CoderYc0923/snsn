from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _candidate_bins() -> list[Path]:
    home = Path(os.environ.get("LOCALAPPDATA", ""))
    out: list[Path] = []
    links = home / "Microsoft" / "WinGet" / "Links"
    if links.is_dir():
        out.append(links)
    packages = home / "Microsoft" / "WinGet" / "Packages"
    if packages.is_dir():
        for bin_dir in packages.glob("Gyan.FFmpeg*/ffmpeg-*/full_build/bin"):
            if bin_dir.is_dir():
                out.append(bin_dir)
    return out


def _resolve_tool(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for folder in _candidate_bins():
        exe = folder / f"{name}.exe"
        if exe.is_file():
            return str(exe)
    return None


def ffmpeg_available() -> bool:
    return _resolve_tool("ffmpeg") is not None and _resolve_tool("ffprobe") is not None


def probe_duration_sec(path: Path) -> float:
    ffprobe = _resolve_tool("ffprobe")
    if not ffprobe:
        raise FileNotFoundError("ffprobe not found")
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    out = subprocess.check_output(cmd, text=True).strip()
    return float(out or 0)


def extract_wav_16k_mono(src: Path, dst: Path) -> Path:
    ffmpeg = _resolve_tool("ffmpeg")
    if not ffmpeg:
        raise FileNotFoundError("ffmpeg not found")
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(src),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(dst),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return dst
