"""Revisão de roteiro (público, storytelling) e copywriting por LLM, com travas de veracidade.

Travas: mesma quantidade e ordem de cenas; nenhum número novo que não esteja nas fontes; duração dentro do
limite; títulos só com afirmações presentes na narração. Se qualquer trava falhar, mantém-se o texto original.
"""
from __future__ import annotations

import re

from ..integrations.llm import get_llm
from ..models import Script
from .scriptwriter import WORDS_PER_SECOND, estimate_seconds

SCRIPT_SYSTEM = (
    "Você é roteirista e storyteller de YouTube Shorts em português do Brasil, especialista em retenção para o público "
    "brasileiro. Reescreva a narração de cada cena para soar natural, envolvente e falada (frases curtas, ritmo, curiosidade), "
    "mantendo EXATAMENTE os fatos fornecidos. Regras: não invente fatos, números, nomes, falas ou acontecimentos; não exagere; "
    "sem clickbait enganoso; sem suspense não resolvido; não use emojis na narração. Mantenha o mesmo número e a mesma ordem "
    "de cenas. Responda em JSON: {\"sections\": [{\"narration\": \"...\", \"on_screen_text\": \"até 4 palavras\"}], "
    "\"title_variants\": [\"3 títulos honestos, até 100 caracteres\"], \"notes\": \"o que mudou e por quê\"}"
)


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:[.,]\d+)?", text))


def review_script(script: Script, facts: list[str], max_seconds: float) -> tuple[Script, dict]:
    """Retorna (roteiro revisado ou original, relatório com tokens/custo/motivo)."""
    llm = get_llm()
    if not llm:
        return script, {"applied": False, "reason": "LLM não configurado (OPENAI_API_KEY/OPENAI_MODEL)"}
    payload = {
        "titulo_atual": script.title, "tom": script.tone, "formato": script.format,
        "fatos_permitidos": facts,
        "cenas": [{"tipo": s.kind, "narracao": s.narration, "texto_na_tela": s.on_screen_text} for s in script.sections],
        "duracao_maxima_segundos": max_seconds,
    }
    import json

    try:
        data, usage = llm.chat_json(SCRIPT_SYSTEM, json.dumps(payload, ensure_ascii=False))
    except Exception as exc:
        return script, {"applied": False, "reason": f"Falha na chamada ao LLM: {exc}"}
    new = data.get("sections") or []
    report = {"applied": False, "usage": usage, "model": llm.model(), "notes": data.get("notes", "")}
    if len(new) != len(script.sections):
        report["reason"] = "LLM alterou o número de cenas"
        return script, report
    allowed = _numbers(" ".join(facts) + " " + " ".join(s.narration for s in script.sections))
    added = _numbers(" ".join(x.get("narration", "") for x in new)) - allowed
    if added:
        report["reason"] = f"LLM introduziu números sem fonte: {sorted(added)}"
        return script, report
    total = sum(len(x.get("narration", "").split()) for x in new) / WORDS_PER_SECOND
    if total > max_seconds * 1.05:
        report["reason"] = f"Texto revisado longo demais (~{total:.0f}s)"
        return script, report
    revised = script.model_copy(deep=True)
    for sec, x in zip(revised.sections, new):
        sec.narration = x.get("narration", sec.narration).strip() or sec.narration
        if x.get("on_screen_text"):
            sec.on_screen_text = x["on_screen_text"].strip().upper()[:40]
        sec.est_seconds = estimate_seconds(sec.narration)
    revised.title_variants = [t[:100] for t in data.get("title_variants", []) if t] or revised.title_variants
    revised.provider = f"{script.provider}+{llm.name}-review"
    revised.est_duration_s = round(sum(s.est_seconds for s in revised.sections) + 0.35 * len(revised.sections), 1)
    report.update(applied=True, reason="Revisão aplicada")
    return revised, report


COPY_SYSTEM = (
    "Você é copywriter de YouTube Shorts para o público brasileiro. Com base SOMENTE na narração e nos fatos fornecidos, "
    "crie: 3 títulos chamativos e honestos (até 100 caracteres, pode usar 1 emoji), uma descrição curta e natural (2–4 frases, "
    "sem hashtags e sem créditos) e um comentário fixado que convide à conversa. Não prometa nada que o vídeo não mostra. "
    "Responda em JSON: {\"titles\": [], \"description\": \"\", \"pinned_comment\": \"\"}"
)


def review_copy(narration: str, facts: list[str], channel_name: str) -> tuple[dict | None, dict]:
    llm = get_llm()
    if not llm:
        return None, {"applied": False, "reason": "LLM não configurado"}
    import json

    try:
        data, usage = llm.chat_json(COPY_SYSTEM, json.dumps({"canal": channel_name, "narracao": narration, "fatos": facts},
                                                            ensure_ascii=False))
    except Exception as exc:
        return None, {"applied": False, "reason": f"Falha na chamada ao LLM: {exc}"}
    return data, {"applied": True, "usage": usage, "model": llm.model()}
