"""Agente especializado — Reality Kitchen Stories.

Shorts narrativos sobre crises e transformações de restaurantes em programas de TV.
Regras (SPEC §7): nenhuma cena de episódio é baixada; fatos só com fonte; etapas sem fato ficam
ausentes; ano de exibição sempre citado; material de terceiros só com licença registrada.
"""
from __future__ import annotations

import html
import re

from ..channels import get_channel
from ..models import (KitchenCatalog, KitchenEpisode, KitchenFact, KitchenStory, LicensedAsset, ResearchSource, Scene,
                      Script, ScriptSection, Task, TaskResult)
from ..research import wikimedia as wm
from ..research.http import get_json
from .base import Agent, AgentContext
from .scriptwriter import estimate_seconds

SHOWS = {
    "restaurant_impossible": {"name": "S.O.S. Restaurante (Restaurant: Impossible, EUA)", "lang": "en",
                              "page": "List of Restaurant: Impossible episodes", "chef": "Robert Irvine"},
    "pesadelo_br": {"name": "Pesadelo na Cozinha (Brasil)", "lang": "pt", "page": "Pesadelo na Cozinha", "chef": "Érick Jacquin"},
    "kitchen_nightmares_us": {"name": "Kitchen Nightmares (EUA)", "lang": "en", "page": "List of Kitchen Nightmares episodes", "chef": "Gordon Ramsay"},
}
STAGES = ["gancho", "contexto", "conflito", "intervencao", "transformacao", "resultado"]
STAGE_LABEL = {"gancho": "Gancho", "contexto": "O restaurante", "conflito": "O problema", "intervencao": "O chef entra",
               "transformacao": "A mudança", "resultado": "E depois?"}
KEYWORDS = {
    "resultado": ("fechou", "fechado", "encerrou", "vendido", "continua aberto", "reabriu", "closed", "sold", "remains open", "após o programa", "depois do programa"),
    "transformacao": ("reforma", "novo cardápio", "decoração", "renov", "mudança", "redecor", "new menu", "renovat", "makeover", "relaunch"),
    "intervencao": ("jacquin", "ramsay", "chef", "ensina", "orienta", "treina", "cardápio", "menu", "teaches", "leaves the restaurant"),
    "conflito": ("briga", "discuss", "conflito", "problema", "sujeira", "higiene", "dívida", "crise", "reclama", "brig", "conflict",
                 "argu", "debt", "dirty", "filth", "rude", "owners"),
}
AFTER_WORDS = ("fechou", "fechado", "encerrou", "vendido", "reabriu", "atualmente", "closed", "sold", "currently")


def _clean(fragment: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", "", fragment))
    text = re.sub(r"\[\s*\d+\s*\]|\[nota \d+\]", "", text)
    return re.sub(r"\s+", " ", text).strip().strip('"“”')


def parse_episode_tables(page_html: str, show_id: str, show_name: str, page_url: str) -> list[KitchenEpisode]:
    episodes: list[KitchenEpisode] = []
    season = 0
    for table in re.findall(r'<table class="wikitable.*?</table>', page_html, re.S):
        headers = [_clean(h).lower() for h in re.findall(r"<th[^>]*>(.*?)</th>", table.split("</tr>", 1)[0], re.S)]
        col = lambda *names: next((i for i, h in enumerate(headers) if any(n in h for n in names)), None)  # noqa: E731
        i_rest, i_loc, i_date = col("restaurant"), col("locali", "location"), col("data de exibição", "release date", "air date")
        if i_rest is None:
            continue
        season += 1
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S)
        for r_idx, row in enumerate(rows):
            if 'class="description"' in row or "<td" not in row:
                continue
            cells = [_clean(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)]
            if len(cells) <= i_rest or not cells[i_rest]:
                continue
            summary = ""
            if r_idx + 1 < len(rows) and 'class="description"' in rows[r_idx + 1]:
                m = re.search(r'class="description"[^>]*>(.*?)</td>', rows[r_idx + 1], re.S)
                summary = _clean(m.group(1)) if m else ""
            date = cells[i_date] if i_date is not None and i_date < len(cells) else None
            year = re.search(r"\b(19|20)\d{2}\b", date or "")
            number = cells[0] if cells and cells[0].isdigit() else str(len(episodes) + 1)
            episodes.append(KitchenEpisode(
                id=f"{show_id}:{number}", show=show_name, season=season, number=number, restaurant=cells[i_rest],
                location=cells[i_loc] if i_loc is not None and i_loc < len(cells) else None, air_date=date,
                air_year=int(year.group(0)) if year else None, summary=summary, source_url=page_url,
            ))
    return episodes


