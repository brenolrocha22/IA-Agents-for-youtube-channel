"""Agente — YouTube SEO: pacote de publicação pronto para colar no YouTube Studio.

Gera títulos, descrição, hashtags, tags, comentário fixado, créditos separados e sugestão de gancho a partir
do roteiro FINAL e das filmagens EFETIVAMENTE usadas. Regras: nada de títulos enganosos (cada afirmação do
título precisa estar na narração), sem hashtags irrelevantes, sem remover créditos obrigatórios.
Local e determinístico (sem LLM); o proprietário escolhe e edita antes de publicar.
"""
from __future__ import annotations

import re
import unicodedata

from ..channels import get_channel
from ..models import Script, Task, TaskResult, VisualPlan
from .base import Agent, AgentContext

EMOJI = {"polvo": "🐙", "tubarão": "🦈", "baleia": "🐋", "golfinho": "🐬", "tartaruga": "🐢", "água-viva": "🪼", "abelha": "🐝",
         "camaleão": "🦎", "restaurante": "🍽️", "chef": "👨‍🍳"}
FEATURES = ("aparência", "cor", "textura", "forma", "tamanho", "padrões")
MARINE = ("oceano", "mar", "recife", "profundezas", "marinho")
SEO_STOP = {"de", "da", "do", "das", "dos", "e", "o", "a", "os", "as", "um", "uma", "que", "em", "para", "com", "se", "seu", "sua"}


def _n(s: str) -> str:
    return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()


def subject_pt(script: Script) -> str:
    text = _n(" ".join(s.narration for s in script.sections))
    for pt in EMOJI:
        if _n(pt) in text:
            return pt
    return script.title.split()[0].lower()


def features_in(text: str) -> list[str]:
    """Características que a narração diz que o animal muda/altera/modifica (ordem de aparição)."""
    low = text.lower()
    found = []
    for m in re.finditer(r"\b(mud\w*|alter\w*|modific\w*|troc\w*)\b(?:\s+\w+){0,3}?\s+(" + "|".join(FEATURES) + r")\b", low):
        if m.group(2) not in found:
            found.append(m.group(2))
    for f in FEATURES:  # também "a cor e os padrões" na mesma frase
        if f in low and f not in found and re.search(rf"\b(mud|alter|modific)\w*\b[^.]*\b{f}\b", low):
            found.append(f)
    return found


def supported(title: str, narration: str) -> bool:
    """Toda palavra de conteúdo do título (exceto o assunto e conectores) precisa estar na narração."""
    words = [w for w in re.findall(r"[a-zà-ú]+", title.lower()) if len(w) > 3 and w not in SEO_STOP]
    low = narration.lower()
    allowed = {"esse", "este", "animal", "segundos", "minuto", "explicado", "menos", "porque", "verdadeiro"}
    return all(w in low or w in allowed or w[:-1] in low for w in words)


def hook_suggestion(script: Script) -> str:
    hook = script.sections[0].narration.strip()
    secs = len(hook.split()) / 2.3
    short = re.sub(r"^você sabia que existe (um|uma) (\w+) capaz de", lambda m: f"{'Este' if m.group(1) == 'um' else 'Esta'} {m.group(2)}",
                   hook, flags=re.I)
    short = re.sub(r"^você sabia que\s+", "", short, flags=re.I).rstrip("?") + ("." if short != hook else "")
    tip = (f"O gancho atual dura ~{secs:.1f}s. ")
    if short != hook:
        tip += f"Versão mais direta (afirmação em vez de pergunta): “{short[0].upper() + short[1:]}”. "
    return tip + "Mostre a transformação na imagem já no 1º segundo e escreva a ideia central na tela (3–4 palavras)."


