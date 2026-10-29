"""Agente — Visual Hunter: encontra filmagens reais e licenciadas que MOSTREM o que cada cena narra.

Correspondência automática = metadados (título, descrição, categorias). Não há modelo de visão local:
a validação visual é feita por um humano a partir da folha de quadros amostrados (preview), e nunca é
presumida. Ação específica sem filmagem adequada → cena "pendente" (sem substituição silenciosa).
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

from ..config import ROOT, output_dir, wikimedia_user_agent
from ..models import Script, Task, TaskResult, VisualCandidate, VisualPlan, VisualScene, now
from ..production import ffmpeg
from ..research.footage import providers
from .base import Agent, AgentContext

# Vocabulário de ações visuais: grupo → (gatilhos em pt na narração, termos em en para busca, sinônimos nos metadados)
ACTIONS: dict[str, tuple[tuple[str, ...], str, tuple[str, ...]]] = {
    # Termos casam por palavra inteira (ex.: "Tintenfisch" = lula em alemão, não "tinta").
    "ink": (("tinta",), "ink", ("ink", "inking", "ink cloud", "encre", "tinta")),
    "color": (("cor", "cores", "aparência", "colorac"), "changing color", ("color", "colour", "chromatophore", "farbe", "couleur")),
    "camouflage": (("camufl", "mistur", "esconde", "disfar"), "camouflage", ("camouflage", "camouflag", "hidden", "hide", "crevasse",
                                                                             "cryptic", "mimic", "disguise", "tarn")),
    "texture": (("textura", "rochas", "imita"), "skin texture", ("texture", "granular", "papillae", "rough")),
    "swimming": (("nada", "nadando", "explor", "desloc"), "swimming", ("swim", "swimming", "flee", "moving", "crawling", "locomotion",
                                                                      "exploring", "walking", "jet")),
    "prey": (("presa", "caç", "captur", "aliment", "comida"), "hunting prey", ("prey", "catching", "crab", "shrimp", "attack", "predat",
                                                                           "food", "feeding", "hunt")),
    "arms": (("braço", "tentác"), "arms", ("arm", "arms", "tentacle", "reach")),
    "suckers": (("ventosa",), "suckers", ("sucker", "adhesion")),
    "intelligence": (("inteligen", "quebra-cabe", "resolve"), "puzzle", ("puzzle", "solve", "open the bottle", "problem")),
    "escape": (("perigo", "escap", "fug"), "escape", ("escape", "flee", "flees", "fleeing", "jet")),
}
SUBJECTS = {"polvo": ("octopus", ("octopus", "octopod", "krake", "poulpe", "pulpo", "polvo")),
            "tubarão": ("shark", ("shark",)), "baleia": ("whale", ("whale",)), "golfinho": ("dolphin", ("dolphin",)),
            "tartaruga": ("turtle", ("turtle",)), "água-viva": ("jellyfish", ("jellyfish", "medusa")),
            "axolote": ("axolotl", ("axolotl",)), "camaleão": ("chameleon", ("chameleon",)), "abelha": ("bee", ("bee",))}
EXCLUDE = ("tattoo", "cook", "recipe", "mukbang", "reader", "neon", "dust", "flour", "reaction", "consumption", "laser")


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()


def subject_for(topic: str) -> tuple[str, tuple[str, ...]]:
    t = _norm(topic)
    for pt, (en, syn) in SUBJECTS.items():
        if _norm(pt) in t or en in t:
            return en, syn
    return topic.lower(), (topic.lower(),)


def infer_action(narration: str) -> str:
    """Ações narradas → grupos exigidos. Várias ações na mesma frase viram alternativas (qualquer uma serve)."""
    low = _norm(narration)
    found = [g for g, (trig, _, _) in ACTIONS.items() if any(_norm(t) in low for t in trig)]
    return "|".join(found) if found else ""


def parse_action(action: str) -> list[list[str]]:
    """'a+b|c' → [[a], [b, c]]: todos os grupos separados por '+' são exigidos; '|' = alternativas."""
    return [[g.strip() for g in part.split("|") if g.strip()] for part in action.split("+") if part.strip()]


def metadata_score(c: VisualCandidate, subject_syn: tuple[str, ...], action: str) -> tuple[float, list[str]]:
    text = _norm(f"{c.title} {c.description}")
    if not any(s in text for s in subject_syn) or any(x in text for x in EXCLUDE):
        return 0.0, []
    req = parse_action(action)
    if not req:
        return 0.5, ["assunto"]
    matched, hit = [], 0
    for alts in req:
        # Prefixo no início da palavra (camouflag → camouflaged); "ink"/"arm" etc. exigem palavra inteira.
        terms = [t for g in alts for t in ACTIONS.get(g, ((), g, (g,)))[2]
                 if re.search(rf"\b{re.escape(t)}{'' if len(t) > 5 else r'(s|ed|ing)?\b'}", text)]
        if terms:
            hit += 1
            matched += terms[:2]
    return round(hit / len(req), 2), matched


def queries_for(subject_en: str, action: str, explicit: str | None) -> list[str]:
    qs = [explicit] if explicit else []
    for alts in parse_action(action):
        qs += [f"{subject_en} {ACTIONS[g][1]}" for g in alts if g in ACTIONS]
    qs.append(subject_en)
    return list(dict.fromkeys(q for q in qs if q))


def rank_key(c: VisualCandidate) -> tuple:
    lic = {"aceita": 2, "condicional": 1}.get(c.license_status, 0)
    return (c.metadata_score, lic, min(c.height or 0, 1080))


def download(c: VisualCandidate, folder: Path, max_mb: int = 150) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    ext = Path(c.file_url.split("?")[0]).suffix or ".webm"
    dest = folder / f"{re.sub(r'[^a-z0-9]+', '_', c.id.lower())}{ext}"
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    with httpx.stream("GET", c.file_url, headers={"User-Agent": wikimedia_user_agent()}, timeout=60, follow_redirects=True) as r:
        r.raise_for_status()
        size = 0
        with open(dest, "wb") as fh:
            for chunk in r.iter_bytes(1 << 16):
                size += len(chunk)
                if size > max_mb * 1_000_000:
                    raise RuntimeError(f"Arquivo maior que {max_mb} MB")
                fh.write(chunk)
    return dest


def contact_sheet(video: Path, out: Path, duration: float, n: int = 4) -> None:
    """Amostra n quadros ao longo do vídeo para validação visual humana."""
    frames = []
    for i in range(n):
        t = duration * (0.12 + 0.76 * i / max(1, n - 1))
        f = out.with_name(f"{out.stem}_{i}.jpg")
        ffmpeg.run(["-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=360:-2", str(f)], 60)
        frames.append(Image.open(f).convert("RGB"))
        f.unlink(missing_ok=True)
    w, h = frames[0].size
    sheet = Image.new("RGB", (w * n + 6 * (n - 1), h), (0, 0, 0))
    for i, fr in enumerate(frames):
        sheet.paste(fr.resize((w, h)), (i * (w + 6), 0))
    ImageDraw.Draw(sheet).text((6, 4), "amostra de quadros", fill=(255, 255, 255))
    sheet.save(out, "JPEG", quality=82)


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else str(p)


def prepare_candidate(c: VisualCandidate, folder: Path) -> VisualCandidate:
    path = download(c, folder)
    info = ffmpeg.probe(path)
    c.duration = info.get("duration") or c.duration
    c.width, c.height = info.get("width") or c.width, info.get("height") or c.height
    if not c.duration or not c.width:
        raise RuntimeError("Arquivo de vídeo ilegível")
    prev = folder / f"{path.stem}_preview.jpg"
    contact_sheet(path, prev, c.duration)
    c.local_path, c.preview_path = rel(path), rel(prev)
    return c


class VisualHunter(Agent):
    name = "visual_hunter"
    title = "Visual Hunter"
    description = ("Divide o roteiro em cenas, identifica a ação narrada, busca filmagens reais licenciadas (Commons, Pexels, "
                   "Pixabay), verifica licenças, baixa, amostra quadros e monta o plano visual para validação.")
    task_types = ("visual_hunt",)
    owned_kinds = frozenset({"visual_plans", "scripts"})

    def run(self, task: Task, ctx: AgentContext) -> TaskResult:
        script = ctx.read("scripts", ctx.param("script_id"), Script)
        if not script:
            raise ValueError("Roteiro não encontrado")
        existing = ctx.read("visual_plans", script.visual_plan_id, VisualPlan) if script.visual_plan_id else None
        if existing and not ctx.param("rehunt"):
            return TaskResult(summary=f"Plano visual existente reaproveitado (cobertura validada {existing.coverage():.0%})",
                              output={"visual_plan_id": existing.id})
        plan = hunt(script, ctx)
        script.visual_plan_id = plan.id
        ctx.save("scripts", script)
        ctx.save("visual_plans", plan)
        covered = sum(s.selected_id is not None for s in plan.scenes)
        pending = [s.index + 1 for s in plan.scenes if not s.selected_id]
        return TaskResult(summary=f"{covered}/{len(plan.scenes)} cenas com filmagem candidata; pendentes: {pending or 'nenhuma'}; "
                                  f"validação visual humana necessária", output={"visual_plan_id": plan.id})


def hunt(script: Script, ctx: AgentContext, max_downloads_per_scene: int = 2) -> VisualPlan:
    subject_en, subject_syn = subject_for(script.topic_en or script.title)
    provs = providers()
    scenes = [VisualScene(index=i, narration=s.narration, action=s.visual_action or infer_action(s.narration),
                          queries=queries_for(subject_en, s.visual_action or infer_action(s.narration), s.visual_query))
              for i, s in enumerate(script.sections)]
    plan = VisualPlan(script_id=script.id, subject_en=subject_en, providers=[p.name for p in provs], scenes=scenes)

    # Um acervo por roteiro (economiza chamadas de API), depois ranqueado cena a cena.
    pool: dict[str, VisualCandidate] = {}
    for q in dict.fromkeys(q for s in scenes for q in s.queries):
        for p in provs:
            ctx.check_cancelled()
            try:
                for c in p.search(ctx.store, q, ctx.budget):
                    pool.setdefault(c.id, c)
            except Exception as exc:  # um provedor fora do ar não derruba a busca
                plan.log.append(f"{p.name} falhou para '{q}': {exc}")
    plan.log.append(f"{len(pool)} materiais encontrados em {', '.join(plan.providers)}")

    folder = output_dir() / "footage" / script.id
    used: set[str] = set()
    for s in scenes:
        ranked = []
        for c in pool.values():
            if c.license_status == "rejeitada":
                continue
            score, terms = metadata_score(c, subject_syn, s.action)
            if score > 0:
                ranked.append(c.model_copy(update={"metadata_score": score, "matched_terms": terms}))
        ranked.sort(key=rank_key, reverse=True)
        specific = [c for c in ranked if c.metadata_score >= 1.0 or (not parse_action(s.action) and c.metadata_score > 0)]
        prepared: list[VisualCandidate] = []
        for c in sorted(specific, key=lambda c: c.id in used)[: max_downloads_per_scene + 2]:
            if len(prepared) >= max_downloads_per_scene:
                break
            try:
                prepared.append(prepare_candidate(c, folder))
            except Exception as exc:
                plan.log.append(f"Cena {s.index + 1}: falha ao preparar {c.id}: {exc}")
        s.candidates = prepared + [c for c in ranked[:6] if c.id not in {p.id for p in prepared}]
        if prepared:
            s.selected_id = prepared[0].id
            used.add(prepared[0].id)
            s.validation = "revisao"
            s.note = (f"Correspondência por metadados ({', '.join(prepared[0].matched_terms)}). Confirme na amostra de quadros "
                      "se a ação aparece de fato.")
        else:
            s.validation = "pendente"
            s.note = (f"Nenhuma filmagem licenciada encontrada que mostre: {s.action or 'o assunto'}. Configure PEXELS_API_KEY/"
                      "PIXABAY_API_KEY para ampliar a busca, troque o material manualmente ou aprove uma adaptação factual.")
    plan.updated_at = now()
    return plan
