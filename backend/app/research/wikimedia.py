"""Provedor Wikimedia (API REST pública, sem chave). Licença do texto: CC BY-SA 4.0."""
from __future__ import annotations

import re
from datetime import date, timedelta
from urllib.parse import quote

from ..store import Store
from .http import ApiBudget, NotFound, get_json

REST = "https://wikimedia.org/api/rest_v1/metrics/pageviews"
LICENSE = "CC BY-SA 4.0 (texto da Wikipedia)"
PROVIDER = "wikimedia"

_SKIP_PREFIXES = (
    "Special:", "Especial:", "Wikipedia:", "Portal:", "File:", "Ficheiro:", "Arquivo:", "Help:", "Ajuda:",
    "Category:", "Categoria:", "Talk:", "User:", "Template:", "Predefinição:",
)
_SKIP_TITLES = {"Main_Page", "Wikipédia:Página_principal", "-", "Undefined"}


def article_url(lang: str, title: str) -> str:
    return f"https://{lang}.wikipedia.org/wiki/{quote(title)}"


def last_full_months(n: int, today: date | None = None) -> list[date]:
    """Primeiro dia dos últimos n meses completos, do mais antigo para o mais recente."""
    first = (today or date.today()).replace(day=1)
    months = []
    for _ in range(n):
        first = (first - timedelta(days=1)).replace(day=1)
        months.append(first)
    return list(reversed(months))


def monthly_pageviews(
    store: Store, lang: str, title: str, months: list[date], budget: ApiBudget | None = None
) -> dict[str, int] | None:
    start = months[0].strftime("%Y%m%d")
    last = months[-1]
    end = ((last.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)).strftime("%Y%m%d")
    url = f"{REST}/per-article/{lang}.wikipedia/all-access/user/{quote(title, safe='')}/monthly/{start}/{end}"
    try:
        data = get_json(url, store=store, ttl_s=24 * 3600, budget=budget)
    except NotFound:
        return None
    return {item["timestamp"][:6]: int(item["views"]) for item in data.get("items", [])}


def top_articles(store: Store, lang: str, day: date, budget: ApiBudget | None = None) -> list[dict]:
    url = f"{REST}/top/{lang}.wikipedia/all-access/{day:%Y/%m/%d}"
    try:
        data = get_json(url, store=store, ttl_s=12 * 3600, budget=budget)
    except NotFound:
        return []
    items = data.get("items", [{}])[0].get("articles", [])
    return [a for a in items if a["article"] not in _SKIP_TITLES and not a["article"].startswith(_SKIP_PREFIXES)]


def page_summary(store: Store, lang: str, title: str, budget: ApiBudget | None = None) -> dict | None:
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title, safe='')}"
    try:
        data = get_json(url, store=store, ttl_s=7 * 24 * 3600, budget=budget)
    except NotFound:
        return None
    return {
        "title": data.get("title", title.replace("_", " ")),
        "description": data.get("description"),
        "extract": data.get("extract", ""),
        "url": data.get("content_urls", {}).get("desktop", {}).get("page", article_url(lang, title)),
        "type": data.get("type"),
    }


def page_text(store: Store, lang: str, title: str, budget: ApiBudget | None = None, max_chars: int = 8000) -> str:
    url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query", "prop": "extracts", "explaintext": 1, "exsectionformat": "plain",
        "redirects": 1, "titles": title.replace("_", " "), "format": "json", "formatversion": 2,
    }
    try:
        data = get_json(url, store=store, ttl_s=7 * 24 * 3600, budget=budget, params=params)
    except NotFound:
        return ""
    pages = data.get("query", {}).get("pages", [])
    text = pages[0].get("extract", "") if pages else ""
    return text[:max_chars]


def search_titles(store: Store, lang: str, query: str, limit: int = 8) -> list[dict]:
    url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {"action": "opensearch", "search": query, "limit": limit, "namespace": 0, "format": "json"}
    data = get_json(url, store=store, ttl_s=24 * 3600, params=params)
    return [{"title": t, "url": u} for t, u in zip(data[1], data[3])] if len(data) >= 4 else []


_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý0-9\"“])")


def sentences(text: str) -> list[str]:
    clean = re.sub(r"\s*\([^)]*\)", "", text)  # remove parênteses (pronúncias, datas alternativas)
    clean = re.sub(r"\s+", " ", clean).strip()
    out = []
    for s in _SENT.split(clean):
        s = s.strip()
        if 40 <= len(s) <= 260 and not s.startswith("="):
            out.append(s)
    return out