def classify_stage(sentence: str) -> str:
    low = sentence.lower()
    for stage in ("resultado", "transformacao", "intervencao", "conflito"):
        if any(k in low for k in KEYWORDS[stage]):
            return stage
    return "contexto"


def build_story(ep: KitchenEpisode, source: ResearchSource, chef: str, lang: str = "pt") -> KitchenStory:
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", ep.summary) if len(s.strip()) > 15]
    facts = [KitchenFact(
        text=s, stage=classify_stage(s), source_id=source.id, language=lang,
        category="posterior_verificado" if any(w in s.lower() for w in AFTER_WORDS) else "exibido_no_programa",
    ) for s in sents]
    where = f", em {ep.location}" if ep.location else ""
    when = f" exibido em {ep.air_date}" if ep.air_date else ""
    facts.insert(0, KitchenFact(text=f"O restaurante {ep.restaurant}{where}, apareceu no programa {ep.show} em episódio{when}.",
                                stage="contexto", category="exibido_no_programa", source_id=source.id))
    present = {f.stage for f in facts}
    missing = [s for s in STAGES[1:] if s not in present]
    scenes = [Scene(stage="gancho", description=f"Cartão com o nome '{ep.restaurant}' e o ano {ep.air_year or '?'} em destaque", visual_type="cartao_texto"),
              Scene(stage="contexto", description=f"Mapa estilizado/ícone de localização: {ep.location or 'local não informado'}", visual_type="grafico_original")]
    for st in STAGES[2:]:
        if st in present:
            scenes.append(Scene(stage=st, description={
                "conflito": "Ilustração original de cozinha caótica (ícones de panela, alerta, relógio) — sem cenas do programa",
                "intervencao": "Cartão 'o chef entra' com silhueta genérica de chapéu de cozinheiro (não usar imagem real do chef)",
                "transformacao": "Comparação 'antes × depois' em gráfico original com ícones",
                "resultado": "Linha do tempo: exibição → situação posterior registrada na fonte",
            }[st], visual_type="linha_do_tempo" if st == "resultado" else "grafico_original"))
    story = KitchenStory(
        show=ep.show, episode_id=ep.id, restaurant=ep.restaurant, location=ep.location, air_date=ep.air_date,
        air_year=ep.air_year, facts=facts, sources=[source], scenes=scenes, missing_stages=missing,
        rights_notes=[
            "Nenhuma cena, áudio ou imagem do programa é utilizada. Visuais são gráficos originais gerados localmente.",
            f"Não usar fotos do chef ({chef}), dos participantes ou do restaurante sem licença registrada.",
            "Resumos da Wikipedia são CC BY-SA 4.0: reescreva com suas palavras e mantenha a atribuição na descrição.",
            "Adicionar cortes, legendas, música ou narração NÃO autoriza a reutilização de cenas protegidas.",
        ],
    )
    story.editorial_summary = (
        f"{ep.restaurant}{where} — episódio de {ep.show}" + (f" ({ep.air_year})" if ep.air_year else "")
        + f". {len(facts)} fatos extraídos da fonte; etapas sem fato: {', '.join(missing) or 'nenhuma'}."
    )
    return story


