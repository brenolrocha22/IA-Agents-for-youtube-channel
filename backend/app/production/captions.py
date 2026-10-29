"""Legendas: divisão em blocos curtos, temporização proporcional e SRT."""
from __future__ import annotations

import re
from pathlib import Path


def chunk_words(text: str, max_words: int, max_chars: int) -> list[str]:
    chunks, cur = [], []
    for w in text.split():
        if cur and (len(cur) >= max_words or len(" ".join(cur + [w])) > max_chars):
            chunks.append(" ".join(cur))
            cur = []
        cur.append(w)
        if re.search(r"[.!?:]$", w):  # pontuação forte fecha o bloco
            chunks.append(" ".join(cur))
            cur = []
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def build_cues(text: str, start: float, duration: float, vertical: bool) -> list[dict]:
    chunks = chunk_words(text, 4 if vertical else 9, 26 if vertical else 60)
    total = sum(len(c) for c in chunks) or 1
    cues, t = [], start
    for c in chunks:
        d = duration * len(c) / total
        cues.append({"start": round(t, 3), "end": round(t + d, 3), "text": c})
        t += d
    return cues


def _ts(s: float) -> str:
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def write_srt(cues: list[dict], path: Path) -> None:
    blocks = [f"{i}\n{_ts(c['start'])} --> {_ts(c['end'])}\n{c['text']}\n" for i, c in enumerate(cues, 1)]
    path.write_text("\n".join(blocks), encoding="utf-8")


def read_srt(path: Path) -> list[dict]:
    def sec(t: str) -> float:
        h, m, rest = t.split(":")
        s, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    cues = []
    for block in path.read_text(encoding="utf-8").strip().split("\n\n"):
        lines = block.strip().splitlines()
        if len(lines) >= 3 and "-->" in lines[1]:
            a, b = [x.strip() for x in lines[1].split("-->")]
            cues.append({"start": sec(a), "end": sec(b), "text": " ".join(lines[2:])})
    return cues
