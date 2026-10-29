"""Agente 2 — Trend Hunter: tendências públicas e pesquisa de tema com fontes."""
from __future__ import annotations

from datetime import date, timedelta

from ..config import load_json
from ..models import Fact, ResearchSource, Task, TaskResult, TrendItem, TrendRun
from ..research import wikimedia as wm
from .base import Agent, AgentContext

SENSITIVE = (
    "death", "morte", "killed", "morto", "murder", "assassin", "shooting", "tiroteio", "attack", "ataque",
    "terror", "crime", "suicide", "suicídio", "massacre", "war ", "guerra", "pornograph", "pornogr",
)
EXCLUDE = ("pornograph", "pornogr", "adult film", "filme adulto")

INTEREST_WORDS = ("maior", "primeir", "único", "única", "mais ", "menor", "recorde", "largest", "first", "only", "most")


def classify(text: str, niches: list[dict]) -> str:
    low = text.lower().replace("_", " ")
    best, hits = "outros", 0
    for n in niches:
        h = sum(1 for kw in n.get("trend_keywords", []) if kw in low)
        if h > hits:
            best, hits = n["id"], h
    return best


def pick_facts(sentences: list[str], k: int) -> list[str]:
    """Prefere frases com números ou superlativos (curiosidades), mantendo a ordem original."""
    scored = []
    for i, s in enumerate(sentences[:40]):
        low = s.lower()
        score = 2 * any(ch.isdigit() for ch in s) + sum(w in low for w in INTEREST_WORDS) - (i * 0.05)
        scored.append((score, i, s))
    chosen = sorted(sorted(scored, reverse=True)[:k], key=lambda t: t[1])
    return [s for _, _, s in chosen]


class TrendHunter(Agent):
    name = "trend_hunter"
    title = "Trend Hunter"
    description = "Descobre assuntos emergentes em fontes públicas e pesquisa temas com fontes datadas."
    task_types = ("collect_trends", "research_topic")
    owned_kinds = frozenset({"trend_runs", "topic_research"})

    def run(self, task: Task, ctx: AgentContext) -> TaskResult:
        if task.type == "collect_trends":
            return self._collect(ctx)
        return self._research(ctx)

    def _collect(self, ctx: AgentContext) -> TaskResult:
        lang = ctx.param("lang", "pt")
        days = int(ctx.param("days", 7))
        niches = load_json("niches.json")["niches"]
        # Dados diários ficam disponíveis com ~1 dia de atraso.
        window = [date.today() - timedelta(days=2 + i) for i in range(days)][::-1]
        agg: dict[str, dict] = {}
        for idx, day in enumerate(window):
            ctx.check_cancelled()
            for a in wm.top_articles(ctx.store, lang, day, ctx.budget)[:50]:
                e = agg.setdefault(a["article"], {"views": 0, "days": set(), "best_rank": 999})
                e["views"] += int(a["views"])
                e["days"].add(idx)
                e["best_rank"] = min(e["best_rank"], int(a["rank"]))
        top = sorted(agg.items(), key=lambda kv: kv[1]["views"], reverse=True)[:40]
        recent = {len(window) - 1, len(window) - 2}
        items: list[TrendItem] = []
        for title, e in top:
            ctx.check_cancelled()
            summ = wm.page_summary(ctx.store, lang, title, ctx.budget) or {}
            desc = summ.get("description") or ""
            text = f"{title} {desc}".lower()
            if any(x in text for x in EXCLUDE):
                continue
            items.append(TrendItem(
                title=title.replace("_", " "), lang=lang, url=wm.article_url(lang, title), views=e["views"],
                days_present=len(e["days"]), best_rank=e["best_rank"], category=classify(f"{title} {desc}", niches),
                description=desc or None, emerging=e["days"] <= recent,
                sensitive=any(s in text for s in SENSITIVE),
            ))
        run = TrendRun(
            lang=lang, window=[d.isoformat() for d in window], provider=wm.PROVIDER, items=items,
            source=ResearchSource(
                provider=wm.PROVIDER, title=f"Wikimedia Top Articles ({lang}.wikipedia)",
                url=f"{wm.REST}/top/{lang}.wikipedia/all-access/", note="Artigos mais vistos por dia; usuários humanos e bots não filtrados nesta rota.",
            ),
        )
        ctx.save("trend_runs", run)
        emerging = sum(i.emerging for i in items)
        return TaskResult(summary=f"{len(items)} assuntos coletados ({emerging} emergentes) em {lang}",
                          output={"trend_run_id": run.id})

    def _research(self, ctx: AgentContext) -> TaskResult:
        topic = str(ctx.param("topic", "")).strip().replace(" ", "_")
        lang = ctx.param("language", "pt")
        n_facts = 4 if ctx.param("format", "short") == "short" else 8
        if not topic:
            raise ValueError("Tema não informado")
        summ = wm.page_summary(ctx.store, lang, topic, ctx.budget)
        if not summ or summ.get("type") == "disambiguation":
            raise ValueError(f"Tema '{topic}' não encontrado (ou ambíguo) na Wikipedia {lang}")
        text = wm.page_text(ctx.store, lang, topic, ctx.budget)
        src = ResearchSource(provider=wm.PROVIDER, title=f"Wikipedia: {summ['title']}", url=summ["url"],
                             license=wm.LICENSE, note="Texto usado como referência factual; atribuição obrigatória.")
        facts_text = pick_facts(wm.sentences(summ["extract"] + " " + text), n_facts)
        facts = [Fact(text=f, source_id=src.id) for f in facts_text]
        if not facts:
            raise ValueError("Nenhum fato utilizável encontrado na fonte")
        doc = {
            "id": f"{lang}:{topic}", "topic": summ["title"], "description": summ.get("description"),
            "facts": [f.model_dump() for f in facts], "sources": [src.model_dump(mode="json")],
        }
        ctx.store.cache_set(f"topic_research:{lang}:{topic}", doc, 7 * 24 * 3600)
        return TaskResult(summary=f"{len(facts)} fatos com fonte para '{summ['title']}'", output={"research": doc})
