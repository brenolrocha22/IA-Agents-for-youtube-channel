"""Agente 5 — Scriptwriter: roteiros originais a partir de fatos com fonte.

Provedores: `template` (local, determinístico) e `llm` (interface do modo híbrido; desativado sem chave).
"""
from __future__ import annotations

import hashlib
import re

from ..channels import get_channel
from ..config import env
from ..models import Script, ScriptSection, Task, TaskResult, VideoBrief
from .base import Agent, AgentContext

WORDS_PER_SECOND = 2.3  # calibrado com a voz SAPI pt-BR (velocidade 1) em 2026-10-29

# Pares de loop: a frase final (loop) termina de forma que o gancho (hook) a complete.
# A resposta prometida sempre é entregue antes do loop (D10).
LOOPS = {
    "comico": [
        ("E é por isso que, toda vez que alguém fala de {t}, eu penso:", "{T} é muito mais estranho do que parece."),
        ("Agora você vai ser aquela pessoa chata da festa que diz:", "Peraí, você sabia isso sobre {t}?"),
    ],
    "educativo": [
        ("E agora você entende por que dizem que", "{T} é mais importante do que parece."),
        ("Então, da próxima vez que ouvir falar disso, lembre:", "{T} tem um detalhe que quase ninguém conhece."),
    ],
    "criativo": [
        ("E se alguém de 500 anos atrás ouvisse isso, diria:", "{T}? Isso parece magia."),
        ("Resumindo em uma frase que cabe num biscoito da sorte:", "{T} é maior do que a gente imagina."),
    ],
}
ASIDES = {
    "comico": ["Sim, é sério.", "Respira.", "Anota aí.", "Pois é.", "Calma que piora.", "Ninguém esperava essa."],
    "educativo": ["Guarde esse dado.", "Isso é importante.", "Agora o detalhe.", "Repare nisso."],
    "criativo": ["Imagina a cena.", "Pensa comigo.", "Visualiza isso.", "Parece ficção, mas não é."],
}
LABELS = ["Fato 1", "Fato 2", "Fato 3", "Fato 4", "Fato 5", "Fato 6"]
CLICKBAIT = ("você não vai acreditar", "chocante", "urgente", "garantido", "100%")


def _seed(text: str) -> int:
    return int(hashlib.md5(text.encode()).hexdigest(), 16)


def _short_fact(text: str, max_words: int = 34) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    cut = " ".join(words[:max_words])
    return re.sub(r"[,;:]?\s*\S*$", "", cut) + "."


def estimate_seconds(text: str) -> float:
    return round(len(text.split()) / WORDS_PER_SECOND, 1)


