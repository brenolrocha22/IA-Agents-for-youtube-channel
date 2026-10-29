"""Agente 3 — Niche Analyst: ranking explicável de nichos e criação de briefings."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from ..config import load_json, output_dir
from ..models import Fact, NicheReport, NicheScore, ResearchSource, Task, TaskResult, VideoBrief
from ..research import scoring
from ..research import wikimedia as wm
from ..research.youtube import YouTubeCompetitionProvider
from .base import Agent, AgentContext

LIMITATIONS = [
    "Pageviews da Wikipedia medem interesse por um tema, não buscas ou visualizações no YouTube.",
    "Artigos-semente são escolhas editoriais; outros artigos poderiam mudar a demanda medida.",
    "Crescimento não é corrigido por sazonalidade (ex.: Copa do Mundo de 2026 em junho/julho).",
    "Retenção e monetização são hipóteses até existirem métricas reais do canal. Nenhum CPM/RPM foi estimado.",
    "Sem YOUTUBE_API_KEY, concorrência é hipótese; com a chave, considera apenas vídeos públicos recentes.",
    "Google Trends não possui API pública aberta e não foi usado.",
]

NEXT_TESTS = [
    "Publicar 3–5 Shorts por nicho candidato com o mesmo padrão de produção e comparar visualizações e % de visualização após 7 dias.",
    "Testar 2 tons (cômico × educativo) no mesmo tema para isolar o efeito do tom.",
    "Configurar YOUTUBE_API_KEY para medir concorrência real de vídeos recentes.",
    "Importar métricas do YouTube Studio (CSV) a cada semana na página Analytics.",
    "Revisar as hipóteses de config/niches.json com base nos resultados.",
]


def _niche_metrics(ctx: AgentContext, niche: dict, lang: str, months: list[date]) -> tuple[dict, list[ResearchSource]]:
    seeds = niche["seeds"].get(lang, [])
    last3 = [m.strftime("%Y%m") for m in months[3:]]
    prev3 = [m.strftime("%Y%m") for m in months[:3]]
    days_last3 = sum((m.replace(month=m.month % 12 + 1, year=m.year + m.month // 12) - m).days for m in months[3:])
    found, missing, avgs, s_last, s_prev, sources = 0, [], [], 0, 0, []
    for title in seeds:
        series = wm.monthly_pageviews(ctx.store, lang, title, months, ctx.budget)
        if not series:
            missing.append(title)
            continue
        found += 1
        l3 = sum(series.get(m, 0) for m in last3)
        p3 = sum(series.get(m, 0) for m in prev3)
        avgs.append(l3 / days_last3)
        s_last += l3
        s_prev += p3
        sources.append(ResearchSource(
            provider=wm.PROVIDER, title=f"Pageviews mensais: {title} ({lang})", url=wm.article_url(lang, title),
            note=f"Wikimedia Pageviews API, agente=user, {months[0]:%Y-%m} a {months[-1]:%Y-%m}",
        ))
    metrics = {
        "avg_daily_views": round(sum(avgs) / len(avgs), 1) if avgs else None,
        "growth_ratio": round(s_last / s_prev, 3) if s_prev else None,
        "seeds_found": found, "seeds_missing": missing,
        "period": f"{months[0]:%Y-%m}..{months[-1]:%Y-%m}",
    }
    return metrics, sources


def render_markdown(report: NicheReport) -> str:
    lines = [
        "# Relatório de nichos — Creator Intelligence OS",
        "",
        f"Gerado em: {report.created_at:%Y-%m-%d %H:%M} UTC · Mercado primário: {report.primary_market}",
        "",
        "## Metodologia",
        report.methodology,
        "",
        "Pesos: " + ", ".join(f"{k} {v:.0%}" for k, v in report.weights.items()),
        "",
    ]
    for market, items in report.rankings.items():
        lines += [f"## Top 5 — mercado `{market}`", "",
                  "| # | Nicho | Nota | Cobertura | Confiança | Recomendado | Alerta |",
                  "|---|-------|------|-----------|-----------|-------------|--------|"]
        for i, s in enumerate(items[:5], 1):
            alert = s.blocked_reason or ", ".join(r.label for r in s.risks if r.severity == "high") or "—"
            lines.append(f"| {i} | {s.name} | {s.total if s.total is not None else 'desconhecido'} | "
                         f"{s.coverage:.0%} | {s.confidence} | {'sim' if s.recommended else 'não'} | {alert} |")
        lines.append("")
        for s in items[:5]:
            lines.append(f"### {s.name} ({market})")
            for c in s.criteria:
                val = "desconhecido" if c.score is None else f"{c.score:.0f}"
                lines.append(f"- **{c.label}**: {val} — _{c.evidence.value}_ — {c.rationale}")
            lines.append("")
        others = [s for s in items[5:] if s.blocked_reason]
        if others:
            lines.append("Fora do top 5 com risco crítico: " + "; ".join(f"{s.name} ({s.blocked_reason})" for s in others))
            lines.append("")
    lines += ["## Fontes", ""]
    for src in report.sources:
        lines.append(f"- {src.title} — {src.url} — coletado em {src.collected_at:%Y-%m-%d} ({src.evidence.value})")
    lines += ["", "## Limitações", ""] + [f"- {x}" for x in report.limitations]
    lines += ["", "## Próximos testes recomendados", ""] + [f"- {x}" for x in report.next_tests]
    return "\n".join(lines) + "\n"


class NicheAnalyst(Agent):
    name = "niche_analyst"
    title = "Niche Analyst"
    description = "Avalia nichos com pontuação explicável, riscos e incertezas; cria briefings de vídeo."
    task_types = ("rank_niches", "build_brief")
    owned_kinds = frozenset({"niche_reports", "briefs"})

    def run(self, task: Task, ctx: AgentContext) -> TaskResult:
        return self._rank(ctx) if task.type == "rank_niches" else self._brief(ctx)

    def _rank(self, ctx: AgentContext) -> TaskResult:
        markets = ctx.param("markets", ["pt", "en"])
        niches = load_json("niches.json")["niches"]
        cfg = load_json("scoring.json")
        months = wm.last_full_months(6)
        yt = YouTubeCompetitionProvider()
        rankings: dict[str, list[NicheScore]] = {}
        all_sources: list[ResearchSource] = []
        for market in markets:
            ctx.check_cancelled()
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda n: _niche_metrics(ctx, n, market, months), niches))
            scores = []
            for niche, (metrics, sources) in zip(niches, results):
                comp = None
                if yt.is_configured():
                    try:
                        raw = yt.recent_videos(ctx.store, niche["youtube_query"][market], market, ctx.budget)
                        comp = {**raw, "score": yt.opportunity_score(raw)}
                        all_sources.append(ResearchSource(provider=yt.name, title=f"YouTube: '{niche['youtube_query'][market]}'",
                                                          url="https://www.youtube.com/results?search_query=" + niche["youtube_query"][market].replace(" ", "+")))
                    except Exception as exc:  # concorrência é opcional: falha vira hipótese
                        ctx.log(f"YouTube API falhou para {niche['id']}: {exc}", "warning")
                all_sources.extend(sources)
                scores.append(scoring.score_niche(niche, market, metrics, comp, [s.id for s in sources], cfg))
            rankings[market] = scoring.rank(scores)
        report = NicheReport(
            primary_market="pt", markets=markets, weights=cfg["weights"], methodology=scoring.METHODOLOGY,
            rankings=rankings, sources=all_sources, limitations=LIMITATIONS, next_tests=NEXT_TESTS,
        )
        reports = output_dir() / "reports"
        reports.mkdir(exist_ok=True)
        stem = f"nichos_{report.created_at:%Y%m%d_%H%M%S}"
        (reports / f"{stem}.md").write_text(render_markdown(report), encoding="utf-8")
        (reports / f"{stem}.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
        report.report_path = str(Path("output") / "reports" / f"{stem}.md")
        ctx.save("niche_reports", report)
        top = rankings.get("pt") or next(iter(rankings.values()))
        return TaskResult(
            summary=f"Ranking gerado ({len(niches)} nichos × {len(markets)} mercados). Líder pt: {top[0].name} ({top[0].total})",
            output={"niche_report_id": report.id, "report_path": report.report_path},
            artifacts=[report.report_path],
        )

    def _brief(self, ctx: AgentContext) -> TaskResult:
        research = ctx.param("research")
        if not research:
            raise ValueError("Pesquisa do tema ausente")
        fmt = ctx.param("format", "short")
        tone = ctx.param("tone", "comico")
        niche_id = ctx.param("niche_id", "ciencia_espaco")
        facts = [Fact(**f) for f in research["facts"]]
        angles = {
            "comico": "Curiosidades reais contadas com humor leve e ritmo rápido, sem distorcer os fatos.",
            "educativo": "Explicação clara e direta do essencial, com um dado surpreendente.",
            "criativo": "Comparações inusitadas e imaginação para tornar o tema memorável.",
        }
        brief = VideoBrief(
            niche_id=niche_id, topic=research["topic"], topic_description=research.get("description"),
            language=ctx.param("language", "pt"), format=fmt, tone=tone, angle=angles.get(tone, angles["educativo"]),
            audience="Público brasileiro geral, 16–40 anos, consumo mobile" if fmt == "short" else "Público brasileiro interessado no tema",
            key_points=[f.text for f in facts[: (3 if fmt == "short" else 6)]],
            facts=facts, sources=[ResearchSource(**s) for s in research["sources"]],
            topic_en=research.get("topic_en"), items=research.get("items", []),
        )
        ctx.save("briefs", brief)
        return TaskResult(summary=f"Briefing '{brief.topic}' ({fmt}, {tone})", output={"brief_id": brief.id})