def unauthorized_scenes(scenes: list[Scene], assets: dict[str, LicensedAsset]) -> list[Scene]:
    return [s for s in scenes if s.visual_type == "material_terceiros" and (not s.asset_id or s.asset_id not in assets)]


def build_script(story: KitchenStory) -> Script:
    """Roteiro 45–60s. Usa somente fatos verificados; etapas sem fato não são preenchidas."""
    year = story.air_year
    when = f"em {year}" if year else "num episódio antigo"
    by_stage: dict[str, list[KitchenFact]] = {}
    for f in story.facts:
        if f.verified and f.language == "pt":
            by_stage.setdefault(f.stage, []).append(f)

    def narr(stage: str, limit: int = 2) -> tuple[str, list[str]]:
        fs = by_stage.get(stage, [])[:limit]
        return " ".join(f.text for f in fs), [f.source_id for f in fs]

    sections: list[ScriptSection] = []
    hook = f"Esse restaurante quase afundou, e tudo foi parar na TV {when}."
    if "conflito" not in by_stage:
        hook = f"A história do {story.restaurant} foi parar na TV {when}."
    sections.append(ScriptSection(kind="hook", heading="Gancho", narration=hook, on_screen_text=story.restaurant.upper(),
                                  visual_note="Cartão com nome e ano; corte seco, sem fade."))
    for stage, kind, label in (("contexto", "context", "O RESTAURANTE"), ("conflito", "point", "O PROBLEMA"),
                               ("intervencao", "point", "O CHEF ENTRA"), ("transformacao", "point", "A MUDANÇA")):
        text, src = narr(stage)
        if text:
            sections.append(ScriptSection(kind=kind, heading=STAGE_LABEL[stage], narration=text, on_screen_text=label,
                                          source_ids=src, visual_note=next((s.description for s in story.scenes if s.stage == stage), "Gráfico original")))
    text, src = narr("resultado")
    payoff = (f"{text} Lembrando: isso é o que a fonte registra sobre o episódio de {year or 'exibição original'}, não necessariamente a situação de hoje."
              if text else f"O que aconteceu depois? A fonte consultada não registra — e a gente não vai inventar.")
    sections.append(ScriptSection(kind="payoff", heading="Resultado", narration=payoff, on_screen_text="E DEPOIS?", source_ids=src,
                                  visual_note="Linha do tempo: exibição → registro posterior."))
    sections.append(ScriptSection(kind="loop", heading="Loop", narration="E é por isso que até hoje tem gente que lembra que",
                                  on_screen_text=story.restaurant.upper(), visual_note="Mesmo cartão do gancho para fechar o loop."))
    for s in sections:
        s.est_seconds = estimate_seconds(s.narration)
    src_lines = "\n".join(f"- {s.title}: {s.url} (consultado em {s.collected_at:%Y-%m-%d})" for s in story.sources)
    title = f"O dia em que o {story.restaurant} foi parar no {story.show.split(' (')[0]}"
    return Script(
        brief_id=story.id, story_id=story.id, format="short", language="pt", tone="narrativo", title=title[:100],
        title_variants=[title[:100], f"{story.restaurant}: crise, chef e o que veio depois", f"A cozinha mais caótica de {year or 'todos os tempos'}?"],
        description=(f"História do restaurante {story.restaurant} no programa {story.show} ({year or 'ano não informado'}). "
                     "Narração e visuais originais; nenhuma cena do programa é usada.\n\nFontes:\n" + src_lines
                     + "\n\nResumo de referência: Wikipedia, CC BY-SA 4.0 — atribuição aos autores do artigo.\nNarração com voz sintética."),
        channel_id="clips_plus", hashtags=get_channel("clips_plus")["hashtags"],
        thumbnail_ideas=[f"Capa: '{story.restaurant.upper()}' + ícone de alerta vermelho + ano {year or ''}",
                         "Capa: 'antes × depois' em ícones originais", "Capa: chapéu de chef estilizado + ponto de interrogação"],
        sections=sections, sources=story.sources, loop=True, provider="kitchen_template",
        est_duration_s=round(sum(s.est_seconds for s in sections) + 0.35 * len(sections), 1),
        scenes=[s.model_dump() for s in story.scenes], rights_notes=story.rights_notes,
    )


