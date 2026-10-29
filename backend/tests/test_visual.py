import wave

from app.agents.visual_hunter import infer_action, metadata_score, parse_action, queries_for
from app.models import VisualCandidate, VisualPlan, VisualScene
from app.production.documentary import caption_chunks, write_ass
from app.production.tts import SAMPLE_RATE, calibrate
from app.research import licensing


def cand(title: str, desc: str = "", lic: str = "CC BY 4.0") -> VisualCandidate:
    ev = licensing.evaluate(lic)
    return VisualCandidate(id=title, provider="t", title=title, description=desc, page_url="u", file_url="f", license=lic,
                           license_status=ev["status"])


def test_license_policy():
    assert licensing.evaluate("CC0")["status"] == "aceita" and not licensing.evaluate("CC0")["attribution"]
    assert licensing.evaluate("CC BY 4.0") == {**licensing.evaluate("CC BY 4.0"), "status": "aceita", "attribution": True}
    sa = licensing.evaluate("CC BY-SA 3.0")
    assert sa["status"] == "condicional" and sa["share_alike"]
    assert licensing.evaluate("CC BY-NC 4.0")["status"] == "rejeitada"
    assert licensing.evaluate("CC BY-ND 4.0")["status"] == "rejeitada"
    assert licensing.evaluate("")["status"] == "rejeitada"  # direitos desconhecidos
    assert licensing.evaluate("All rights reserved")["status"] == "rejeitada"


def test_semantic_actions_and_queries():
    assert infer_action("Quando ameaçado, libera uma nuvem de tinta.") == "ink"
    assert "color" in infer_action("O polvo consegue mudar a cor da pele.")
    assert parse_action("prey+arms|suckers") == [["prey"], ["arms", "suckers"]]
    qs = queries_for("octopus", "ink", "octopus releasing ink underwater")
    assert qs[0] == "octopus releasing ink underwater" and "octopus ink" in qs


def test_metadata_score_avoids_false_positives():
    syn = ("octopus", "krake")
    # "Tintenfisch" (alemão: lula) não pode contar como "tinta"
    assert metadata_score(cand("Octopus vulgaris im Zoo", "Octopus Tintenfisch im Zoo Basel"), syn, "ink")[0] == 0
    assert metadata_score(cand("Octopus inking", "octopus releasing an ink cloud"), syn, "ink")[0] == 1.0
    # assunto errado ou contexto excluído
    assert metadata_score(cand("Laser tattoo removal", "ink"), syn, "ink")[0] == 0
    assert metadata_score(cand("How to cook octopus", "recipe"), syn, "")[0] == 0


def test_coverage_counts_only_validated_time():
    s = lambda i, v, a, b: VisualScene(index=i, narration="x", action="", queries=[], start=a, end=b, selected_id="c", validation=v)  # noqa: E731
    plan = VisualPlan(script_id="s", subject_en="octopus", providers=[], scenes=[s(0, "validada", 0, 6), s(1, "revisao", 6, 10)])
    assert plan.coverage() == 0.6


def test_tts_calibration_and_caption_timing(tmp_path):
    wav_path = tmp_path / "a.wav"
    with wave.open(str(wav_path), "wb") as w:  # 0,5 s silêncio + 2 s "fala" + 0,5 s silêncio
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(b"\x00\x00" * (SAMPLE_RATE // 2) + b"\x00\x40" * (SAMPLE_RATE * 2) + b"\x00\x00" * (SAMPLE_RATE // 2))
    raw = [{"t": 0.5 / (16000 / SAMPLE_RATE), "word": "O"}, {"t": 1.5 / (16000 / SAMPLE_RATE), "word": "polvo"}]
    cal = calibrate(raw, wav_path)
    assert abs(cal[0]["t"] - 0.5) < 0.01 and abs(cal[1]["t"] - 1.5) < 0.01
    cues = caption_chunks([{"t": 0.1, "word": "O"}, {"t": 0.3, "word": "polvo"}, {"t": 0.9, "word": "muda."}, {"t": 1.4, "word": "Sim"}], 10, 12)
    assert cues[0]["start"] == 10.1 and cues[0]["end"] == cues[1]["start"] == 11.4  # fim = início da próxima legenda
    ass = tmp_path / "c.ass"
    write_ass(cues, ass, {"polvo"}, {"green_light": (120, 230, 180)})
    text = ass.read_text(encoding="utf-8")
    assert "Dialogue: 0,0:00:10.10" in text and "\\c&H00B4E678&" in text
