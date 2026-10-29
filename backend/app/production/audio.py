"""Trilha e efeitos originais (obra própria, sintetizados localmente) e mixagem com ducking + loudnorm."""
from __future__ import annotations

import array
import math
import random
import wave
from pathlib import Path

from . import ffmpeg

SR = 44100


def suspense_music(out: Path, duration: float, timeout_s: int) -> None:
    """Drone grave + pulso que se intensifica + brilho tenso. Sem material de terceiros."""
    d = max(1.0, duration)
    expr = (
        f"(0.10*sin(2*PI*55*t)*(0.7+0.3*sin(2*PI*0.07*t))+0.07*sin(2*PI*55.6*t)+0.05*sin(2*PI*82.41*t)"
        f"+0.22*sin(2*PI*48*t)*exp(-9*mod(t,0.9))*(0.3+0.7*t/{d:.2f})"
        f"+0.02*sin(2*PI*659.25*t)*(0.5+0.5*sin(2*PI*0.25*t))*(t/{d:.2f}))"
    )
    # Aspas simples: as vírgulas da expressão não podem ser lidas como separadores do filtro.
    ffmpeg.run(["-y", "-f", "lavfi", "-i", f"aevalsrc='{expr}':s={SR}:d={d:.2f}",
                "-af", f"lowpass=f=2600,afade=t=in:d=1.5,afade=t=out:st={max(0, d - 2):.2f}:d=2", str(out)], timeout_s)


def _add(buf: array.array, t0: float, samples: list[float]) -> None:
    i0 = int(t0 * SR)
    for i, s in enumerate(samples):
        j = i0 + i
        if 0 <= j < len(buf):
            buf[j] = max(-32767, min(32767, buf[j] + int(s * 32767)))


def _impact(rnd: random.Random, dur: float = 1.2, gain: float = 0.7) -> list[float]:
    out = []
    for i in range(int(dur * SR)):
        x = i / SR
        out.append(gain * (math.sin(2 * math.pi * (70 - 45 * x) * x) * math.exp(-3.5 * x)
                           + 0.35 * (rnd.random() * 2 - 1) * math.exp(-25 * x)))
    return out


def _whoosh(rnd: random.Random, dur: float = 0.6, gain: float = 0.10) -> list[float]:
    out, lp = [], 0.0
    for i in range(int(dur * SR)):
        x = i / (dur * SR)
        a = 0.02 + 0.25 * math.sin(math.pi * x)  # filtro abre e fecha
        lp += a * ((rnd.random() * 2 - 1) - lp)
        out.append(gain * lp * math.sin(math.pi * x) ** 2 * 3)
    return out


def _riser(rnd: random.Random, dur: float = 1.4, gain: float = 0.16) -> list[float]:
    out, lp, ph = [], 0.0, 0.0
    for i in range(int(dur * SR)):
        x = i / (dur * SR)
        lp += (0.03 + 0.4 * x) * ((rnd.random() * 2 - 1) - lp)
        ph += 2 * math.pi * (200 + 700 * x * x) / SR
        out.append(gain * x * x * (0.6 * lp * 3 + 0.4 * math.sin(ph)))
    return out


def sfx_track(out: Path, duration: float, boundaries: list[float], riser_at: list[float], end_hit: float) -> None:
    """Efeitos pontuais: impacto inicial, whoosh entre cenas, crescente de tensão, encerramento."""
    rnd = random.Random(42)
    buf = array.array("h", bytes(int(duration * SR) * 2))
    _add(buf, 0.0, _impact(rnd))
    for b in boundaries:
        _add(buf, max(0.0, b - 0.3), _whoosh(rnd))
    for r in riser_at:
        _add(buf, max(0.0, r - 1.4), _riser(rnd))
    _add(buf, end_hit, _impact(rnd, 1.6, 0.55))
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(buf.tobytes())


# Volumes padrão definidos pelo proprietário (2026-10-30): voz 55%, música 35%. Editáveis em config/channels.json ("audio").
VOICE_VOLUME, MUSIC_VOLUME, SFX_VOLUME = 0.55, 0.35, 0.5

MIX_FILTER = (
    "[1:a]aresample={sr},apad=whole_dur={dur:.3f},asplit=2[nk][nv];"
    "[nv]volume={voice}[n1];"
    "[2:a]aresample={sr},volume={music}[m];"
    "[m][nk]sidechaincompress=threshold=0.02:ratio=4:attack=15:release=350[md];"
    "[3:a]aresample={sr},volume={sfx}[s];"
    # loudnorm ajusta a altura final (-14 LUFS, padrão do YouTube) preservando a proporção voz/música
    "[n1][md][s]amix=inputs=3:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]"
)


def levels(channel: dict) -> dict:
    a = channel.get("audio", {})
    return {"voice": a.get("voice", VOICE_VOLUME), "music": a.get("music", MUSIC_VOLUME), "sfx": a.get("sfx", SFX_VOLUME)}


def remix(video: Path, narration: Path, music: Path, sfx: Path, out: Path, duration: float, lv: dict, timeout_s: int) -> None:
    """Refaz só o áudio de um vídeo já renderizado (imagem copiada sem recodificar)."""
    graph = MIX_FILTER.format(sr=SR, dur=duration, **lv)
    ffmpeg.run(["-y", "-i", str(video), "-i", str(narration), "-i", str(music), "-i", str(sfx), "-filter_complex", graph,
                "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                "-t", f"{duration:.3f}", str(out)], timeout_s)
