"""Pontuação explicável de nichos (0–100). Metodologia em SPEC.md §2; pesos em config/scoring.json."""
from __future__ import annotations

import math
from typing import Any

from ..models import CriterionScore, Evidence, NicheScore, RiskFlag

LABELS = {
    "demanda": "Demanda observável",
    "crescimento": "Potencial de crescimento",
    "concorrencia": "Concorrência / diferenciação",
    "retencao": "Retenção potencial",
    "monetizacao": "Monetização",
    "producao": "Facilidade e custo de produção",
    "risco": "Risco de conformidade (maior = mais seguro)",
}

METHODOLOGY = (
    "Cada critério recebe nota de 0 a 100 e é classificado como observado, estimativa ou hipótese. "
    "Demanda: média diária de pageviews (últimos 3 meses completos) dos artigos-semente da Wikipedia no "
    "idioma, em escala log10 (100/dia = 0, 100 mil/dia = 100). Crescimento: 50 + 50·log2(últimos 3 meses / "
    "3 meses anteriores). Concorrência: YouTube Data API (vídeos públicos dos últimos 30 dias) quando "
    "configurada; caso contrário, hipótese editorial. Retenção, monetização, produção e risco: hipóteses ou "
    "estimativas documentadas em config/niches.json. Critérios desconhecidos saem da média e os pesos são "
    "renormalizados. Riscos críticos impedem a recomendação, independentemente da nota."
)


def clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


def demand_score(avg_daily: float | None, scale: dict[str, float]) -> float | None:
    if not avg_daily or avg_daily <= 0:
        return None
    lo, hi = scale["log10_min_daily_views"], scale["log10_max_daily_views"]
    return round(clamp(100 * (math.log10(avg_daily) - lo) / (hi - lo)), 1)


def growth_score(ratio: float | None) -> float | None:
    if not ratio or ratio <= 0:
        return None
    return round(clamp(50 + 50 * math.log2(ratio)), 1)


def score_niche(
    niche: dict[str, Any],
    market: str,
    metrics: dict[str, Any],
    competition: dict[str, Any] | None,
    source_ids: list[str],
    scoring: dict[str, Any],
) -> NicheScore:
    weights: dict[str, float] = scoring["weights"]
    hyp = niche.get("hypotheses", {})
    criteria: list[CriterionScore] = []

    def add(key: str, score: float | None, evidence: Evidence, rationale: str, srcs: list[str] | None = None):
        criteria.append(CriterionScore(
            key=key, label=LABELS[key], score=score, weight=weights.get(key, 0.0),
            evidence=evidence if score is not None else Evidence.desconhecido,
            rationale=rationale, source_ids=srcs or [],
        ))

    avg = metrics.get("avg_daily_views")
    add("demanda", demand_score(avg, scoring["demand_scale"]), Evidence.observado,
        f"Média de {avg:,.0f} pageviews/dia por artigo-semente ({metrics.get('seeds_found', 0)} artigos)."
        if avg else "Sem pageviews disponíveis para os artigos-semente.", source_ids)

    ratio = metrics.get("growth_ratio")
    add("crescimento", growth_score(ratio), Evidence.observado,
        f"Últimos 3 meses / 3 meses anteriores = {ratio:.2f}. Sazonalidade não corrigida." if ratio
        else "Série histórica insuficiente.", source_ids)

    comp_score = competition.get("score") if competition else None
    if comp_score is not None:
        add("concorrencia", comp_score, Evidence.observado,
            f"{competition['videos']} vídeos públicos recentes, {len(competition['channels'])} canais distintos, "
            f"mediana de {competition['median_views']:,.0f} visualizações (últimos {competition['window_days']} dias).")
    else:
        val, why = hyp.get("concorrencia", [None, "Sem dado."])
        add("concorrencia", val, Evidence.hipotese, f"Hipótese: {why}")

    for key in ("retencao", "monetizacao"):
        val, why = hyp.get(key, [None, "Sem dado."])
        add(key, val, Evidence.hipotese, f"Hipótese: {why}")
    for key in ("producao", "risco"):
        val, why = hyp.get(key, [None, "Sem dado."])
        add(key, val, Evidence.estimativa, f"Estimativa: {why}")

    known = [c for c in criteria if c.score is not None]
    wsum = sum(c.weight for c in known)
    total = round(sum(c.score * c.weight for c in known) / wsum, 1) if wsum else None  # type: ignore[operator]
    total_w = sum(weights.values()) or 1.0
    coverage = round(wsum / total_w, 2)
    observed_share = sum(c.weight for c in known if c.evidence == Evidence.observado) / total_w
    confidence = "alta" if observed_share >= 0.5 else "média" if observed_share >= 0.3 else "baixa"

    risks = [RiskFlag(**r) for r in niche.get("risks", [])]
    critical = [r for r in risks if r.severity == "critical"]
    blocked = f"Risco crítico: {critical[0].label}" if critical else None
    recommended = (
        not critical and total is not None
        and total >= scoring.get("recommend_min_score", 55)
        and coverage >= scoring.get("recommend_min_coverage", 0.4)
    )
    return NicheScore(
        niche_id=niche["id"], name=niche["name"], market=market, total=total, coverage=coverage,
        confidence=confidence, recommended=recommended, blocked_reason=blocked, criteria=criteria,
        risks=risks, opportunities=niche.get("opportunities", []),
        competitors=(competition or {}).get("channels", [])[:10], metrics=metrics,
    )


def rank(scores: list[NicheScore]) -> list[NicheScore]:
    return sorted(scores, key=lambda s: (s.total is None, -(s.total or 0)))
