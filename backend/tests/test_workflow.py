"""Fluxo completo de um Short: pesquisa → roteiro → aprovações → render real (FFmpeg, voz silenciosa) → pacote."""
from pathlib import Path

import pytest

from app.config import ROOT
from app.models import ProductionJob, QualityReport, Script, Task, TaskStatus, Workflow
from app.orchestrator.orchestrator import ApprovalBlocked, Orchestrator
from app.production import ffmpeg
from app.store import get_store


def _task(orch: Orchestrator, wf: Workflow, ttype: str) -> Task:
    return next(t for t in orch.tasks_of(wf) if t.type == ttype)


def _make(orch, fmt="short"):
    return orch.create_workflow("video", {"topic": "Marte_(planeta)", "niche_id": "ciencia_espaco", "format": fmt,
                                          "tone": "comico", "language": "pt"}, "teste")


def test_short_pipeline_end_to_end(fake_wiki):
    orch = Orchestrator(store=get_store())
    wf = _make(orch)
    orch.run_until_idle()
    gate = _task(orch, wf, "editorial_approval")
    assert gate.status == TaskStatus.awaiting_approval
    assert _task(orch, wf, "produce_video").status == TaskStatus.pending  # nada é produzido sem aprovação

    script = get_store().list("scripts", Script)[0]
    assert script.loop and [s.kind for s in script.sections][-2:] == ["payoff", "loop"]
    assert script.sources and "wikipedia.org" in script.sources[0].url
    assert script.retention_notes

    orch.approve(gate.id)
    assert get_store().get("scripts", script.id, Script).status == "approved"
    orch.run_until_idle()
    produce = _task(orch, wf, "produce_video")
    assert produce.status == TaskStatus.completed, produce.errors
    job = get_store().list("jobs", ProductionJob)[0]
    video = ROOT / job.outputs["video"]
    assert video.exists()
    info = ffmpeg.probe(video)
    assert (info["width"], info["height"]) == (1080, 1920) and info["has_audio"]

    final = _task(orch, wf, "final_approval")
    assert final.status == TaskStatus.awaiting_approval
    qa = [r for r in get_store().list("quality_reports", QualityReport) if r.target_id == job.id][0]
    assert not qa.blocking, [c for c in qa.checks if c.status == "fail"]
    orch.approve(final.id)
    orch.run_until_idle()
    pkg = _task(orch, wf, "publish_prep")
    assert pkg.status == TaskStatus.completed
    pub = Path(pkg.result.output["publish_dir"])
    pub = pub if pub.is_absolute() else ROOT / pub
    assert (pub / "metadata.json").exists() and (pub / "CHECKLIST.md").exists()
    assert (pub / "cover.png").exists() and (pub / "editavel" / "narration.wav").exists()
    assert get_store().get("workflows", wf.id, Workflow).status == TaskStatus.completed

    # Biblioteca: o vídeo aparece como pronto para postar e, depois de publicado, com o link
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        item = next(i for i in c.get("/api/library").json() if i["script_id"] == script.id)
        assert item["status"] == "pronto para postar" and item["video"] and item["package"]
        c.post("/api/analytics/published", json={"url": "https://www.youtube.com/shorts/sshOJpegjdw", "script_id": script.id})
        item = next(i for i in c.get("/api/library").json() if i["script_id"] == script.id)
        assert item["status"] == "publicado" and item["published"]["url"].endswith("sshOJpegjdw")

    # Editar e refazer: destrava o roteiro e volta para a aprovação editorial
    orch.rework(wf.id)
    assert get_store().get("scripts", script.id, Script).status == "draft"
    orch.run_until_idle()
    assert _task(orch, wf, "editorial_approval").status == TaskStatus.awaiting_approval
    ctx = orch.approval_context(_task(orch, wf, "editorial_approval").id)
    assert ctx["script"].id == script.id and ctx["script_quality"] is not None


def test_workflow_params_reach_brief_and_script(fake_wiki):
    orch = Orchestrator(store=get_store())
    orch.create_workflow("video", {"topic": "Marte_(planeta)", "niche_id": "natureza_animais", "format": "short",
                                   "tone": "educativo", "language": "pt", "channel_id": "natureza"}, "params")
    orch.run_until_idle()
    script = get_store().list("scripts", Script)[0]
    assert script.tone == "educativo" and script.channel_id == "natureza"
    assert "#natureza" in script.hashtags


def test_quality_block_prevents_approval(fake_wiki):
    orch = Orchestrator(store=get_store())
    wf = _make(orch)
    orch.run_until_idle()
    report = get_store().list("quality_reports", QualityReport)[0]
    report.blocking = True
    get_store().put("quality_reports", report)
    with pytest.raises(ApprovalBlocked):
        orch.approve(_task(orch, wf, "editorial_approval").id)


def test_reject_cancels_downstream(fake_wiki):
    orch = Orchestrator(store=get_store())
    wf = _make(orch)
    orch.run_until_idle()
    orch.reject(_task(orch, wf, "editorial_approval").id, note="refazer")
    assert _task(orch, wf, "publish_prep").status == TaskStatus.cancelled
    assert get_store().list("scripts", Script)[0].status == "rejected"


def test_unknown_topic_fails_without_retry(monkeypatch):
    from app.research import wikimedia as wm
    monkeypatch.setattr(wm, "page_summary", lambda *a, **k: None)
    orch = Orchestrator(store=get_store())
    wf = _make(orch)
    orch.run_until_idle()
    research = _task(orch, wf, "research_topic")
    assert research.status == TaskStatus.failed and research.attempts == 1
    assert _task(orch, wf, "write_script").status == TaskStatus.cancelled
