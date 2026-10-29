"""Agente 7 — Quality & Compliance: revisão factual/editorial e verificação técnica. Pode bloquear a aprovação interna."""
from __future__ import annotations

import re

from ..config import ROOT, get_policy
from ..models import (KitchenStory, LicensedAsset, ProductionJob, QualityCheck, QualityReport, Scene, Script, Task, TaskResult,
                      VideoBrief, VisualPlan)
from ..production import ffmpeg
from ..production.captions import read_srt
from .base import Agent, AgentContext
from .reality_kitchen import unauthorized_scenes
from .scriptwriter import CLICKBAIT

SENSITIVE_WORDS = ("morte", "assassin", "suicíd", "drogas", "arma", "sangue", "tiroteio", "terror", "massacre", "estupro")


def _ngrams(text: str, n: int = 6) -> set[tuple[str, ...]]:
    w = re.findall(r"\w+", text.lower())
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


def overlap_ratio(script_text: str, source_texts: list[str]) -> float:
    s = _ngrams(script_text)
    if not s:
        return 0.0
    src: set[tuple[str, ...]] = set()
    for t in source_texts:
        src |= _ngrams(t)
    return len(s & src) / len(s)


def review_script(script: Script, brief: VideoBrief | None, story: KitchenStory | None = None,
                  assets: dict[str, LicensedAsset] | None = None) -> QualityReport:
    checks: list[QualityCheck] = []

    def add(code: str, label: str, status: str, detail: str, field: str | None = None) -> None:
        checks.append(QualityCheck(code=code, label=label, status=status, detail=detail, field=field))

    secs = script.sections
    factual = [s for s in secs if s.kind in ("context", "point")]
    missing = [i for i, s in enumerate(secs) if s.kind == "point" and not s.source_ids]
    add("fontes_por_fato", "Cada fato tem fonte", "fail" if missing else "pass",
        f"Sem fonte: {', '.join(secs[i].heading for i in missing)}" if missing else f"{len(factual)} blocos factuais com fonte.",
        f"section:{missing[0]}" if missing else None)
    no_url = [s.title for s in script.sources if not s.url]
    add("fontes_rastreaveis", "Fontes com URL e data", "fail" if no_url or not script.sources else "pass",
        f"{len(script.sources)} fonte(s) com URL e data de coleta." if script.sources and not no_url else "Fontes incompletas.", "sources")

    source_texts = [f.text for f in brief.facts] if brief else [f.text for f in story.facts] if story else []
    if source_texts and not script.edited_by_human:
        full = " ".join(s.narration for s in secs)
        ratio = overlap_ratio(full, source_texts)
        status = "fail" if ratio >= 0.8 else "warn" if ratio >= 0.25 else "pass"
        per = [overlap_ratio(s.narration, source_texts) for s in secs]
        worst = max(range(len(secs)), key=per.__getitem__) if secs else 0
        add("originalidade", "Originalidade textual (sobreposição de 6-gramas com as fontes)", status,
            f"{ratio:.0%} do texto coincide com as fontes; o trecho mais parecido é “{secs[worst].heading}” ({per[worst]:.0%}). "
            + ("Reescreva com suas palavras antes de publicar; atribuição CC BY-SA incluída na descrição." if status != "pass" else "Ok."),
            f"section:{worst}" if status != "pass" else None)
    elif script.edited_by_human:
        add("originalidade", "Originalidade textual", "pass", "Roteiro editado pelo proprietário.")

    if script.provider in ("template", "kitchen_template") and not script.edited_by_human:
        add("repetitividade", "Risco de conteúdo repetitivo/inautêntico", "warn",
            "Roteiro de template. Personalize frases e humor para evitar padrão em massa (política de monetização do YouTube).",
            "section:0")

    if script.format == "short":
        d, lim = script.est_duration_s, get_policy().limits.max_short_duration_s
        longest = max(range(len(secs)), key=lambda i: secs[i].est_seconds) if secs else 0
        add("duracao_short", "Duração do Short", "fail" if d > lim + 10 else "warn" if d > lim else "pass",
            f"~{d:.0f}s estimados (limite: {lim}s)." + (f" Bloco mais longo: “{secs[longest].heading}”." if d > lim else ""),
            f"section:{longest}" if d > lim else None)
        if script.loop:
            kinds = [s.kind for s in secs]
            ok = "payoff" in kinds and "loop" in kinds and kinds.index("payoff") < kinds.index("loop")
            add("loop_honesto", "Loop sem suspense enganoso", "pass" if ok else "fail",
                "A resposta é entregue antes do loop." if ok else "O loop aparece antes da resposta ao gancho.",
                None if ok else f"section:{kinds.index('loop') if 'loop' in kinds else 0}")

    titles = " ".join([script.title, *script.title_variants]).lower()
    bait = [w for w in CLICKBAIT if w in titles]
    add("titulo_honesto", "Títulos sem promessas enganosas", "warn" if bait else "pass", f"Termos: {bait}" if bait else "Ok.",
        "title" if bait else None)
    sens_at = next(((i, w) for i, s in enumerate(secs) for w in SENSITIVE_WORDS if w in s.narration.lower()), None)
    add("adequacao_anunciantes", "Adequação a anunciantes", "warn" if sens_at else "pass",
        f"Termo sensível “{sens_at[1]}” em “{secs[sens_at[0]].heading}”. Monetização pode ser limitada." if sens_at
        else "Nenhum termo sensível detectado.", f"section:{sens_at[0]}" if sens_at else None)

    if script.story_id and story is not None:
        checks.extend(kitchen_checks(script, story, assets or {}))

    return QualityReport(target_kind="script", target_id=script.id, checks=checks,
                         blocking=any(c.status == "fail" for c in checks))


