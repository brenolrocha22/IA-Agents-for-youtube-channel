"""Agente 4 — Retention Strategist: análise estrutural do próprio roteiro (não de retenção real de terceiros)."""
from __future__ import annotations

from ..models import Script, Task, TaskResult
from .base import Agent, AgentContext


def analyze(script: Script) -> list[str]:
    notes: list[str] = []
    hook = next((s for s in script.sections if s.kind == "hook"), None)
    limit = 3.0 if script.format == "short" else 15.0
    if hook:
        ok = hook.est_seconds <= limit
        notes.append(f"Gancho com ~{hook.est_seconds:.1f}s ({'ok' if ok else 'longo demais'}; alvo ≤ {limit:.0f}s).")
    dur = script.est_duration_s
    if script.format == "short":
        notes.append(f"Duração estimada {dur:.0f}s. Hipótese a testar: 20–45s favorece revisualização em loop.")
        if script.loop:
            notes.append("Loop: a frase final conduz ao gancho; a resposta é entregue antes (sem suspense não resolvido).")
        notes.append("Ritmo: legendas de 2–5 palavras com troca visual a cada ~1,5s.")
    else:
        notes.append(f"Duração estimada {dur / 60:.1f} min. Garanta uma virada a cada 60–90s.")
    words = [len(s.narration.split()) for s in script.sections]
    longest = max(words) if words else 0
    if longest > 45:
        notes.append(f"Um bloco tem {longest} palavras; considere dividir para manter o ritmo.")
    notes.append(
        "Teste A/B sugerido: título 1 × título 2 em Shorts equivalentes, mesmo horário; comparar % de "
        "visualização e visualizações após 7 dias (amostra mínima: 3 vídeos por variante)."
    )
    return notes


class RetentionStrategist(Agent):
    name = "retention_strategist"
    title = "Retention Strategist"
    description = "Analisa estrutura narrativa, ritmo e loop; sugere testes de título e capa. Não alega retenção real de terceiros."
    task_types = ("retention_review",)
    owned_kinds = frozenset({"scripts"})

    def run(self, task: Task, ctx: AgentContext) -> TaskResult:
        script = ctx.read("scripts", ctx.param("script_id"), Script)
        if not script:
            raise ValueError("Roteiro não encontrado")
        script.retention_notes = analyze(script)
        ctx.save("scripts", script)
        return TaskResult(summary=f"{len(script.retention_notes)} recomendações de ritmo/retenção",
                          output={"retention_notes": script.retention_notes})
