import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import store as store_mod  # noqa: E402
from app.orchestrator import orchestrator as orch_mod  # noqa: E402
from app.research import wikimedia as wm  # noqa: E402

EXTRACT = (
    "Marte é o quarto planeta a partir do Sol e o segundo menor do Sistema Solar. "
    "O planeta tem o maior vulcão conhecido, o Monte Olimpo, com cerca de 22 quilômetros de altura. "
    "Um dia em Marte dura aproximadamente 24 horas e 37 minutos, quase igual ao da Terra. "
    "Marte possui duas luas pequenas chamadas Fobos e Deimos, descobertas em 1877. "
    "A cor avermelhada vem do óxido de ferro presente na superfície do planeta."
)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("CIOS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CIOS_OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("TTS_PROVIDER", "silent")
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    store_mod.reset_store()
    orch_mod.reset_orchestrator()
    yield
    orch_mod.reset_orchestrator()
    store_mod.reset_store()


@pytest.fixture
def fake_wiki(monkeypatch):
    monkeypatch.setattr(wm, "page_summary", lambda store, lang, title, budget=None: {
        "title": "Marte", "description": "quarto planeta do Sistema Solar", "extract": EXTRACT,
        "url": "https://pt.wikipedia.org/wiki/Marte_(planeta)", "type": "standard"})
    monkeypatch.setattr(wm, "page_text", lambda store, lang, title, budget=None, max_chars=8000: "")