class RealityKitchenStories(Agent):
    name = "reality_kitchen"
    title = "Reality Kitchen Stories"
    description = "Pesquisa episódios de reality shows de cozinha, monta dossiês com fatos verificáveis e roteiros de Shorts com visuais originais."
    task_types = ("kitchen_catalog", "kitchen_story", "kitchen_script")
    owned_kinds = frozenset({"kitchen_catalogs", "kitchen_stories", "scripts"})

    def run(self, task: Task, ctx: AgentContext) -> TaskResult:
        return {"kitchen_catalog": self._catalog, "kitchen_story": self._story, "kitchen_script": self._script}[task.type](ctx)

    def _catalog(self, ctx: AgentContext) -> TaskResult:
        show_id = ctx.param("show_id", "pesadelo_br")
        cfg = SHOWS[show_id]
        data = get_json(f"https://{cfg['lang']}.wikipedia.org/w/api.php", store=ctx.store, ttl_s=7 * 24 * 3600, budget=ctx.budget,
                        params={"action": "parse", "page": cfg["page"], "prop": "text", "format": "json", "formatversion": 2, "redirects": 1})
        page_url = wm.article_url(cfg["lang"], cfg["page"].replace(" ", "_"))
        episodes = parse_episode_tables(data["parse"]["text"], show_id, cfg["name"], page_url)
        if not episodes:
            raise ValueError("Nenhuma tabela de episódios encontrada na fonte")
        cat = KitchenCatalog(id=show_id, show=cfg["name"], lang=cfg["lang"], episodes=episodes,
                             source=ResearchSource(provider=wm.PROVIDER, title=f"Wikipedia: {cfg['page']}", url=page_url, license=wm.LICENSE,
                                                   note="Tabelas de episódios com resumos; fonte secundária, verificar fatos relevantes."))
        ctx.save("kitchen_catalogs", cat)
        return TaskResult(summary=f"{len(episodes)} episódios catalogados de {cfg['name']}", output={"catalog_id": show_id})

    def _story(self, ctx: AgentContext) -> TaskResult:
        episode_id = ctx.param("episode_id")
        cat = ctx.read("kitchen_catalogs", episode_id.split(":")[0], KitchenCatalog)
        ep = next((e for e in cat.episodes if e.id == episode_id), None) if cat else None
        if not ep:
            raise ValueError("Episódio não encontrado no catálogo")
        if not ep.summary:
            raise ValueError("A fonte não tem resumo deste episódio; adicione fatos manualmente com fonte")
        src = cat.source.model_copy(update={"id": f"src_{episode_id.replace(':', '_')}", "title": f"{cat.source.title} — {ep.restaurant}"})
        show = SHOWS[episode_id.split(":")[0]]
        story = build_story(ep, src, show["chef"], show["lang"])
        ctx.save("kitchen_stories", story)
        return TaskResult(summary=f"Dossiê '{ep.restaurant}': {len(story.facts)} fatos (pendentes de verificação)", output={"story_id": story.id})

    def _script(self, ctx: AgentContext) -> TaskResult:
        story = ctx.read("kitchen_stories", ctx.param("story_id"), KitchenStory)
        if not story:
            raise ValueError("Dossiê não encontrado")
        if not any(f.verified and f.language == "pt" for f in story.facts):
            raise ValueError("Nenhum fato verificado em português no dossiê. Verifique ou adicione fatos em português antes de gerar o roteiro.")
        script = build_script(story)
        ctx.save("scripts", script)
        return TaskResult(summary=f"Roteiro '{script.title}' (~{script.est_duration_s:.0f}s)", output={"script_id": script.id})
