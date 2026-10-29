"""Integração FFmpeg. Único binário de mídia permitido; argumentos montados pelo código, sem shell, com timeout."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from ..config import env

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


@lru_cache
def ffmpeg_exe() -> str:
    configured = env("FFMPEG_PATH")
    if configured and Path(configured).exists():
        return configured
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def available() -> dict:
    try:
        exe = ffmpeg_exe()
        out = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=15, creationflags=_NO_WINDOW)
        return {"available": True, "version": out.stdout.splitlines()[0] if out.stdout else "?", "path": exe}
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def run(args: list[str], timeout_s: int, cwd: Path | None = None) -> subprocess.CompletedProcess:
    if any(not isinstance(a, str) for a in args):
        raise TypeError("Argumentos do ffmpeg devem ser strings")
    proc = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-nostdin", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout_s, creationflags=_NO_WINDOW, cwd=cwd,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou ({proc.returncode}): {proc.stderr[-800:]}")
    return proc


def probe(path: Path) -> dict:
    proc = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=60, creationflags=_NO_WINDOW)
    err = proc.stderr
    info: dict = {"has_audio": False}
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", err)
    if m:
        h, mi, s = m.groups()
        info["duration"] = int(h) * 3600 + int(mi) * 60 + float(s)
    v = re.search(r"Video: (\w+).*?, (\d{2,5})x(\d{2,5})", err)
    if v:
        info.update(video_codec=v.group(1), width=int(v.group(2)), height=int(v.group(3)))
    a = re.search(r"Audio: (\w+)", err)
    if a:
        info.update(has_audio=True, audio_codec=a.group(1))
    return info


def decode_errors(path: Path) -> str:
    proc = subprocess.run([ffmpeg_exe(), "-v", "error", "-i", str(path), "-f", "null", "-"], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300, creationflags=_NO_WINDOW)
    return proc.stderr.strip()


def black_segments(path: Path, min_s: float = 0.4) -> list[tuple[float, float]]:
    """Trechos de tela preta (blackdetect) com duração mínima."""
    proc = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(path), "-vf", f"blackdetect=d={min_s}:pix_th=0.08", "-an",
                           "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
                          creationflags=_NO_WINDOW)
    return [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", proc.stderr)]


def volume_stats(path: Path) -> dict:
    proc = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(path), "-vn", "-af", "volumedetect", "-f", "null", "-"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, creationflags=_NO_WINDOW)
    mean = re.search(r"mean_volume: (-?[\d.]+) dB", proc.stderr)
    peak = re.search(r"max_volume: (-?[\d.]+) dB", proc.stderr)
    return {"mean_db": float(mean.group(1)) if mean else None, "max_db": float(peak.group(1)) if peak else None}