def kitchen_checks(script: Script, story: KitchenStory, assets: dict[str, LicensedAsset]) -> list[QualityCheck]:
    """Verificações específicas de Reality Kitchen Stories (SPEC §7)."""
    out: list[QualityCheck] = []
    full = " ".join(s.narration for s in script.sections)
    unverified = [f for f in story.facts if not f.verified and f.text in full]
    pending = sum(not f.verified for f in story.facts)
    at = lambda pred: next((f"section:{i}" for i, s in enumerate(script.sections) if pred(s.narration)), None)  # noqa: E731
    out.append(QualityCheck(code="fatos_verificados", label="Somente fatos verificados no roteiro",
                            status="fail" if unverified else "pass",
                            detail=f"{len(unverified)} fato(s) não verificados usados." if unverified
                            else f"Fatos usados verificados. {pending} fato(s) do dossiê seguem pendentes (não usados).",
                            field=at(lambda n: any(f.text in n for f in unverified)) if unverified else None))
    year_ok = story.air_year is None or str(story.air_year) in full
    out.append(QualityCheck(code="ano_exibicao", label="Ano de exibição citado (evita apresentar fato antigo como atual)",
                            status="pass" if year_ok else "fail", detail=f"Ano {story.air_year}" + ("" if year_ok else " ausente da narração"),
                            field=None if year_ok else "section:0"))
    quote_re = re.compile(r"[\"“]([^\"”]{3,})[\"”]")
    quotes = quote_re.findall(full)
    declared = any(f.category == "declaracao" and f.verified for f in story.facts)
    out.append(QualityCheck(code="falas_atribuidas", label="Falas atribuídas somente com fonte",
                            status="fail" if quotes and not declared else "pass",
                            detail="Há citações sem fato do tipo 'declaração' verificado." if quotes and not declared else "Ok.",
                            field=at(lambda n: bool(quote_re.search(n))) if quotes and not declared else None))
    bad = unauthorized_scenes([Scene(**s) for s in script.scenes], assets)
    out.append(QualityCheck(code="materiais_autorizados", label="Materiais de terceiros com autorização documentada",
                            status="fail" if bad else "pass",
                            detail=("Cenas dependem de material sem licença registrada: " + "; ".join(s.description for s in bad)
                                    + ". Alternativa: substituir por gráfico original.") if bad
                            else "Somente visuais originais ou licenciados.", field="scenes" if bad else None))
    if story.missing_stages:
        out.append(QualityCheck(code="etapas_ausentes", label="Etapas narrativas sem fonte", status="warn",
                                detail=f"Não preenchidas (sem invenção): {', '.join(story.missing_stages)}. Adicione fatos com fonte no dossiê.",
                                field="story"))
    d = script.est_duration_s
    if d < 45:
        out.append(QualityCheck(code="duracao_minima", label="Duração alvo 45–60s", status="warn",
                                detail=f"~{d:.0f}s: verifique mais fatos do dossiê para completar a história.", field="story"))
    return out


