"""Agente 8 — Analytics: métricas autorizadas/importadas, comparações e experimentos. Demo sempre identificado."""
from __future__ import annotations

import csv
import io
import random
from statistics import mean

from ..models import AnalyticsReport, MetricRecord, Task, TaskResult
from .base import Agent, AgentContext

MIN_SAMPLE = 3

# Cabeçalhos aceitos (export do YouTube Studio em pt/en ou planilha manual).
HEADERS = {
    "video_ref": ("content", "conteúdo", "video", "vídeo", "video_ref"),
    "title": ("video title", "título do vídeo", "title", "título"),
    "published_at": ("video publish time", "horário de publicação do vídeo", "published_at"),
    "duration_s": ("duration", "duração", "duration_s"),
    "views": ("views", "visualizações"),
    "watch_time_h": ("watch time (hours)", "tempo de exibição (horas)", "watch_time_h"),
    "subs_gained": ("subscribers", "inscritos", "subs_gained"),
    "impressions": ("impressions", "impressões"),
    "ctr": ("impressions click-through rate (%)", "taxa de cliques de impressões (%)", "ctr"),
    "avg_view_pct": ("average percentage viewed (%)", "porcentagem média visualizada (%)", "avg_view_pct"),
    "revenue_usd": ("estimated revenue (usd)", "receita estimada (usd)", "revenue_usd"),
    "format": ("format", "formato"),
    "niche": ("niche", "nicho"),
    "theme": ("theme", "tema"),
    "hook": ("hook", "gancho"),
}
NUMERIC = {"duration_s": float, "views": int, "watch_time_h": float, "subs_gained": int, "impressions": int,
           "ctr": float, "avg_view_pct": float, "revenue_usd": float}


def parse_csv(text: str) -> list[MetricRecord]:
    reader = csv.DictReader(io.StringIO(text))
    cols = {h: k for k, names in HEADERS.items() for h in (reader.fieldnames or []) if h.strip().lower() in names}
    out = []
    for row in reader:
        data: dict = {"source": "csv"}
        for col, key in cols.items():
            val = (row.get(col) or "").strip()
            if not val or val.lower() == "total":
                continue
            if key in NUMERIC:
                try:
                    data[key] = NUMERIC[key](float(val.replace(",", ".")))
                except ValueError:
                    continue
            else:
                data[key] = val
        if data.get("video_ref", "").lower() == "total" or "title" not in data and "video_ref" not in data:
            continue
        data.setdefault("video_ref", data.get("title", "?"))
        data.setdefault("title", data["video_ref"])
        if "format" not in data and data.get("duration_s"):
            data["format"] = "short" if data["duration_s"] <= 180 else "long"
        out.append(MetricRecord(**data))
    return out


def demo_records(n: int = 18, seed: int = 7) -> list[MetricRecord]:
    """Dados SINTÉTICOS para demonstração da interface. Nunca misturados com dados reais."""
    rnd = random.Random(seed)
    hooks = ["pergunta", "afirmação", "humor"]
    themes = ["espaço", "história", "psicologia"]
    out = []
    for i in range(n):
        fmt = "short" if i % 3 else "long"
        views = int(rnd.lognormvariate(7 if fmt == "short" else 6, 1))
        out.append(MetricRecord(
            video_ref=f"demo_{i:02}", title=f"[DEMO] Vídeo de demonstração {i + 1}", theme=themes[i % 3],
            niche="ciencia_espaco", format=fmt, hook=hooks[i % 3],
            duration_s=rnd.randint(20, 55) if fmt == "short" else rnd.randint(300, 720),
            views=views, impressions=views * rnd.randint(5, 15), ctr=round(rnd.uniform(2, 9), 1),
            avg_view_pct=round(rnd.uniform(40, 110) if fmt == "short" else rnd.uniform(20, 55), 1),
            watch_time_h=round(views * rnd.uniform(0.005, 0.05), 1), subs_gained=rnd.randint(0, 40),
            revenue_usd=None, demo=True, source="demo",
        ))
    return out


def _group(records: list[MetricRecord], key: str) -> list[dict]:
    groups: dict[str, list[MetricRecord]] = {}
    for r in records:
        k = getattr(r, key)
        if k is None and key == "duration_s":
            continue
        if key == "duration_s":
            k = "≤30s" if r.duration_s <= 30 else "31–60s" if r.duration_s <= 60 else "61–180s" if r.duration_s <= 180 else ">3min"
        groups.setdefault(str(k or "não informado"), []).append(r)

    def avg(rs: list[MetricRecord], f: str):
        vals = [getattr(r, f) for r in rs if getattr(r, f) is not None]
        return round(mean(vals), 2) if vals else None

    return [{"group": g, "n": len(rs), "views_avg": avg(rs, "views"), "ctr_avg": avg(rs, "ctr"),
             "avg_view_pct": avg(rs, "avg_view_pct"), "subs_avg": avg(rs, "subs_gained"),
             "sample_ok": len(rs) >= MIN_SAMPLE} for g, rs in sorted(groups.items())]


def build_report(records: list[MetricRecord], demo: bool) -> AnalyticsReport:
    def tot(f: str):
        vals = [getattr(r, f) for r in records if getattr(r, f) is not None]
        return float(sum(vals)) if vals else None

    comps = {k: _group(records, k) for k in ("format", "hook", "theme", "duration_s")}
    recs: list[str] = []
    fmt = [g for g in comps["format"] if g["sample_ok"] and g["avg_view_pct"] is not None]
    if len(fmt) >= 2:
        best = max(fmt, key=lambda g: g["avg_view_pct"])
        recs.append(f"Maior % média visualizada em '{best['group']}' ({best['avg_view_pct']}%). Correlação, não causalidade.")
    hooks = [g for g in comps["hook"] if g["sample_ok"] and g["views_avg"] is not None]
    if len(hooks) >= 2:
        best = max(hooks, key=lambda g: g["views_avg"])
        recs.append(f"Gancho '{best['group']}' com mais visualizações médias; repita o teste mantendo tema e horário.")
    if not recs:
        recs.append(f"Amostra insuficiente: são necessários ≥ {MIN_SAMPLE} vídeos por grupo para comparar.")
    limitations = ["Métricas ausentes não são estimadas.", "Grupos pequenos têm alta variância."]
    if demo:
        limitations.insert(0, "DADOS SINTÉTICOS DE DEMONSTRAÇÃO — não representam nenhum canal real.")
    return AnalyticsReport(
        demo=demo, records=len(records),
        totals={"views": tot("views"), "impressions": tot("impressions"), "watch_time_h": tot("watch_time_h"),
                "subs_gained": tot("subs_gained"), "revenue_usd": tot("revenue_usd")},
        comparisons=comps, recommendations=recs, limitations=limitations,
    )


class AnalyticsAgent(Agent):
    name = "analytics"
    title = "Analytics Agent"
    description = "Importa métricas autorizadas, compara formatos/ganchos/temas e recomenda experimentos. Demo sempre identificado."
    task_types = ("analytics_report",)
    owned_kinds = frozenset({"metrics"})

    def run(self, task: Task, ctx: AgentContext) -> TaskResult:
        demo = bool(ctx.param("demo", False))
        records = demo_records() if demo else [m for m in ctx.store.list("metrics", MetricRecord) if not m.demo]
        report = build_report(records, demo)
        return TaskResult(summary=f"Relatório {'DEMO' if demo else 'real'} com {report.records} vídeos",
                          output={"report": report.model_dump(mode="json")})
