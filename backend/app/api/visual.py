"""Rotas do Visual Hunter: plano visual por roteiro e ações humanas de validação."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..agents.visual_hunter import metadata_score, prepare_candidate, rank_key, subject_for
from ..config import output_dir
from ..models import ResearchSource, Script, ScriptSection, VisualPlan, Workflow, now
from ..orchestrator.orchestrator import get_orchestrator
from ..research.footage import providers
from ..research.http import ApiBudget
from ..store import get_store

router = APIRouter(prefix="/api/visual")


def _plan(plan_id: str) -> VisualPlan:
    p = get_store().get("visual_plans", plan_id, VisualPlan)
    if not p:
        raise HTTPException(404, "Plano visual não encontrado")
    return p


def _scene(plan: VisualPlan, index: int):
    if not 0 <= index < len(plan.scenes):
        raise HTTPException(404, "Cena não encontrada")
    return plan.scenes[index]


def _save(plan: VisualPlan) -> dict:
    plan.updated_at = now()
    get_store().put("visual_plans", plan)
    return {"plan": plan, "coverage": plan.coverage()}


@router.get("/plans")
def plans() -> list[dict]:
    out = []
    for p in get_store().list("visual_plans", VisualPlan, limit=50):
        cands = [c for s in p.scenes for c in s.candidates]
        out.append({"id": p.id, "script_id": p.script_id, "updated_at": p.updated_at, "subject": p.subject_en, "providers": p.providers,
                    "scenes": len(p.scenes), "coverage": p.coverage(),
                    "validated": sum(s.validation == "validada" for s in p.scenes),
                    "review": sum(s.validation == "revisao" for s in p.scenes),
                    "pending": sum(s.validation in ("pendente", "rejeitada") for s in p.scenes),
                    "found": len(cands), "downloaded": sum(bool(c.local_path) for c in cands),
                    "licenses": sorted({c.license for c in cands if c.local_path})})
    return out


@router.get("/plans/{plan_id}")
def plan(plan_id: str) -> dict:
    p = _plan(plan_id)
    return {"plan": p, "coverage": p.coverage()}


class ValidateIn(BaseModel):
    status: Literal["validada", "rejeitada"]
    note: str = Field("", max_length=300)
    by: str = Field("proprietário", max_length=80)


@router.post("/plans/{plan_id}/scenes/{index}/validate")
def validate(plan_id: str, index: int, body: ValidateIn) -> dict:
    p = _plan(plan_id)
    s = _scene(p, index)
    if body.status == "validada" and not s.selected_id:
        raise HTTPException(409, "Selecione um material antes de validar")
    s.validation, s.validated_by = body.status, body.by
    s.validation_method = "inspeção visual humana (amostra de quadros / reprodução)"
    if body.note:
        s.note = body.note
    return _save(p)


class SelectIn(BaseModel):
    candidate_id: str
    clip_start: float | None = Field(None, ge=0)


@router.post("/plans/{plan_id}/scenes/{index}/select")
def select(plan_id: str, index: int, body: SelectIn) -> dict:
    p = _plan(plan_id)
    s = _scene(p, index)
    i = next((k for k, c in enumerate(s.candidates) if c.id == body.candidate_id), None)
    if i is None:
        raise HTTPException(404, "Material não está entre os candidatos da cena")
    c = s.candidates[i]
    if c.license_status == "rejeitada":
        raise HTTPException(409, f"Licença rejeitada: {c.license_note}")
    if not c.local_path:
        try:
            s.candidates[i] = prepare_candidate(c, output_dir() / "footage" / p.script_id)
        except Exception as exc:
            raise HTTPException(502, f"Falha ao baixar o material: {exc}")
    s.selected_id, s.clip_start = c.id, body.clip_start
    s.validation, s.validated_by = "revisao", None  # material novo precisa de nova validação
    return _save(p)


class SearchIn(BaseModel):
    query: str = Field(min_length=3, max_length=120)


@router.post("/plans/{plan_id}/scenes/{index}/search")
def search(plan_id: str, index: int, body: SearchIn) -> dict:
    """Nova busca com palavras-chave escolhidas pelo humano; adiciona candidatos ranqueados à cena."""
    p = _plan(plan_id)
    s = _scene(p, index)
    _, syn = subject_for(p.subject_en)
    budget, found = ApiBudget(20), {}
    for prov in providers():
        try:
            for c in prov.search(get_store(), body.query, budget):
                found.setdefault(c.id, c)
        except Exception as exc:
            p.log.append(f"{prov.name} falhou para '{body.query}': {exc}")
    known = {c.id for c in s.candidates}
    new = []
    for c in found.values():
        if c.id in known or c.license_status == "rejeitada":
            continue
        score, terms = metadata_score(c, syn, s.action)
        new.append(c.model_copy(update={"metadata_score": score, "matched_terms": terms}))
    new.sort(key=rank_key, reverse=True)
    s.candidates += new[:8]
    s.queries = list(dict.fromkeys([*s.queries, body.query]))
    p.log.append(f"Cena {index + 1}: nova busca '{body.query}' → {len(new)} candidatos")
    return _save(p)


class AdaptIn(BaseModel):
    narration: str = Field(min_length=10, max_length=600)
    action: str = Field(min_length=2, max_length=80)
    candidate_id: str


@router.post("/plans/{plan_id}/scenes/{index}/adapt")
def adapt(plan_id: str, index: int, body: AdaptIn) -> dict:
    """Aprova uma adaptação factual da narração compatível com o material disponível (decisão humana)."""
    p = _plan(plan_id)
    s = _scene(p, index)
    script = get_store().get("scripts", p.script_id, Script)
    if script.status == "approved":
        raise HTTPException(409, "Roteiro já aprovado: use 'Editar e refazer' antes de adaptar")
    script.sections[index].narration = body.narration
    script.sections[index].visual_action = body.action
    script.edited_by_human = True
    get_store().put("scripts", script)
    s.narration, s.action, s.adaptation = body.narration, body.action, None
    get_store().put("visual_plans", p)
    return select(plan_id, index, SelectIn(candidate_id=body.candidate_id))


class ManualSection(BaseModel):
    kind: Literal["hook", "context", "point", "payoff", "loop", "cta"] = "point"
    heading: str = Field(min_length=1, max_length=60)
    narration: str = Field(min_length=5, max_length=600)
    on_screen_text: str = ""
    visual_query: str | None = None
    visual_action: str | None = None


class ManualScriptIn(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    channel_id: str = "natureza"
    topic_en: str = Field(min_length=2, max_length=60)
    tone: str = "documentario"
    sources: list[dict] = Field(min_length=1)
    sections: list[ManualSection] = Field(min_length=2, max_length=12)


@router.post("/scripts")
def manual_script(body: ManualScriptIn) -> dict:
    """Roteiro escrito pelo proprietário → Visual Hunter → revisão → aprovação → produção."""
    srcs = [ResearchSource(provider="manual", title=s["title"], url=s["url"], license=s.get("license")) for s in body.sources]
    secs = [ScriptSection(**s.model_dump(), visual_note=f"Filmagem real: {s.visual_action or 'assunto'}", source_ids=[srcs[0].id])
            for s in body.sections]
    script = Script(brief_id="manual", format="short", language="pt", tone=body.tone, title=body.title,
                    title_variants=[body.title], description="", thumbnail_ideas=[], sections=secs, sources=srcs,
                    provider="proprietário", edited_by_human=True, channel_id=body.channel_id, topic_en=body.topic_en)
    script.est_duration_s = round(sum(len(s.narration.split()) / 2.3 for s in secs) + 0.3 * len(secs), 1)
    get_store().put("scripts", script)
    wf: Workflow = get_orchestrator().create_workflow("script_short", {"script_id": script.id, "channel_id": body.channel_id},
                                                      f"Short: {body.title}")
    return {"script_id": script.id, "workflow": wf}
