"""Agente 6 — Video Producer: roteiro aprovado → vídeo renderizado; preparação do pacote de publicação."""
from __future__ import annotations

import json
import shutil

from ..config import ROOT, output_dir
from ..models import LicensedAsset, ProductionJob, Scene, Script, Task, TaskResult, VisualPlan, now
from ..production import documentary, pipeline
from .base import Agent, AgentContext
from .reality_kitchen import unauthorized_scenes

CHECKLIST = """# Checklist de publicação manual — {title}

Este pacote NÃO foi enviado ao YouTube. A publicação é feita manualmente pelo proprietário.

- [ ] Assistir ao vídeo completo e revisar legendas
- [ ] Reescrever trechos sinalizados pelo Quality & Compliance (originalidade)
- [ ] Confirmar os termos de uso comercial da voz sintética (ou trocar o provedor de voz)
- [ ] Revisar título, descrição, fontes e atribuição CC BY-SA
- [ ] Declarar conteúdo alterado/sintético no YouTube Studio, se aplicável
- [ ] Escolher a capa (Shorts: quadro do vídeo)
- [ ] Publicar como privado/não listado primeiro e conferir

## Edição externa (CapCut ou outro editor)
A pasta `editavel/` traz a narração, a trilha e as legendas (SRT) separadas.
- Mantenha as legendas no vídeo final (decisão do canal: sempre legendado).
- Músicas, efeitos e modelos da biblioteca do editor têm licença própria: confira se o uso comercial
  no YouTube é permitido e anote no manifesto de direitos.
- Não adicione cenas de programas de TV sem licença registrada no sistema.
"""


class VideoProducer(Agent):
    name = "video_producer"
    title = "Video Producer"
    description = "Transforma roteiros aprovados em vídeos (narração, legendas, visuais, trilha, render) e prepara pacotes de publicação."
    task_types = ("produce_video", "publish_prep")
    owned_kinds = frozenset({"jobs", "visual_plans", "scripts"})

    def run(self, task: Task, ctx: AgentContext) -> TaskResult:
        return self._produce(ctx) if task.type == "produce_video" else self._package(ctx)

    def _produce(self, ctx: AgentContext) -> TaskResult:
        script = ctx.read("scripts", ctx.param("script_id"), Script)
        if not script:
            raise ValueError("Roteiro não encontrado")
        if script.scenes:
            assets = {a.id: a for a in ctx.store.list("licensed_assets", LicensedAsset)}
            bad = unauthorized_scenes([Scene(**s) for s in script.scenes], assets)
            if bad:
                raise PermissionError("Renderização interrompida: cenas dependem de material de terceiros sem licença registrada ("
                                      + "; ".join(s.description for s in bad)
                                      + "). Alternativa: trocar essas cenas por gráficos originais e gerar o roteiro novamente.")
        orientation = ctx.param("orientation") or ("vertical" if script.format == "short" else "horizontal")
        job = ProductionJob(script_id=script.id, orientation=orientation)
        ctx.save("jobs", job)
        plan = ctx.read("visual_plans", script.visual_plan_id, VisualPlan) if script.visual_plan_id else None
        try:
            if plan:
                job = documentary.produce_documentary(job, script, plan, lambda j: ctx.save("jobs", j),
                                                      lambda p: ctx.save("visual_plans", p), ctx.check_cancelled)
                script.description = documentary.with_credits(script.description, plan)
                ctx.save("scripts", script)
            else:
                job = pipeline.produce(job, script, lambda j: ctx.save("jobs", j), ctx.check_cancelled)
        except Exception as exc:
            job.status, job.stage = "failed", "failed"
            job.log.append(f"Erro: {exc}")
            ctx.save("jobs", job)
            raise
        job.finished_at = now()
        ctx.save("jobs", job)
        return TaskResult(summary=f"Vídeo {orientation} renderizado ({job.media.get('duration_s')}s)",
                          output={"job_id": job.id}, artifacts=list(job.outputs.values()))

    def _package(self, ctx: AgentContext) -> TaskResult:
        job = ctx.read("jobs", ctx.param("job_id"), ProductionJob)
        script = ctx.read("scripts", job.script_id, Script) if job else None
        if not job or not script or job.status != "rendered":
            raise ValueError("Job renderizado não encontrado")
        dest = output_dir() / "publish" / job.id
        dest.mkdir(parents=True, exist_ok=True)
        for key in ("video", "captions", "cover"):
            if key in job.outputs:
                src = ROOT / job.outputs[key]
                shutil.copy2(src, dest / src.name)
        # Faixas separadas para edição externa (ex.: CapCut): narração, trilha e legendas.
        edit_dir = dest / "editavel"
        edit_dir.mkdir(exist_ok=True)
        for key in ("narration", "music", "captions"):
            if key in job.outputs:
                src = ROOT / job.outputs[key]
                shutil.copy2(src, edit_dir / src.name)
        meta = {
            "status": "aguardando publicação manual", "title": script.title, "title_variants": script.title_variants,
            "description": script.description + "\n\n" + " ".join(script.hashtags), "language": script.language,
            "format": script.format, "orientation": job.orientation, "visibility_suggested": "private",
            "made_for_kids": None, "rights_manifest": job.rights_manifest, "prepared_at": now().isoformat(),
        }
        (dest / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        (dest / "CHECKLIST.md").write_text(CHECKLIST.format(title=script.title), encoding="utf-8")
        path = pipeline.rel(dest)
        return TaskResult(summary=f"Pacote preparado em {path} (não publicado)", output={"publish_dir": path}, artifacts=[path])