def review_job(job: ProductionJob, script: Script | None, plan: VisualPlan | None = None) -> QualityReport:
    limits = get_policy().limits
    checks: list[QualityCheck] = []
    fields = {"legendas": "captions", "direitos": "rights", "aprovacao_editorial": "section:0"}

    def add(code: str, label: str, status: str, detail: str) -> None:
        checks.append(QualityCheck(code=code, label=label, status=status, detail=detail, field=fields.get(code, "video")))

    video = ROOT / job.outputs.get("video", "__missing__")
    if not video.exists():
        add("arquivo", "Arquivo de vídeo existe", "fail", "Vídeo não encontrado.")
        return QualityReport(target_kind="job", target_id=job.id, checks=checks, blocking=True)

    size_mb = video.stat().st_size / 1e6
    add("tamanho", "Tamanho do arquivo", "fail" if size_mb > limits.max_file_size_mb else "pass", f"{size_mb:.1f} MB")
    info = ffmpeg.probe(video)
    want = (1080, 1920) if job.orientation == "vertical" else (1920, 1080)
    add("resolucao", "Resolução e proporção", "pass" if (info.get("width"), info.get("height")) == want else "fail",
        f"{info.get('width')}x{info.get('height')} (esperado {want[0]}x{want[1]})")
    dur = info.get("duration") or 0
    add("audio", "Faixa de áudio presente", "pass" if info.get("has_audio") else "fail", info.get("audio_codec") or "sem áudio")
    errors = ffmpeg.decode_errors(video)
    add("integridade", "Integridade (decodificação completa)", "fail" if errors else "pass", errors[:200] or "Sem erros.")
    if job.orientation == "vertical":
        lim = limits.max_short_duration_s
        add("duracao", "Duração do Short", "fail" if dur > lim + 0.5 else "pass", f"{dur:.1f}s (limite {lim}s)")
    vol = ffmpeg.volume_stats(video)
    mean, peak = vol.get("mean_db"), vol.get("max_db")
    if mean is not None:
        st = "pass" if -28 <= mean <= -10 and (peak or 0) <= -0.3 else "warn"
        add("volume", "Nível de áudio", st, f"médio {mean:.1f} dB, pico {peak:.1f} dB (alvo médio -28..-10 dB)")
    srt = ROOT / job.outputs.get("captions", "__missing__")
    if srt.exists():
        cues = read_srt(srt)
        cps = max((len(c["text"]) / max(0.1, c["end"] - c["start"]) for c in cues), default=0)
        end = cues[-1]["end"] if cues else 0
        add("legendas", "Legendas sincronizadas e legíveis", "pass" if cues and cps <= 22 and abs(end - dur) < 2.5 else "warn",
            f"{len(cues)} legendas, máx. {cps:.0f} caracteres/s, fim em {end:.1f}s de {dur:.1f}s")
    else:
        add("legendas", "Legendas", "fail", "Arquivo SRT ausente.")
    pending = [r["asset"] for r in job.rights_manifest if r.get("status") != "ok"]
    missing = [r["asset"] for r in job.rights_manifest if not r.get("license")]
    add("direitos", "Direitos dos materiais documentados", "fail" if missing or not job.rights_manifest else "warn" if pending else "pass",
        f"Sem licença: {missing}" if missing else f"Verificar: {pending}" if pending else "Todos os materiais com licença documentada.")
    if script and script.status != "approved":
        add("aprovacao_editorial", "Roteiro aprovado", "warn", "Roteiro ainda não marcado como aprovado.")
    if plan is not None:
        checks.extend(documentary_checks(job, script, plan, video, dur))
    return QualityReport(target_kind="job", target_id=job.id, checks=checks, blocking=any(c.status == "fail" for c in checks))


