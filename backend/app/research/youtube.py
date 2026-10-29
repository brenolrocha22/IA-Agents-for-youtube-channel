"""Provedor de concorrência via YouTube Data API v3 (opcional, exige YOUTUBE_API_KEY).

Usa apenas dados públicos (search.list + videos.list). Custo de quota: ~101 unidades por consulta.
Não acessa métricas privadas de nenhum canal.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from statistics import median

from ..config import env
from ..store import Store
from .http import ApiBudget, get_json

API = "https://www.googleapis.com/youtube/v3"


class YouTubeCompetitionProvider:
    name = "youtube_data_api"

    def is_configured(self) -> bool:
        return bool(env("YOUTUBE_API_KEY"))

    def recent_videos(self, store: Store, query: str, lang: str, budget: ApiBudget | None, days: int = 30) -> dict:
        if not self.is_configured():
            raise RuntimeError("YOUTUBE_API_KEY ausente: provedor de concorrência desativado")
        key = env("YOUTUBE_API_KEY")
        after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
        search = get_json(
            f"{API}/search", store=store, ttl_s=24 * 3600, budget=budget,
            params={"part": "snippet", "q": query, "type": "video", "order": "viewCount", "maxResults": 25,
                    "publishedAfter": after, "relevanceLanguage": lang,
                    "regionCode": "BR" if lang == "pt" else "US", "key": key},
        )
        ids = [i["id"]["videoId"] for i in search.get("items", []) if i.get("id", {}).get("videoId")]
        if not ids:
            return {"videos": 0, "channels": [], "median_views": None}
        stats = get_json(
            f"{API}/videos", store=store, ttl_s=24 * 3600, budget=budget,
            params={"part": "statistics,snippet", "id": ",".join(ids), "key": key},
        )
        views = [int(v["statistics"].get("viewCount", 0)) for v in stats.get("items", [])]
        channels = sorted({v["snippet"]["channelTitle"] for v in stats.get("items", [])})
        return {"videos": len(views), "channels": channels, "median_views": median(views) if views else None,
                "window_days": days}

    @staticmethod
    def opportunity_score(result: dict) -> float | None:
        """Mais visualizações recentes distribuídas entre mais canais = demanda aberta a novos criadores."""
        mv = result.get("median_views")
        if not mv:
            return None
        diversity = min(1.0, len(result.get("channels", [])) / 20)
        demand = max(0.0, min(1.0, (math.log10(mv) - 3) / 3))  # 1 mil → 0, 1 milhão → 1
        return round(100 * (0.6 * demand + 0.4 * diversity), 1)
