from app.agents.seo import build_pack, features_in, supported
from app.channels import get_channel
from app.models import ResearchSource, Script, ScriptSection, VisualCandidate, VisualPlan, VisualScene


def _script() -> Script:
    secs = [ScriptSection(kind="hook", heading="G", narration="Você sabia que existe um animal capaz de mudar de aparência em segundos?",
                          visual_note="", on_screen_text="MUDA EM SEGUNDOS"),
            ScriptSection(kind="point", heading="Cor", narration="O polvo consegue alterar a cor e os padrões da pele no oceano.",
                          visual_note="", on_screen_text="MUDA DE COR"),
            ScriptSection(kind="point", heading="Textura", narration="Algumas espécies modificam a textura da pele.",
                          visual_note="", on_screen_text="MUDA A TEXTURA"),
            ScriptSection(kind="payoff", heading="Fim", narration="O polvo é um verdadeiro mestre da sobrevivência.",
                          visual_note="", on_screen_text="MESTRE DA SOBREVIVÊNCIA")]
    return Script(brief_id="m", format="short", language="pt", tone="doc", title="O mestre do disfarce do oceano",
                  title_variants=[], description="Polvos mudam de cor.\n\nNarração com voz sintética.", thumbnail_ideas=[],
                  sections=secs, sources=[ResearchSource(provider="w", title="Wikipedia: Polvo", url="https://pt.wikipedia.org/wiki/Polvo")],
                  provider="proprietário", channel_id="natureza", topic_en="octopus")


def _cand(cid: str, title: str) -> VisualCandidate:
    return VisualCandidate(id=cid, provider="Wikimedia Commons", title=title, page_url=f"https://x/{cid}", file_url="f",
                           license="CC BY 4.0", license_status="aceita", credit=f"“{title}” — autor — CC BY 4.0 — https://x/{cid}")


def test_seo_pack_is_honest_and_complete():
    sc = _script()
    used, unused = _cand("a", "Usado"), _cand("b", "NaoUsado")
    plan = VisualPlan(script_id=sc.id, subject_en="octopus", providers=[], scenes=[
        VisualScene(index=0, narration="", action="", queries=[], candidates=[used, unused], selected_id="a", validation="validada")])
    pack = build_pack(sc, plan, get_channel("natureza"))
    assert 1 <= len(pack["titles"]) <= 3 and all(len(t) <= 100 for t in pack["titles"])
    assert pack["titles"][0].startswith("🐙 Esse animal muda de cor e de textura")
    assert all("desaparec" not in t.lower() for t in pack["titles"])  # nada que o vídeo não mostre
    assert len(pack["hashtags"]) == 5 and "#Polvo" in pack["hashtags"] and "#VidaMarinha" in pack["hashtags"]
    assert "Usado" in pack["credits"] and "NaoUsado" not in pack["credits"]  # só filmagens da versão final
    assert "voz sintética" not in pack["description"]
    assert "— Créditos —" in pack["youtube_description"]
    assert "Este animal" in pack["hook_suggestion"]


def test_title_support_check():
    narr = "O polvo muda de cor e de textura em segundos."
    assert supported("Esse animal muda de cor e de textura", narr)
    assert not supported("Esse animal consegue desaparecer", narr)
    assert features_in("Ele consegue alterar a cor e os padrões da pele e modifica a textura") [:2] == ["cor", "textura"]
