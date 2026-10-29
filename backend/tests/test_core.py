from app.agents.analytics import build_report, demo_records, parse_csv
from app.agents.quality import overlap_ratio
from app.config import get_policy
from app.models import Evidence, Workflow
from app.production.captions import build_cues, read_srt, write_srt
from app.research import scoring
from app.research.http import ApiBudget, LimitExceeded
from app.store import get_store

import pytest

CFG = {"weights": {"demanda": .25, "crescimento": .15, "concorrencia": .15, "retencao": .1, "monetizacao": .15,
                   "producao": .1, "risco": .1},
       "demand_scale": {"log10_min_daily_views": 2, "log10_max_daily_views": 5},
       "recommend_min_score": 55, "recommend_min_coverage": 0.4}


def test_store_roundtrip_and_cache():
    s = get_store()
    wf = Workflow(kind="analytics", title="x")
    s.put("workflows", wf)
    assert s.get("workflows", wf.id, Workflow).title == "x"
    assert s.count("workflows") == 1
    s.cache_set("k", {"a": 1}, 60)
    assert s.cache_get("k") == {"a": 1}
    s.cache_set("old", {"a": 1}, 0)
    assert s.cache_get("old") is None


def test_scales():
    scale = CFG["demand_scale"]
    assert scoring.demand_score(100, scale) == 0
    assert scoring.demand_score(100_000, scale) == 100
    assert scoring.demand_score(None, scale) is None
    assert scoring.growth_score(1.0) == 50
    assert scoring.growth_score(2.0) == 100
    assert scoring.growth_score(0.5) == 0


def test_unknown_criteria_are_renormalized_and_critical_risk_blocks():
    niche = {"id": "n", "name": "N", "hypotheses": {"retencao": [80, "x"], "monetizacao": [80, "x"],
                                                    "producao": [80, "x"], "risco": [80, "x"], "concorrencia": [80, "x"]},
             "risks": [{"code": "c", "label": "crítico", "severity": "critical"}]}
    s = scoring.score_niche(niche, "pt", {"avg_daily_views": None, "growth_ratio": None}, None, [], CFG)
    assert s.total == 80  # demanda e crescimento desconhecidos saem da média
    assert s.coverage == 0.6
    assert s.confidence == "baixa"
    assert not s.recommended and "crítico" in s.blocked_reason
    assert {c.key: c.evidence for c in s.criteria}["demanda"] == Evidence.desconhecido


def test_api_budget_limit():
    b = ApiBudget(2)
    b.consume()
    b.consume()
    with pytest.raises(LimitExceeded):
        b.consume()


def test_policy_is_immutable():
    p = get_policy()
    with pytest.raises(Exception):
        p.limits.max_retries = 99  # type: ignore[misc]


def test_captions_roundtrip(tmp_path):
    cues = build_cues("Marte tem o maior vulcão do Sistema Solar. Sim, é sério.", 0.0, 4.0, vertical=True)
    assert all(len(c["text"]) <= 26 for c in cues)
    assert abs(cues[-1]["end"] - 4.0) < 0.01
    write_srt(cues, tmp_path / "a.srt")
    back = read_srt(tmp_path / "a.srt")
    assert [c["text"] for c in back] == [c["text"] for c in cues]


def test_overlap_ratio():
    src = "o planeta tem o maior vulcão conhecido do sistema solar inteiro"
    assert overlap_ratio(src, [src]) == 1.0
    assert overlap_ratio("um texto totalmente diferente escrito com outras palavras aqui", [src]) == 0.0


def test_analytics_csv_and_demo_flag():
    csv_text = ("Content,Video title,Duration,Views,Impressions click-through rate (%)\n"
                "Total,,,100,\nabc,Meu vídeo,40,1234,5.5\n")
    recs = parse_csv(csv_text)
    assert len(recs) == 1 and recs[0].views == 1234 and recs[0].format == "short" and not recs[0].demo
    demo = demo_records()
    assert all(r.demo and r.title.startswith("[DEMO]") and r.revenue_usd is None for r in demo)
    rep = build_report(demo, demo=True)
    assert rep.demo and "SINTÉTICOS" in rep.limitations[0]
    assert build_report([], demo=False).recommendations[0].startswith("Amostra insuficiente")