class TemplateScriptProvider:
    name = "template"

    def is_configured(self) -> bool:
        return True

    def write_list(self, brief: VideoBrief) -> Script:
        """Formato Lista/Top N: gancho, uma cena por item (fato verificado + filmagem do próprio item), fechamento."""
        n, t = len(brief.items), brief.topic
        sections = [ScriptSection(kind="hook", heading="Gancho", narration=f"{n} {t} que você precisa conhecer.",
                                  on_screen_text=f"TOP {n}", visual_note="Abertura rápida com o 1º item.",
                                  visual_subject=brief.items[0]["title_en"])]
        for k, item in enumerate(brief.items, 1):
            sections.append(ScriptSection(
                kind="point", heading=f"{k}. {item['title']}", narration=f"Número {k}: {item['title']}. {_short_fact(item['fact'], 30)}",
                on_screen_text=f"#{k} {item['title'].upper()}", source_ids=[item["source_id"]],
                visual_note=f"Filmagem real de {item['title']}.", visual_subject=item["title_en"], visual_query=item["title_en"]))
        sections.append(ScriptSection(kind="payoff", heading="Fechamento", narration="Qual desses é o seu favorito? Conta nos comentários.",
                                      on_screen_text="QUAL O SEU FAVORITO?", visual_note="Retoma o item mais impactante.",
                                      visual_subject=brief.items[0]["title_en"]))
        for s in sections:
            s.est_seconds = estimate_seconds(s.narration)
        names = ", ".join(i["title"] for i in brief.items)
        src_lines = "\n".join(f"- {s.title}: {s.url} (consultado em {s.collected_at:%Y-%m-%d})" for s in brief.sources)
        title = f"{n} {t} que você precisa conhecer"
        return Script(
            brief_id=brief.id, format=brief.format, language=brief.language, tone=brief.tone, title=title[:100],
            title_variants=[title[:100], f"Top {n}: {t}", f"{t}: {names}"[:100]],
            description=f"{title}: {names}.\n\nFontes:\n{src_lines}\n\nTexto de referência: Wikipedia (CC BY-SA 4.0).",
            hashtags=["#shorts", "#curiosidades", "#animais"], thumbnail_ideas=[f"Capa: 'TOP {n}' + {brief.items[0]['title']}"],
            sections=sections, sources=brief.sources, loop=False, provider=self.name,
            est_duration_s=round(sum(s.est_seconds for s in sections) + 0.35 * len(sections), 1),
        )

    def write(self, brief: VideoBrief) -> Script:
        if brief.items:
            return self.write_list(brief)
        tone = brief.tone if brief.tone in LOOPS else "educativo"
        t = brief.topic
        rnd = _seed(brief.id + t)
        asides = ASIDES[tone]
        sections: list[ScriptSection] = []
        n_points = 3 if brief.format == "short" else min(6, len(brief.facts))
        facts = brief.facts[:n_points]

        loop_line, hook_line = LOOPS[tone][rnd % len(LOOPS[tone])]
        hook = hook_line.format(t=t, T=t)
        sections.append(ScriptSection(kind="hook", heading="Gancho", narration=hook,
                                      on_screen_text=t.upper(), visual_note="Título grande, cor de destaque, entrada imediata (sem fade)."))
        if brief.format == "long" and brief.topic_description:
            ctx_txt = f"Primeiro, o básico: {t} é {brief.topic_description}."
            sections.append(ScriptSection(kind="context", heading="Contexto", narration=ctx_txt,
                                          on_screen_text="O BÁSICO", visual_note="Cartão de contexto."))
        for i, f in enumerate(facts):
            aside = asides[(rnd + i) % len(asides)]
            narr = f"{_short_fact(f.text)} {aside}" if i < len(facts) - 1 or brief.format == "long" else _short_fact(f.text)
            sections.append(ScriptSection(kind="point", heading=LABELS[i], narration=narr, source_ids=[f.source_id],
                                          on_screen_text=LABELS[i].upper(), visual_note="Troca de cor a cada legenda; número do fato no topo."))
        payoff = {
            "comico": f"Resumo: {t} não é só aquilo que te ensinaram. É bem mais curioso.",
            "educativo": f"Ou seja: agora você sabe o essencial sobre {t}, com fontes na descrição.",
            "criativo": f"No fim, {t} é uma daquelas histórias reais que parecem inventadas.",
        }[tone]
        sections.append(ScriptSection(kind="payoff", heading="Resposta", narration=payoff,
                                      on_screen_text="RESUMO", visual_note="Recapitula os fatos; responde o gancho."))
        if brief.format == "short":
            sections.append(ScriptSection(kind="loop", heading="Loop", narration=loop_line,
                                          on_screen_text=t.upper(), visual_note="Mesmo fundo do gancho; corte seco para reiniciar o vídeo."))
        else:
            sections.append(ScriptSection(kind="cta", heading="Encerramento", narration="Se quiser outro tema assim, deixe nos comentários.",
                                          on_screen_text="", visual_note="Tela final."))
        for s in sections:
            s.est_seconds = estimate_seconds(s.narration)

        slug = re.sub(r"[^a-z0-9]", "", t.lower())[:24]
        titles = {
            "comico": [f"{t} é mais estranho do que parece", f"Ninguém me contou isso sobre {t}", f"{t}: os fatos mais curiosos"],
            "educativo": [f"{t} explicado em 30 segundos", f"O essencial sobre {t}", f"3 fatos sobre {t} que valem saber"],
            "criativo": [f"{t} como você nunca imaginou", f"Se {t} fosse um filme…", f"{t} em 3 cenas"],
        }[tone]
        src_lines = "\n".join(f"- {s.title}: {s.url} (consultado em {s.collected_at:%Y-%m-%d})" for s in brief.sources)
        licenses = {s.license for s in brief.sources if s.license}
        description = (
            f"{titles[0]}. {brief.angle}\n\nFontes:\n{src_lines}\n"
            + (f"\nTexto de referência licenciado sob {', '.join(licenses)} — atribuição aos autores dos artigos citados.\n" if licenses else "")
            + "\nNarração com voz sintética."
        )
        script = Script(
            brief_id=brief.id, format=brief.format, language=brief.language, tone=tone, title=titles[0],
            title_variants=titles, description=description,
            hashtags=["#shorts", f"#{slug}", "#curiosidades"] if brief.format == "short" else [f"#{slug}"],
            thumbnail_ideas=[
                f"Capa: '{t.upper()}' em letras grandes + emoji 🤯 sobre fundo de alto contraste",
                f"Capa: pergunta curta '{t}?' + seta apontando para um elemento visual do tema",
                "Capa: comparação 'o que você acha × a realidade' em tela dividida",
            ],
            sections=sections, sources=brief.sources, loop=brief.format == "short",
            provider=self.name, est_duration_s=round(sum(s.est_seconds for s in sections) + 0.35 * len(sections), 1),
        )
        return script


class LLMScriptProvider:
    """Modo híbrido (D10). Ainda não implementado: requer ANTHROPIC_API_KEY e teto de custo."""

    name = "llm"

    def is_configured(self) -> bool:
        return False  # habilitar quando a implementação existir (ver TASKS.md, backlog)

    def write(self, brief: VideoBrief) -> Script:
        raise RuntimeError("Provedor LLM não implementado; use SCRIPT_PROVIDER=template")


def get_script_provider():
    wanted = env("SCRIPT_PROVIDER", "template")
    llm = LLMScriptProvider()
    if wanted == "llm" and llm.is_configured():
        return llm
    return TemplateScriptProvider()


class Scriptwriter(Agent):
    name = "scriptwriter"
    title = "Scriptwriter"
    description = "Cria roteiros originais (Shorts em loop e vídeos longos), títulos, descrição e ideias de capa."
    task_types = ("write_script",)
    owned_kinds = frozenset({"scripts"})

    def run(self, task: Task, ctx: AgentContext) -> TaskResult:
        brief = ctx.read("briefs", ctx.param("brief_id"), VideoBrief)
        if not brief:
            raise ValueError("Briefing não encontrado")
        provider = get_script_provider()
        script = provider.write(brief)
        channel = get_channel(ctx.param("channel_id"), "video")
        script.channel_id = channel["id"]
        script.topic_en = brief.topic_en
        if script.format == "short":
            script.hashtags = list(dict.fromkeys(channel["hashtags"] + script.hashtags[1:]))
        ctx.save("scripts", script)
        return TaskResult(summary=f"Roteiro '{script.title}' (~{script.est_duration_s:.0f}s, {provider.name})",
                          output={"script_id": script.id})
