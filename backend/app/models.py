"""Contratos tipados compartilhados entre API, orquestrador e agentes."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    awaiting_approval = "awaiting_approval"


TERMINAL = {TaskStatus.completed, TaskStatus.failed, TaskStatus.cancelled}


class Evidence(str, Enum):
    observado = "observado"
    estimativa = "estimativa"
    hipotese = "hipótese"
    desconhecido = "desconhecido"


Severity = Literal["low", "medium", "high", "critical"]


# ---------- Orquestração ----------

class ExecutionLimits(BaseModel):
    timeout_s: int = 600
    max_retries: int = 1


class TaskResult(BaseModel):
    ok: bool = True
    summary: str = ""
    output: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)
    tokens_estimated: int = 0
    cost_estimated_usd: float = 0.0


class Task(BaseModel):
    id: str = Field(default_factory=lambda: new_id("task"))
    type: str
    agent: str
    status: TaskStatus = TaskStatus.pending
    workflow_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    input: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = False
    limits: ExecutionLimits = Field(default_factory=ExecutionLimits)
    attempts: int = 0
    created_at: datetime = Field(default_factory=now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: TaskResult | None = None
    errors: list[str] = Field(default_factory=list)
    decided_by: str | None = None


class Workflow(BaseModel):
    id: str = Field(default_factory=lambda: new_id("wf"))
    kind: Literal["niche_research", "video", "analytics", "kitchen_catalog", "kitchen_short", "script_short"]
    title: str
    params: dict[str, Any] = Field(default_factory=dict)
    task_ids: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.pending
    created_at: datetime = Field(default_factory=now)
    finished_at: datetime | None = None
    tasks_executed: int = 0
    api_calls: int = 0
    cost_estimated_usd: float = 0.0
    tokens_estimated: int = 0


# ---------- Pesquisa ----------

class ResearchSource(BaseModel):
    id: str = Field(default_factory=lambda: new_id("src"))
    provider: str
    title: str
    url: str
    collected_at: datetime = Field(default_factory=now)
    evidence: Evidence = Evidence.observado
    license: str | None = None
    note: str | None = None


class CriterionScore(BaseModel):
    key: str
    label: str
    score: float | None
    weight: float
    evidence: Evidence
    rationale: str
    source_ids: list[str] = Field(default_factory=list)


class RiskFlag(BaseModel):
    code: str
    label: str
    severity: Severity


class NicheScore(BaseModel):
    niche_id: str
    name: str
    market: str
    total: float | None
    coverage: float
    confidence: Literal["baixa", "média", "alta"]
    recommended: bool
    blocked_reason: str | None = None
    criteria: list[CriterionScore]
    risks: list[RiskFlag] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class NicheReport(BaseModel):
    id: str = Field(default_factory=lambda: new_id("nr"))
    created_at: datetime = Field(default_factory=now)
    primary_market: str = "pt"
    markets: list[str]
    weights: dict[str, float]
    methodology: str
    rankings: dict[str, list[NicheScore]]
    sources: list[ResearchSource]
    limitations: list[str]
    next_tests: list[str]
    report_path: str | None = None


class TrendItem(BaseModel):
    title: str
    lang: str
    url: str
    views: int
    days_present: int
    best_rank: int
    category: str
    description: str | None = None
    emerging: bool = False
    sensitive: bool = False


class TrendRun(BaseModel):
    id: str = Field(default_factory=lambda: new_id("tr"))
    collected_at: datetime = Field(default_factory=now)
    lang: str
    window: list[str]
    provider: str
    items: list[TrendItem]
    source: ResearchSource


# ---------- Conteúdo ----------

class Fact(BaseModel):
    text: str
    source_id: str


class VideoBrief(BaseModel):
    id: str = Field(default_factory=lambda: new_id("brief"))
    created_at: datetime = Field(default_factory=now)
    niche_id: str
    topic: str
    language: str = "pt"
    format: Literal["short", "long"] = "short"
    tone: Literal["comico", "educativo", "criativo"] = "comico"
    angle: str
    audience: str
    key_points: list[str]
    facts: list[Fact]
    sources: list[ResearchSource]
    topic_description: str | None = None


class ScriptSection(BaseModel):
    kind: Literal["hook", "context", "point", "payoff", "loop", "cta"]
    heading: str
    narration: str
    visual_note: str
    on_screen_text: str = ""
    source_ids: list[str] = Field(default_factory=list)
    est_seconds: float = 0.0
    # Visual First: o que a imagem precisa MOSTRAR nesta cena
    visual_query: str | None = None  # busca em inglês, ex.: "octopus releasing ink"
    visual_action: str | None = None  # grupos exigidos: "+" = todos, "|" = qualquer um (ex.: "color|camouflage")


class Script(BaseModel):
    id: str = Field(default_factory=lambda: new_id("script"))
    brief_id: str
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    format: Literal["short", "long"]
    language: str
    tone: str
    title: str
    title_variants: list[str]
    description: str
    hashtags: list[str] = Field(default_factory=list)
    thumbnail_ideas: list[str]
    sections: list[ScriptSection]
    sources: list[ResearchSource]
    loop: bool = False
    retention_notes: list[str] = Field(default_factory=list)
    status: Literal["draft", "approved", "rejected"] = "draft"
    provider: str
    edited_by_human: bool = False
    est_duration_s: float = 0.0
    planned_date: str | None = None  # calendário editorial (AAAA-MM-DD)
    channel_id: str | None = None
    topic_en: str | None = None  # assunto em inglês para a busca visual
    visual_plan_id: str | None = None
    story_id: str | None = None  # Reality Kitchen Stories
    scenes: list[dict[str, Any]] = Field(default_factory=list)
    rights_notes: list[str] = Field(default_factory=list)


# ---------- Visual Hunter ----------

class VisualCandidate(BaseModel):
    id: str  # identificador do material na plataforma
    provider: str
    title: str
    description: str = ""
    page_url: str
    file_url: str
    author: str = "desconhecido"
    license: str = "desconhecida"
    license_url: str | None = None
    license_status: Literal["aceita", "condicional", "rejeitada"] = "rejeitada"
    license_note: str = ""
    attribution_required: bool = True
    share_alike: bool = False
    verified_at: datetime = Field(default_factory=now)
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    local_path: str | None = None
    preview_path: str | None = None  # folha de quadros amostrados para validação visual
    metadata_score: float = 0.0  # fração dos grupos de ação encontrados no título/descrição (não é análise visual)
    matched_terms: list[str] = Field(default_factory=list)
    credit: str = ""


class VisualScene(BaseModel):
    index: int
    narration: str
    action: str  # grupos exigidos (ex.: "ink", "color|camouflage")
    queries: list[str]
    start: float | None = None
    end: float | None = None
    candidates: list[VisualCandidate] = Field(default_factory=list)
    selected_id: str | None = None
    clip_start: float | None = None  # trecho utilizado do material
    # Tomadas extras validadas (cortes dentro da cena): [{"id": candidato, "start": segundos}]
    shots: list[dict[str, Any]] = Field(default_factory=list)
    validation: Literal["pendente", "revisao", "validada", "rejeitada"] = "pendente"
    validated_by: str | None = None
    validation_method: str | None = None
    note: str = ""
    adaptation: str | None = None  # proposta factual de narração compatível com o material disponível (exige aprovação)


class VisualPlan(BaseModel):
    id: str = Field(default_factory=lambda: new_id("vp"))
    script_id: str
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    subject_en: str
    providers: list[str]
    scenes: list[VisualScene]
    log: list[str] = Field(default_factory=list)

    def coverage(self) -> float:
        """Proporção do tempo narrado (ou das cenas, antes da narração) coberta por material validado."""
        timed = all(s.start is not None and s.end is not None for s in self.scenes)
        weight = [(s.end - s.start) if timed else 1.0 for s in self.scenes]  # type: ignore[operator]
        ok = sum(w for s, w in zip(self.scenes, weight) if s.validation == "validada" and s.selected_id)
        return round(ok / sum(weight), 3) if self.scenes else 0.0


# ---------- Reality Kitchen Stories ----------

FactCategory = Literal["exibido_no_programa", "declaracao", "posterior_verificado", "interpretacao_editorial"]
Stage = Literal["gancho", "contexto", "conflito", "intervencao", "transformacao", "resultado"]


class KitchenEpisode(BaseModel):
    id: str
    show: str
    season: int | None = None
    number: str | None = None
    restaurant: str
    location: str | None = None
    air_date: str | None = None
    air_year: int | None = None
    summary: str = ""
    source_url: str


class KitchenCatalog(BaseModel):
    id: str  # show_id
    show: str
    lang: str
    collected_at: datetime = Field(default_factory=now)
    episodes: list[KitchenEpisode]
    source: ResearchSource


class KitchenFact(BaseModel):
    id: str = Field(default_factory=lambda: new_id("kf"))
    text: str
    category: FactCategory
    stage: Stage
    source_id: str
    verified: bool = False
    verified_by: str | None = None
    added_by: str = "agente"
    language: str = "pt"  # fatos em outro idioma são só referência e não entram na narração pt-BR


class Scene(BaseModel):
    stage: str
    description: str
    visual_type: Literal["grafico_original", "linha_do_tempo", "cartao_texto", "material_terceiros"]
    asset_id: str | None = None


class LicensedAsset(BaseModel):
    id: str = Field(default_factory=lambda: new_id("asset"))
    name: str
    origin: str
    license: str
    scope: str
    restrictions: str = ""
    authorized_by: str = "proprietário"
    registered_at: datetime = Field(default_factory=now)


class KitchenStory(BaseModel):
    id: str = Field(default_factory=lambda: new_id("story"))
    created_at: datetime = Field(default_factory=now)
    show: str
    episode_id: str
    restaurant: str
    location: str | None = None
    air_date: str | None = None
    air_year: int | None = None
    facts: list[KitchenFact]
    sources: list[ResearchSource]
    scenes: list[Scene] = Field(default_factory=list)
    missing_stages: list[str] = Field(default_factory=list)
    editorial_summary: str = ""
    rights_notes: list[str] = Field(default_factory=list)


class ProductionJob(BaseModel):
    id: str = Field(default_factory=lambda: new_id("job"))
    script_id: str
    orientation: Literal["vertical", "horizontal"]
    status: Literal["queued", "running", "rendered", "failed"] = "queued"
    stage: str = "queued"
    progress: float = 0.0
    created_at: datetime = Field(default_factory=now)
    finished_at: datetime | None = None
    outputs: dict[str, str] = Field(default_factory=dict)
    rights_manifest: list[dict[str, str]] = Field(default_factory=list)
    log: list[str] = Field(default_factory=list)
    media: dict[str, Any] = Field(default_factory=dict)


class QualityCheck(BaseModel):
    code: str
    label: str
    status: Literal["pass", "warn", "fail"]
    detail: str
    # Onde corrigir: "title", "description", "section:<i>", "video", "captions", "rights", "scenes", "sources"
    field: str | None = None


class QualityReport(BaseModel):
    id: str = Field(default_factory=lambda: new_id("qr"))
    created_at: datetime = Field(default_factory=now)
    target_kind: Literal["script", "job"]
    target_id: str
    checks: list[QualityCheck]
    blocking: bool
    disclaimer: str = (
        "Aprovação interna não garante monetização: a decisão final é do YouTube conforme suas políticas."
    )


# ---------- Analytics ----------

class MetricRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("m"))
    video_ref: str
    title: str
    theme: str | None = None
    niche: str | None = None
    format: Literal["short", "long"] | None = None
    hook: str | None = None
    duration_s: float | None = None
    published_at: str | None = None
    views: int | None = None
    impressions: int | None = None
    ctr: float | None = None
    avg_view_pct: float | None = None
    watch_time_h: float | None = None
    subs_gained: int | None = None
    revenue_usd: float | None = None
    demo: bool = False
    source: str = "manual"
    imported_at: datetime = Field(default_factory=now)


class AnalyticsReport(BaseModel):
    generated_at: datetime = Field(default_factory=now)
    demo: bool
    records: int
    totals: dict[str, float | None]
    comparisons: dict[str, list[dict[str, Any]]]
    recommendations: list[str]
    limitations: list[str]
