from app.agents import llm_review
from app.models import PublishedVideo, Script, ScriptSection
from app.research.monitoring import refresh, video_id
from app.store import get_store


class FakeLLM:
    name = "openai"

    def __init__(self, reply):
        self.reply = reply

    def model(self):
        return "modelo-teste"

    def chat_json(self, system, user):
        return self.reply, {"total_tokens": 100, "cost_usd": 0.001}


def _script() -> Script:
    secs = [ScriptSection(kind="hook", heading="G", narration="O polvo muda de cor.", visual_note=""),
            ScriptSection(kind="point", heading="P", narration="Ele tem oito braços.", visual_note="")]
    return Script(brief_id="b", format="short", language="pt", tone="educativo", title="Polvo", title_variants=[], description="",
                  thumbnail_ideas=[], sections=secs, sources=[], provider="template")


def test_llm_review_applies_when_safe(monkeypatch):
    reply = {"sections": [{"narration": "Sabia que o polvo muda de cor?"}, {"narration": "E tem oito braços!"}], "title_variants": ["Polvo incrível"]}
    monkeypatch.setattr(llm_review, "get_llm", lambda: FakeLLM(reply))
    s, rep = llm_review.review_script(_script(), ["O polvo muda de cor.", "Ele tem oito braços."], 60)
    assert rep["applied"] and s.sections[0].narration.startswith("Sabia") and s.provider == "template+openai-review"


def test_llm_review_rejects_invented_numbers_and_scene_changes(monkeypatch):
    invented = {"sections": [{"narration": "O polvo muda de cor 300 vezes por dia."}, {"narration": "Tem oito braços."}]}
    monkeypatch.setattr(llm_review, "get_llm", lambda: FakeLLM(invented))
    s, rep = llm_review.review_script(_script(), ["O polvo muda de cor."], 60)
    assert not rep["applied"] and "300" in rep["reason"] and s.sections[0].narration == "O polvo muda de cor."
    monkeypatch.setattr(llm_review, "get_llm", lambda: FakeLLM({"sections": [{"narration": "Só uma cena"}]}))
    assert not llm_review.review_script(_script(), [], 60)[1]["applied"]


def test_llm_disabled_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    s, rep = llm_review.review_script(_script(), [], 60)
    assert not rep["applied"] and "não configurado" in rep["reason"]


def test_monitoring_ids_and_no_key(monkeypatch):
    assert video_id("https://www.youtube.com/shorts/sshOJpegjdw") == "sshOJpegjdw"
    assert video_id("https://youtu.be/sshOJpegjdw?si=x") == "sshOJpegjdw"
    assert video_id("https://example.com/x") is None
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    get_store().put("published_videos", PublishedVideo(id="sshOJpegjdw", url="https://www.youtube.com/shorts/sshOJpegjdw"))
    r = refresh(get_store(), force=True)
    assert r["updated"] == 0 and "YOUTUBE_API_KEY" in r["reason"]
    assert "YOUTUBE_API_KEY" in get_store().get("published_videos", "sshOJpegjdw", PublishedVideo).last_error
