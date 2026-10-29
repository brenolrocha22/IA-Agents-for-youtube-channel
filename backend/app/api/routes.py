"""Rotas HTTP. Finas: validam a entrada e delegam ao orquestrador/armazenamento."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ..agents import AGENTS
from ..channels import channels
from ..config import output_dir
from ..production.branding import render_brand_assets
from ..agents.analytics import build_report, demo_records, parse_csv
from ..config import env, env_status, get_policy, load_json
from ..models import (MetricRecord, NicheReport, ProductionJob, QualityReport, Script, Task, TaskStatus, TrendRun,
                      VideoBrief, Workflow, now)
from ..orchestrator.orchestrator import ApprovalBlocked, get_orchestrator
from ..production import ffmpeg
from ..production.tts import get_tts
from ..agents.scriptwriter import estimate_seconds, get_script_provider
from ..research import wikimedia as wm
from ..research.youtube import YouTubeCompetitionProvider
from ..store import get_store

router = APIRouter(prefix="/api")


def _404(what: str):
    raise HTTPException(404, f"{what} não encontrado")


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "time": now().isoformat()}


# ---------------- Dashboard ----------------
@router.get("/dashboard")
def dashboard() -> dict:
    s = get_store()
    tasks = s.list("tasks", Task, limit=1000)
    wfs = s.list("workflows", Workflow, limit=200)
    jobs = s.list("jobs", ProductionJob, limit=200)
    by_status = {st.value: sum(t.status == st for t in tasks) for st in TaskStatus}
    report = next(iter(s.list("niche_reports", NicheReport, limit=1)), None)
    trend = next((r for r in s.list("trend_runs", TrendRun, limit=10) if r.lang == "pt"), None)
    return {
        "projects": [{"id": w.id, "title": w.title, "kind": w.kind, "status": w.status, "created_at": w.created_at} for w in wfs[:8]],
        "project_count": len(wfs),
        "tasks_by_status": by_status,
        "active_tasks": [{"id": t.id, "type": t.type, "agent": t.agent, "status": t.status}
                         for t in tasks if t.status in (TaskStatus.running, TaskStatus.awaiting_approval)][:10],
        "videos_rendered": sum(j.status == "rendered" for j in jobs),
        "videos_failed": sum(j.status == "failed" for j in jobs),
        "errors": s.logs(limit=8, level="error"),
        "cost_estimated_usd": round(sum(w.cost_estimated_usd for w in wfs), 4),
        "tokens_estimated": sum(w.tokens_estimated for w in wfs),
        "api_calls": sum(w.api_calls for w in wfs),
        "top_niches": [{"name": n.name, "total": n.total, "recommended": n.recommended, "confidence": n.confidence}
                       for n in (report.rankings.get("pt", []) if report else [])[:5]],
        "niche_report_date": report.created_at if report else None,
        "opportunities": [i.model_dump() for i in (trend.items if trend else []) if i.emerging and not i.sensitive][:6],
        "trend_date": trend.collected_at if trend else None,
    }


# ---------------- Canais ----------------
def _branding_files(channel_id: str) -> dict[str, str]:
    """Caminhos com versão (mtime) para o navegador nunca mostrar uma arte antiga do cache."""
    folder = output_dir() / "branding" / channel_id
    if not folder.exists():
        return {}
    return {p.stem: f"output/branding/{channel_id}/{p.name}?v={p.stat().st_mtime_ns}" for p in sorted(folder.glob("*.png"))}


@router.get("/channels")
def list_channels() -> list[dict]:
    return [{**c, "branding": _branding_files(c["id"])} for c in channels()]


@router.post("/channels/{channel_id}/branding")
def make_branding(channel_id: str) -> dict:
    ch = next((c for c in channels() if c["id"] == channel_id), None) or _404("Canal")
    render_brand_assets(ch, output_dir() / "branding" / channel_id)
    get_store().log("info", "branding", f"Identidade visual gerada para {ch['name']}")
    return {"channel_id": channel_id, "branding": _branding_files(channel_id)}


# ---------------- Settings ----------------
@router.get("/settings")
def settings() -> dict:
    yt = YouTubeCompetitionProvider()
    tts = get_tts()
    script = get_script_provider()
    return {
        "env": env_status(),
        "policy": get_policy().model_dump(),
        "providers": [
            {"name": "Wikimedia (demanda e tendências)", "status": "ativo", "detail": "API pública, sem chave"},
            {"name": "YouTube Data API (concorrência)", "status": "ativo" if yt.is_configured() else "desativado",
             "detail": "Configure YOUTUBE_API_KEY" if not yt.is_configured() else "Somente dados públicos"},
            {"name": "Google Trends", "status": "indisponível", "detail": "Sem API pública aberta"},
            {"name": f"Roteiros ({script.name})", "status": "ativo",
             "detail": "Modo híbrido: provedor LLM ainda não implementado" if script.name == "template" else ""},
            {"name": f"Narração ({tts.name})", "status": "ativo", "detail": tts.license},
            {"name": "FFmpeg", **({"status": "ativo", "detail": ffmpeg.available().get("version", "")}
                                  if ffmpeg.available()["available"] else {"status": "erro", "detail": "não encontrado"})},
            {"name": "Publicação YouTube", "status": "desativado", "detail": "Exige OAuth oficial e aprovação humana (D09)"},
        ],
        "production": {"short": "1080x1920, H.264/AAC, 30 fps, loop", "long": "1920x1080, H.264/AAC, 30 fps",
                       "tts_voice_pt": env("TTS_VOICE_PT", "Microsoft Maria Desktop")},
        "scoring": load_json("scoring.json"),
    }


# ---------------- Nichos ----------------
@router.get("/niches/latest")
def niches_latest() -> NicheReport | None:
    return next(iter(get_store().list("niche_reports", NicheReport, limit=1)), None)


@router.get("/niches/reports")
def niche_reports() -> list[dict]:
    return [{"id": r.id, "created_at": r.created_at, "report_path": r.report_path, "markets": r.markets}
            for r in get_store().list("niche_reports", NicheReport, limit=30)]


class ResearchIn(BaseModel):
    markets: list[Literal["pt", "en"]] = ["pt", "en"]
    days: int = Field(7, ge=2, le=14)


@router.post("/niches/research")
def niches_research(body: ResearchIn) -> Workflow:
    return get_orchestrator().create_workflow("niche_research", body.model_dump(), "Pesquisa de nichos e tendências")


@router.get("/niches/config")
def niches_config() -> dict:
    return {"niches": load_json("niches.json")["niches"], "scoring": load_json("scoring.json")}


# ---------------- Tendências ----------------
@router.get("/trends")
def trends(lang: str = "pt", category: str | None = None, emerging: bool = False, run_id: str | None = None) -> dict:
    runs = [r for r in get_store().list("trend_runs", TrendRun, limit=50) if r.lang == lang]
    run = next((r for r in runs if r.id == run_id), None) if run_id else (runs[0] if runs else None)
    if not run:
        return {"run": None, "items": [], "categories": []}
    items = [i for i in run.items if (not category or i.category == category) and (not emerging or i.emerging)]
    return {"run": {"id": run.id, "collected_at": run.collected_at, "window": run.window, "source": run.source},
            "items": items, "categories": sorted({i.category for i in run.items})}


@router.get("/trends/runs")
def trend_runs() -> list[dict]:
    return [{"id": r.id, "lang": r.lang, "collected_at": r.collected_at, "items": len(r.items), "window": r.window}
            for r in get_store().list("trend_runs", TrendRun, limit=50)]


# ---------------- Conteúdo ----------------
@router.get("/topics/search")
def topic_search(q: str, lang: str = "pt") -> list[dict]:
    if len(q.strip()) < 2:
        return []
    try:
        return wm.search_titles(get_store(), lang, q.strip())
    except Exception as exc:
        raise HTTPException(502, f"Busca indisponível: {exc}")


class VideoIn(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    channel_id: str = "natureza"
    niche_id: str = "natureza_animais"
    format: Literal["short", "long"] = "short"
    tone: Literal["comico", "educativo", "criativo"] = "comico"
    language: Literal["pt", "en"] = "pt"
    items: list[str] = Field(default_factory=list, max_length=10)  # formato Lista/Top N


@router.post("/videos")
def create_video(body: VideoIn) -> Workflow:
    label = "Short" if body.format == "short" else "Vídeo longo"
    ch = next((c for c in channels() if c["id"] == body.channel_id), {})
    params = {**body.model_dump(), "require_footage": bool(ch.get("require_footage"))}
    return get_orchestrator().create_workflow("video", params, f"{label}: {body.topic}")


@router.get("/briefs")
def briefs() -> list[VideoBrief]:
    return get_store().list("briefs", VideoBrief, limit=100)


@router.get("/scripts")
def scripts() -> list[Script]:
    return get_store().list("scripts", Script, limit=100)


@router.get("/scripts/{script_id}")
def script(script_id: str) -> dict:
    s = get_store().get("scripts", script_id, Script) or _404("Roteiro")
    reports = [r for r in get_store().list("quality_reports", QualityReport) if r.target_id == script_id]
    return {"script": s, "quality": reports[0] if reports else None}


class SectionEdit(BaseModel):
    narration: str = Field(min_length=1, max_length=2000)


class ScriptEdit(BaseModel):
    title: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=5000)
    planned_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$|^$")
    sections: list[SectionEdit] | None = None


@router.put("/scripts/{script_id}")
def edit_script(script_id: str, body: ScriptEdit) -> dict:
    store = get_store()
    s = store.get("scripts", script_id, Script) or _404("Roteiro")
    if s.status == "approved" and body.sections:
        raise HTTPException(409, "Roteiro já aprovado; o texto não pode mais ser alterado")
    if body.title is not None:
        s.title = body.title
    if body.description is not None:
        s.description = body.description
    if body.planned_date is not None:
        s.planned_date = body.planned_date or None
    if body.sections is not None:
        if len(body.sections) != len(s.sections):
            raise HTTPException(422, "Número de seções diferente do roteiro")
        changed = False
        for sec, edit in zip(s.sections, body.sections):
            if sec.narration != edit.narration:
                sec.narration, sec.est_seconds, changed = edit.narration, estimate_seconds(edit.narration), True
        if changed:
            s.edited_by_human = True
            s.est_duration_s = round(sum(x.est_seconds for x in s.sections) + 0.35 * len(s.sections), 1)
    s.updated_at = now()
    store.put("scripts", s)
    result = get_orchestrator().run_adhoc("fact_review", {"script_id": s.id})
    return {"script": s, "quality": store.get("quality_reports", result.output["quality_report_id"], QualityReport)}


@router.get("/calendar")
def calendar() -> list[dict]:
    return [{"script_id": s.id, "title": s.title, "date": s.planned_date, "format": s.format, "status": s.status}
            for s in get_store().list("scripts", Script, limit=200) if s.planned_date]


# ---------------- Produção ----------------
@router.get("/jobs")
def jobs() -> list[ProductionJob]:
    return get_store().list("jobs", ProductionJob, limit=100)


@router.get("/quality")
def quality(target_id: str | None = None) -> list[QualityReport]:
    reps = get_store().list("quality_reports", QualityReport, limit=300)
    return [r for r in reps if not target_id or r.target_id == target_id]


# ---------------- Agentes / tarefas ----------------
@router.get("/agents")
def agents() -> list[dict]:
    tasks = get_store().list("tasks", Task, limit=2000)
    out = []
    for name, a in [("orchestrator", None), *AGENTS.items()]:
        mine = [t for t in tasks if t.agent == name]
        last = max((t.completed_at or t.started_at or t.created_at for t in mine), default=None)
        out.append({
            "name": name, "title": a.title if a else "Orchestrator",
            "description": a.description if a else "Divide objetivos em tarefas, controla dependências, limites e aprovações humanas.",
            "task_types": list(a.task_types) if a else ["editorial_approval", "final_approval"],
            "counts": {st.value: sum(t.status == st for t in mine) for st in TaskStatus},
            "last_activity": last,
            # Só mostra erro se a tarefa MAIS RECENTE do agente falhou; cancelamentos em cascata não são erros.
            "last_error": (lambda recent: recent.errors[-1] if recent and recent.status == TaskStatus.failed and recent.errors else None)(
                max(mine, key=lambda t: t.completed_at or t.started_at or t.created_at, default=None)),
            "tokens_estimated": sum(t.result.tokens_estimated for t in mine if t.result),
            "cost_estimated_usd": round(sum(t.result.cost_estimated_usd for t in mine if t.result), 4),
        })
    return out


@router.get("/workflows")
def workflows() -> list[Workflow]:
    return get_store().list("workflows", Workflow, limit=100)


@router.get("/workflows/{wf_id}")
def workflow(wf_id: str) -> dict:
    wf = get_store().get("workflows", wf_id, Workflow) or _404("Workflow")
    return {"workflow": wf, "tasks": get_orchestrator().tasks_of(wf)}


@router.post("/workflows/{wf_id}/cancel")
def cancel(wf_id: str) -> Workflow:
    try:
        return get_orchestrator().cancel_workflow(wf_id)
    except KeyError:
        _404("Workflow")


@router.post("/workflows/{wf_id}/rework")
def rework(wf_id: str) -> Workflow:
    try:
        return get_orchestrator().rework(wf_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/tasks/{task_id}/context")
def task_context(task_id: str) -> dict:
    try:
        return get_orchestrator().approval_context(task_id)
    except ValueError:
        _404("Tarefa")


@router.get("/tasks")
def tasks(status: TaskStatus | None = None, limit: int = 100) -> list[Task]:
    ts = get_store().list("tasks", Task, limit=1000)
    return [t for t in ts if not status or t.status == status][:limit]


class Decision(BaseModel):
    note: str = Field("", max_length=500)


@router.post("/tasks/{task_id}/approve")
def approve(task_id: str, body: Decision) -> Task:
    try:
        return get_orchestrator().approve(task_id, "proprietário", body.note)
    except ApprovalBlocked as exc:
        raise HTTPException(409, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/tasks/{task_id}/reject")
def reject(task_id: str, body: Decision) -> Task:
    try:
        return get_orchestrator().reject(task_id, "proprietário", body.note)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/tasks/{task_id}/retry")
def retry(task_id: str) -> Task:
    try:
        return get_orchestrator().retry_task(task_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/logs")
def logs(limit: int = 100, task_id: str | None = None) -> list[dict]:
    return get_store().logs(limit=min(limit, 500), task_id=task_id)


# ---------------- Analytics ----------------
@router.get("/analytics")
def analytics(demo: bool = False) -> dict[str, Any]:
    records = demo_records() if demo else [m for m in get_store().list("metrics", MetricRecord) if not m.demo]
    return {"report": build_report(records, demo), "records": records}


@router.post("/analytics/import")
async def analytics_import(file: UploadFile) -> dict:
    raw = await file.read()
    if len(raw) > 5_000_000:
        raise HTTPException(413, "Arquivo maior que 5 MB")
    text = raw.decode("utf-8-sig", errors="replace")
    records = parse_csv(text)
    if not records:
        raise HTTPException(422, "Nenhuma linha reconhecida. Use o CSV exportado do YouTube Studio ou o modelo do README.")
    for r in records:
        get_store().put("metrics", r)
    return {"imported": len(records)}


@router.post("/analytics/metrics")
def add_metric(body: MetricRecord) -> MetricRecord:
    body.demo, body.source = False, "manual"
    get_store().put("metrics", body)
    return body
