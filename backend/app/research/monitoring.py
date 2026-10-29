"""Monitoramento de vídeos publicados: snapshots periódicos de dados públicos (YouTube Data API)."""
from __future__ import annotations

import re
from datetime import timedelta

from ..models import PublishedVideo, now
from ..store import Store
from .youtube import YouTubeCompetitionProvider

REFRESH_EVERY = timedelta(hours=6)
_ID = re.compile(r"(?:youtu\.be/|shorts/|watch\?v=|embed/)([A-Za-z0-9_-]{11})")


def video_id(url: str) -> str | None:
    m = _ID.search(url)
    return m.group(1) if m else (url if re.fullmatch(r"[A-Za-z0-9_-]{11}", url) else None)


def refresh(store: Store, force: bool = False) -> dict:
    """Atualiza vídeos sem snapshot recente. Sem chave: registra o motivo e não faz nada."""
    yt = YouTubeCompetitionProvider()
    videos = store.list("published_videos", PublishedVideo)
    due = [v for v in videos if force or not v.snapshots or now() - _ts(v.snapshots[-1]["ts"]) >= REFRESH_EVERY]
    if not due:
        return {"updated": 0, "reason": "nada a atualizar"}
    if not yt.is_configured():
        for v in due:
            v.last_error = "Configure YOUTUBE_API_KEY para coletar visualizações/curtidas/comentários automaticamente."
            store.put("published_videos", v)
        return {"updated": 0, "reason": "YOUTUBE_API_KEY ausente"}
    try:
        stats = yt.public_stats([v.id for v in due])
    except Exception as exc:
        return {"updated": 0, "reason": str(exc)}
    for v in due:
        s = stats.get(v.id)
        if not s:
            v.last_error = "Vídeo não encontrado (privado, removido ou ID incorreto)."
        else:
            v.snapshots.append({"ts": now().isoformat(), "views": s["views"], "likes": s["likes"], "comments": s["comments"]})
            v.title, v.published_at, v.last_error = s["title"] or v.title, s["published_at"], None
        store.put("published_videos", v)
    return {"updated": sum(v.id in stats for v in due), "reason": "ok"}


def _ts(iso: str):
    from datetime import datetime

    return datetime.fromisoformat(iso)