def build_pack(script: Script, plan: VisualPlan | None, channel: dict, use_llm: bool = True) -> dict:
    narration = " ".join(s.narration for s in script.sections)
    subj = subject_pt(script)
    emoji = EMOJI.get(subj, "")
    feats = features_in(narration)
    fast = "segundos" in narration.lower()
    titles: list[str] = []
    visual_feats = [f for f in feats if f != "aparência"][:2]
    if len(visual_feats) >= 2:
        titles.append(f"{emoji} Esse animal muda de {visual_feats[0]} e de {visual_feats[1]}{' em segundos' if fast else ''}".strip())
    elif feats:
        titles.append(f"{emoji} Esse animal muda de {feats[0]}{' em segundos' if fast else ''}".strip())
    payoff = next((s.on_screen_text for s in script.sections if s.kind == "payoff" and s.on_screen_text), "")
    if payoff and payoff.lower() in narration.lower():
        art = "o" if subj not in ("abelha", "baleia", "tartaruga", "água-viva") else "a"
        titles.append(f"Por que {art} {subj} é um {payoff.lower()}? {emoji}".strip())
    titles.append(script.title)
    titles = [t[:100] for t in dict.fromkeys(titles) if supported(t, narration) or t == script.title][:3]

    hashtags = [f"#{subj.capitalize().replace('-', '')}", "#Curiosidades"]
    hashtags.append("#VidaMarinha" if any(m in narration.lower() for m in MARINE) else "#Natureza")
    hashtags += ["#Animais", "#Shorts"]

    summary = script.description.split("\n\n")[0].strip()
    summary = re.sub(r"\s*Um mini-documentário[^.]*\.", "", summary).strip()
    first = re.sub(r"^você sabia que\s+", "", script.sections[0].narration, flags=re.I).rstrip("?")
    description = (f"{first[0].upper() + first[1:]}? {emoji}\n\n{summary}\n\n"
                   f"Siga o {channel['name']} para mais curiosidades reais da natureza, com imagens de verdade.").strip()

    tags = [subj, f"{subj} curiosidades", *[f"{subj} {f}" for f in feats[:3]], "curiosidades da natureza", "animais",
            "vida marinha" if "#VidaMarinha" in hashtags else "natureza", "documentário curto", channel["name"]]
    if script.topic_en:
        tags.append(script.topic_en)
    tags = list(dict.fromkeys(t for t in tags if t))[:15]

    def as_option(text: str) -> str:  # "muda de cor" → "mudar de cor"; "oito braços" → "os oito braços"
        t = text.lower().strip()
        if t.startswith("muda "):
            return "mudar " + t[5:]
        return ("os " if t.split()[0] in ("dois", "três", "quatro", "cinco", "seis", "sete", "oito", "dez") else "") + t

    shown = [as_option(s.on_screen_text) for s in script.sections if s.kind == "point" and s.on_screen_text][:3]
    options = ", ".join(shown[:-1]) + f" ou {shown[-1]}" if len(shown) > 1 else (shown[0] if shown else "essa curiosidade")
    pinned = f"Qual habilidade do {subj} mais te surpreendeu: {options}? 👇 Conta aqui e sugere o próximo animal!"

    # Modo híbrido: copywriting pelo LLM, mantendo a trava de honestidade dos títulos.
    copy_note = "Textos gerados por modelo local (sem LLM)."
    if use_llm:
        from .llm_review import review_copy

        data, rep = review_copy(narration, [s.narration for s in script.sections], channel["name"])
        if data:
            llm_titles = [t[:100] for t in data.get("titles", []) if t and supported(t, narration)]
            titles = list(dict.fromkeys(llm_titles + titles))[:3]
            if data.get("description"):
                description = f"{data['description'].strip()}\n\nSiga o {channel['name']} para mais curiosidades reais da natureza."
            pinned = data.get("pinned_comment") or pinned
            dropped = len(data.get("titles", [])) - len(llm_titles)
            copy_note = (f"Copy revisado por {rep['model']} ({rep['usage']['total_tokens']} tokens)."
                         + (f" {dropped} título(s) do LLM descartado(s) por afirmar algo fora da narração." if dropped else ""))
        else:
            copy_note = f"LLM não usado: {rep['reason']}"

    credits = ["Fonte factual:"] + [f"- {s.title} — {s.url}" + (f" ({s.license})" if s.license else "") for s in script.sources]
    if plan:
        from ..production.documentary import used_footage

        used = used_footage(plan)
        credits += ["", "Imagens (filmagens reais usadas neste vídeo):"] + [f"- {c.credit}" for c in sorted(used, key=lambda c: c.title)]
    credits_text = "\n".join(credits)
    full = f"{description}\n\n{' '.join(hashtags)}\n\n— Créditos —\n{credits_text}"
    return {"titles": titles, "description": description, "hashtags": hashtags, "tags": tags, "pinned_comment": pinned,
            "credits": credits_text, "hook_suggestion": hook_suggestion(script), "youtube_description": full,
            "notes": [copy_note, "Aviso de conteúdo sintético do YouTube vale para conteúdo realista (pessoas, lugares, eventos); "
                      "narração por TTS sobre fatos não exige, mas a decisão final é do proprietário."]}


def copy_ready(pack: dict) -> str:
    """Texto único para colar no YouTube Studio."""
    lines = ["TÍTULO (escolha um):"] + [f"{i}. {t}" for i, t in enumerate(pack["titles"], 1)]
    lines += ["", "DESCRIÇÃO (cole inteira):", pack["youtube_description"], "", "TAGS (campo 'Tags' do YouTube Studio):",
              ", ".join(pack["tags"]), "", "COMENTÁRIO FIXADO:", pack["pinned_comment"], "", "SUGESTÃO PARA O GANCHO:",
              pack["hook_suggestion"]]
    return "\n".join(lines) + "\n"


class YouTubeSEO(Agent):
    name = "youtube_seo"
    title = "YouTube SEO Agent"
    description = ("Gera títulos honestos, descrição, hashtags, tags, comentário fixado, créditos separados e melhoria "
                   "de gancho a partir do roteiro final e das filmagens usadas. A escolha final é do proprietário.")
    task_types = ("seo_pack",)

    def run(self, task: Task, ctx: AgentContext) -> TaskResult:
        script = ctx.read("scripts", ctx.param("script_id"), Script)
        if not script:
            raise ValueError("Roteiro não encontrado")
        plan = ctx.read("visual_plans", script.visual_plan_id, VisualPlan) if script.visual_plan_id else None
        pack = build_pack(script, plan, get_channel(script.channel_id, "video"))
        return TaskResult(summary=f"{len(pack['titles'])} títulos, {len(pack['tags'])} tags, créditos de "
                                  f"{pack['credits'].count('- ')} itens", output={"seo": pack})
