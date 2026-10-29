"""Provedores de filmagens reais por API oficial (sem scraping).

- Wikimedia Commons: API pública, licença por arquivo (extmetadata). Sempre ativo.
- Pexels (PEXELS_API_KEY) e Pixabay (PIXABAY_API_KEY): desativados sem chave.
"""
from __future__ import annotations

import html
import re
from typing import Any

from ..config import env
from ..models import VisualCandidate
from ..store import Store
from . import licensing
from .http import ApiBudget, get_json

COMMONS = "https://commons.wikimedia.org/w/api.php"


def _strip(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _candidate(provider: str, cid: str, title: str, desc: str, page: str, file_url: str, author: str, lic_name: str,
               lic_url: str | None, w: int | None, h: int | None, dur: float | None, restrictions: str = "") -> VisualCandidate:
    ev = licensing.evaluate(lic_name, restrictions)
    return VisualCandidate(
        id=cid, provider=provider, title=title, description=desc[:600], page_url=page, file_url=file_url,
        author=author or "desconhecido", license=lic_name or "desconhecida", license_url=lic_url,
        license_status=ev["status"], license_note=ev["note"], attribution_required=ev["attribution"],
        share_alike=ev["share_alike"], width=w, height=h, duration=dur,
        credit=licensing.credit_line(title, author or "autor desconhecido", provider, lic_name or "?", page),
    )


class CommonsVideos:
    name = "Wikimedia Commons"

    def is_configured(self) -> bool:
        return True

    def search(self, store: Store, query: str, budget: ApiBudget | None, limit: int = 30) -> list[VisualCandidate]:
        data = get_json(COMMONS, store=store, ttl_s=7 * 24 * 3600, budget=budget, params={
            "action": "query", "format": "json", "formatversion": 2, "generator": "search",
            "gsrsearch": f"{query} filetype:video", "gsrnamespace": 6, "gsrlimit": limit,
            "prop": "videoinfo", "viprop": "url|size|mime|extmetadata|derivatives",
        })
        out = []
        for p in data.get("query", {}).get("pages", []):
            vi = (p.get("videoinfo") or [{}])[0]
            m: dict[str, Any] = vi.get("extmetadata", {})
            val = lambda k: _strip(m.get(k, {}).get("value", ""))  # noqa: E731
            url = self._best_file(vi)
            if not url:
                continue
            out.append(_candidate(
                "Wikimedia Commons", f"commons:{p['pageid']}", p["title"].removeprefix("File:"),
                f"{val('ImageDescription')} {val('Categories')}", vi.get("descriptionurl", ""), url,
                val("Artist") or val("Credit"), val("LicenseShortName"), m.get("LicenseUrl", {}).get("value"),
                vi.get("width"), vi.get("height"), vi.get("duration"), val("Restrictions"),
            ))
        return out

    @staticmethod
    def _best_file(vi: dict) -> str | None:
        """Prefere transcodificação WebM até 1080p (arquivo menor); senão o original se ≤ 120 MB."""
        ders = [d for d in vi.get("derivatives", []) if "webm" in d.get("type", "") and (d.get("height") or 0) <= 1080]
        if ders:
            return max(ders, key=lambda d: d.get("height") or 0)["src"]
        if (vi.get("size") or 0) <= 120_000_000:
            return vi.get("url")
        return None


class PexelsVideos:
    name = "Pexels"

    def is_configured(self) -> bool:
        return bool(env("PEXELS_API_KEY"))

    def search(self, store: Store, query: str, budget: ApiBudget | None, limit: int = 15) -> list[VisualCandidate]:
        import httpx  # chamada autenticada: não passa pelo cache compartilhado com a chave

        if budget:
            budget.consume()
        r = httpx.get("https://api.pexels.com/videos/search", params={"query": query, "per_page": limit},
                      headers={"Authorization": env("PEXELS_API_KEY")}, timeout=20)
        r.raise_for_status()
        name, url, _ = licensing.STOCK_LICENSES["pexels"]
        out = []
        for v in r.json().get("videos", []):
            files = sorted((f for f in v.get("video_files", []) if (f.get("height") or 0) <= 1920),
                           key=lambda f: f.get("height") or 0, reverse=True)
            if not files:
                continue
            slug = v.get("url", "").rstrip("/").split("/")[-1].replace("-", " ")
            out.append(_candidate("Pexels", f"pexels:{v['id']}", slug or f"Pexels {v['id']}", slug, v.get("url", ""),
                                  files[0]["link"], v.get("user", {}).get("name", ""), name, url,
                                  v.get("width"), v.get("height"), v.get("duration")))
        return out


class PixabayVideos:
    name = "Pixabay"

    def is_configured(self) -> bool:
        return bool(env("PIXABAY_API_KEY"))

    def search(self, store: Store, query: str, budget: ApiBudget | None, limit: int = 15) -> list[VisualCandidate]:
        import httpx

        if budget:
            budget.consume()
        r = httpx.get("https://pixabay.com/api/videos/", params={"key": env("PIXABAY_API_KEY"), "q": query, "per_page": limit},
                      timeout=20)
        r.raise_for_status()
        name, url, _ = licensing.STOCK_LICENSES["pixabay"]
        out = []
        for v in r.json().get("hits", []):
            f = v.get("videos", {}).get("large") or v.get("videos", {}).get("medium") or {}
            if not f.get("url"):
                continue
            out.append(_candidate("Pixabay", f"pixabay:{v['id']}", v.get("tags", ""), v.get("tags", ""), v.get("pageURL", ""),
                                  f["url"], v.get("user", ""), name, url, f.get("width"), f.get("height"), v.get("duration")))
        return out


def providers() -> list:
    return [p for p in (PexelsVideos(), PixabayVideos(), CommonsVideos()) if p.is_configured()]