def documentary_checks(job: ProductionJob, script: Script | None, plan: VisualPlan, video, dur: float) -> list[QualityCheck]:
    """Regra permanente: o vídeo precisa MOSTRAR o que é narrado (cobertura visual validada = 100%)."""
    out: list[QualityCheck] = []
    add = lambda c, l, st, d, f="visual": out.append(QualityCheck(code=c, label=l, status=st, detail=d, field=f))  # noqa: E731
    cov = plan.coverage()
    missing = [f"{s.index + 1} ({s.validation})" for s in plan.scenes if not (s.validation == "validada" and s.selected_id)]
    add("cobertura_visual", "Cobertura visual do roteiro", "pass" if cov >= 0.999 else "fail",
        f"{cov:.0%} do tempo narrado com filmagem validada." + (f" Cenas sem cobertura validada: {', '.join(missing)}." if missing else ""))
    from ..production.documentary import used_footage

    used = used_footage(plan)
    bad = [c.title for c in used if c.license_status == "rejeitada"]
    cond = [c.title for c in used if c.license_status == "condicional"]
    add("licencas_filmagens", "Licenças das filmagens verificadas", "fail" if bad else "warn" if cond else "pass",
        f"Rejeitadas: {bad}" if bad else f"Condicionais (revisar): {cond}" if cond else f"{len(used)} filmagens com licença aceita.")
    need_credit = [c for c in used if c.attribution_required]
    desc = script.description if script else ""
    missing_credit = [c.title for c in need_credit if c.page_url not in desc]
    add("creditos", "Créditos obrigatórios na descrição", "fail" if missing_credit else "pass",
        f"Faltam créditos: {missing_credit}" if missing_credit else f"{len(need_credit)} crédito(s) obrigatório(s) incluídos.", "description")
    blacks = [(a, b) for a, b in ffmpeg.black_segments(video) if a < dur - 3]  # ignora o encerramento
    add("telas_pretas", "Sem telas pretas inesperadas", "fail" if blacks else "pass",
        f"Trechos pretos: {blacks}" if blacks else "Nenhum trecho preto ≥ 0,4 s.", "video")
    narr, music = ROOT / job.outputs.get("narration", "_"), ROOT / job.outputs.get("music", "_")
    if narr.exists() and music.exists():
        vn, vm = ffmpeg.volume_stats(narr).get("mean_db"), ffmpeg.volume_stats(music).get("mean_db")
        if vn is not None and vm is not None:
            import math

            from ..channels import get_channel
            from ..production.audio import levels

            lv = job.media.get("audio_levels") or levels(get_channel(script.channel_id if script else None, "video"))
            voice_db, music_db = vn + 20 * math.log10(lv["voice"]), vm + 20 * math.log10(lv["music"])
            gap = voice_db - music_db  # antes do ducking, que abaixa ainda mais a trilha durante a fala
            add("voz_clara", "Música abaixo da narração", "pass" if gap >= 8 else "warn",
                f"Voz {voice_db:.1f} dB vs. música {music_db:.1f} dB na mixagem (voz {lv['voice']:.0%}, música {lv['music']:.0%}; "
                f"diferença {gap:.1f} dB antes do ducking).", "video")
    notes = job.media.get("notes") or []
    if notes:
        add("tratamentos", "Tratamentos de montagem", "warn" if any("PENDENTE" in n or "lenta" in n for n in notes) else "pass",
            "; ".join(notes), "visual")
    return out


class QualityCompliance(Agent):
    name = "quality_compliance"
    title = "Quality & Compliance"
    description = "Verifica fatos, fontes, originalidade, direitos, legendas, áudio e arquivo. Pode bloquear a aprovação interna."
    task_types = ("fact_review", "technical_qa")
    owned_kinds = frozenset({"quality_reports"})

    def run(self, task: Task, ctx: AgentContext) -> TaskResult:
        if task.type == "fact_review":
            script = ctx.read("scripts", ctx.param("script_id"), Script)
            if not script:
                raise ValueError("Roteiro não encontrado")
            story = ctx.read("kitchen_stories", script.story_id, KitchenStory) if script.story_id else None
            assets = {a.id: a for a in ctx.store.list("licensed_assets", LicensedAsset)}
            report = review_script(script, ctx.read("briefs", script.brief_id, VideoBrief), story, assets)
        else:
            job = ctx.read("jobs", ctx.param("job_id"), ProductionJob)
            if not job:
                raise ValueError("Job de produção não encontrado")
            script = ctx.read("scripts", job.script_id, Script)
            plan = ctx.read("visual_plans", script.visual_plan_id, VisualPlan) if script and script.visual_plan_id else None
            report = review_job(job, script, plan)
        ctx.save("quality_reports", report)
        fails = sum(c.status == "fail" for c in report.checks)
        warns = sum(c.status == "warn" for c in report.checks)
        return TaskResult(summary=f"{'BLOQUEADO' if report.blocking else 'Liberado'}: {fails} falha(s), {warns} alerta(s)",
                          output={"quality_report_id": report.id, "blocks_approval": report.blocking})
