"""Rotas do módulo Reality Kitchen Stories."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..agents.reality_kitchen import SHOWS
from ..models import (KitchenCatalog, KitchenFact, KitchenStory, LicensedAsset, ProductionJob, ResearchSource, Script, Task,
                      TaskStatus, Workflow)
from ..orchestrator.orchestrator import get_orchestrator
from ..store import get_store

router = APIRouter(prefix="/api/kitchen")


def _story(story_id: str) -> KitchenStory:
    s = get_store().get("kitchen_stories", story_id, KitchenStory)
    if not s:
        raise HTTPException(404, "Dossiê não encontrado")
    return s


@router.get("/overview")
def overview() -> dict:
    s = get_store()
    cats = s.list("kitchen_catalogs", KitchenCatalog)
    stories = s.list("kitchen_stories", KitchenStory)
    scripts = [x for x in s.list("scripts", Script, limit=300) if x.story_id]
    script_ids = {x.id for x in scripts}
    jobs = [j for j in s.list("jobs", ProductionJob, limit=300) if j.script_id in script_ids]
    wfs = [w for w in s.list("workflows", Workflow, limit=200) if w.kind == "kitchen_short"]
    wf_ids = {w.id for w in wfs}
    approvals = [t for t in s.list("tasks", Task, limit=1000) if t.workflow_id in wf_ids and t.status == TaskStatus.awaiting_approval]
    assets = s.list("licensed_assets", LicensedAsset)
    pending = [{"story_id": st.id, "restaurant": st.restaurant, "fact": f.model_dump()} for st in stories for f in st.facts if not f.verified]
    return {
        "shows": [{"id": k, "name": v["name"]} for k, v in SHOWS.items()],
        "counts": {
            "episodes": sum(len(c.episodes) for c in cats),
            "restaurants": len({e.restaurant for c in cats for e in c.episodes}),
            "stories": len(stories), "pending_verification": len(pending), "scripts": len(scripts),
            "in_production": sum(j.status in ("queued", "running") for j in jobs),
            "videos_done": sum(j.status == "rendered" for j in jobs), "approvals": len(approvals), "assets": len(assets),
        },
        "catalogs": [{"id": c.id, "show": c.show, "episodes": len(c.episodes), "collected_at": c.collected_at, "source": c.source} for c in cats],
        "stories": [{"id": st.id, "restaurant": st.restaurant, "show": st.show, "air_year": st.air_year,
                     "facts": len(st.facts), "verified": sum(f.verified for f in st.facts), "missing_stages": st.missing_stages} for st in stories],
        "scripts": [{"id": x.id, "title": x.title, "status": x.status, "est_duration_s": x.est_duration_s} for x in scripts],
        "jobs": [{"id": j.id, "status": j.status, "stage": j.stage, "progress": j.progress, "video": j.outputs.get("video")} for j in jobs],
        "workflows": [{"id": w.id, "title": w.title, "status": w.status} for w in wfs],
        "approvals": [{"id": t.id, "type": t.type, "workflow_id": t.workflow_id} for t in approvals],
        "pending": pending[:50],
        "assets": assets,
    }


class CatalogIn(BaseModel):
    show_id: Literal["restaurant_impossible", "pesadelo_br", "kitchen_nightmares_us"] = "restaurant_impossible"


@router.post("/catalog")
def catalog(body: CatalogIn) -> Workflow:
    return get_orchestrator().create_workflow("kitchen_catalog", body.model_dump(), f"Catálogo: {SHOWS[body.show_id]['name']}")


@router.get("/episodes")
def episodes(show_id: str = "pesadelo_br", q: str = "") -> list[dict]:
    cat = get_store().get("kitchen_catalogs", show_id, KitchenCatalog)
    if not cat:
        return []
    ql = q.lower().strip()
    return [e.model_dump() for e in cat.episodes if not ql or ql in e.restaurant.lower() or ql in (e.location or "").lower()][:200]


class StoryIn(BaseModel):
    episode_id: str = Field(min_length=3)


@router.post("/stories")
def create_story(body: StoryIn) -> KitchenStory:
    """Pesquisa rápida e síncrona (usa o catálogo em cache)."""
    try:
        res = get_orchestrator().run_adhoc("kitchen_story", body.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return _story(res.output["story_id"])


@router.get("/stories/{story_id}")
def get_story(story_id: str) -> KitchenStory:
    return _story(story_id)


class FactIn(BaseModel):
    text: str = Field(min_length=10, max_length=600)
    category: Literal["exibido_no_programa", "declaracao", "posterior_verificado", "interpretacao_editorial"]
    stage: Literal["contexto", "conflito", "intervencao", "transformacao", "resultado"]
    source_title: str = Field(min_length=3, max_length=200)
    source_url: str = Field(pattern=r"^https?://")


@router.post("/stories/{story_id}/facts")
def add_fact(story_id: str, body: FactIn) -> KitchenStory:
    """Fato adicionado pelo proprietário (já verificado por ele), sempre com fonte."""
    story = _story(story_id)
    src = ResearchSource(provider="manual", title=body.source_title, url=body.source_url, note="Adicionada pelo proprietário")
    story.sources.append(src)
    story.facts.append(KitchenFact(text=body.text, category=body.category, stage=body.stage, source_id=src.id,
                                   verified=True, verified_by="proprietário", added_by="proprietário"))
    story.missing_stages = [s for s in story.missing_stages if s != body.stage]
    get_store().put("kitchen_stories", story)
    return story


class VerifyIn(BaseModel):
    verified: bool = True
    by: str = Field("proprietário", max_length=80)


@router.post("/stories/{story_id}/facts/{fact_id}/verify")
def verify_fact(story_id: str, fact_id: str, body: VerifyIn) -> KitchenStory:
    story = _story(story_id)
    fact = next((f for f in story.facts if f.id == fact_id), None)
    if not fact:
        raise HTTPException(404, "Fato não encontrado")
    fact.verified, fact.verified_by = body.verified, body.by if body.verified else None
    get_store().put("kitchen_stories", story)
    return story


@router.post("/stories/{story_id}/short")
def create_short(story_id: str) -> Workflow:
    story = _story(story_id)
    if not any(f.verified for f in story.facts):
        raise HTTPException(409, "Verifique ao menos um fato do dossiê antes de gerar o roteiro")
    return get_orchestrator().create_workflow("kitchen_short", {"story_id": story_id}, f"Kitchen Short: {story.restaurant}")


class AssetIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    origin: str = Field(min_length=3, max_length=500)
    license: str = Field(min_length=3, max_length=300)
    scope: str = Field(min_length=3, max_length=300)
    restrictions: str = Field("", max_length=500)


@router.post("/assets")
def add_asset(body: AssetIn) -> LicensedAsset:
    asset = LicensedAsset(**body.model_dump())
    get_store().put("licensed_assets", asset)
    return asset
