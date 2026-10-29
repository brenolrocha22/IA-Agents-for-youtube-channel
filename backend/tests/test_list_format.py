from app.agents.scriptwriter import TemplateScriptProvider
from app.agents.visual_hunter import scene_synonyms
from app.models import Fact, ResearchSource, Script, VideoBrief
from app.orchestrator.orchestrator import Orchestrator
from app.research import wikimedia as wm
from app.store import get_store


def test_list_brief_produces_one_scene_per_item():
    src = ResearchSource(provider="w", title="Wikipedia", url="https://pt.wikipedia.org/wiki/X")
    items = [{"title": "Ornitorrinco", "title_en": "Platypus", "fact": "O ornitorrinco é um mamífero que bota ovos.", "source_id": src.id},
             {"title": "Coala", "title_en": "Koala", "fact": "O coala dorme até 20 horas por dia.", "source_id": src.id}]
    brief = VideoBrief(niche_id="natureza_animais", topic="animais da Austrália", angle="", audience="", key_points=[],
                       facts=[Fact(text=i["fact"], source_id=src.id) for i in items], sources=[src], items=items)
    script = TemplateScriptProvider().write(brief)
    points = [s for s in script.sections if s.kind == "point"]
    assert [s.visual_subject for s in points] == ["Platypus", "Koala"]  # filmagem do próprio item
    assert "bota ovos" in points[0].narration and points[0].source_ids == [src.id]
    assert script.title.startswith("2 animais da Austrália")


def test_scene_synonyms():
    assert scene_synonyms("Platypus") == ("platypus",)
    assert "devil" in scene_synonyms("Tasmanian devil")


def test_free_text_topic_resolves_to_article(monkeypatch, fake_wiki):
    calls = {"n": 0}
    real = wm.page_summary

    def summary(store, lang, title, budget=None):
        calls["n"] += 1
        return None if title == "animais_da_Austrália" else real(store, lang, title, budget)

    monkeypatch.setattr(wm, "page_summary", summary)
    monkeypatch.setattr(wm, "resolve_title", lambda store, lang, q, budget=None: "Fauna_da_Austrália")
    monkeypatch.setattr(wm, "english_title", lambda *a, **k: "Fauna of Australia")
    orch = Orchestrator(store=get_store())
    orch.create_workflow("video", {"topic": "animais_da_Austrália", "format": "short", "tone": "educativo", "language": "pt"}, "t")
    orch.run_until_idle()
    script = get_store().list("scripts", Script)[0]
    assert script.topic_en == "Fauna of Australia"
