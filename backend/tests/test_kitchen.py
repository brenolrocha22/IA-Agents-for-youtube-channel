import pytest

from app.agents.quality import review_script
from app.agents.reality_kitchen import build_script, build_story, parse_episode_tables
from app.models import KitchenStory, LicensedAsset, ResearchSource, Scene, Script, TaskStatus
from app.orchestrator.orchestrator import Orchestrator
from app.store import get_store

# Estrutura igual à das tabelas de episódios da Wikipedia; conteúdo fictício apenas para teste do parser.
HTML = """
<table class="wikitable plainrowheaders"><tbody>
<tr><th>№ em geral</th><th>№ na temporada</th><th>Restaurante</th><th>Localização</th><th>Data de exibição</th></tr>
<tr class="vevent"><th>1</th><td>1</td><td>"Cantina Teste"</td><td>Cidade X, SP</td><td>5 de março de 2019<sup>[1]</sup></td></tr>
<tr class="expand-child"><td class="description" colspan="5">Os sócios brigam sobre dívidas e a cozinha tem problemas de higiene.
O chef ensina a equipe a organizar o estoque. O restaurante passa por uma reforma e ganha novo cardápio. O restaurante fechou em 2021.</td></tr>
</tbody></table>
"""


def _story() -> KitchenStory:
    eps = parse_episode_tables(HTML, "pesadelo_br", "Pesadelo na Cozinha (Brasil)", "https://pt.wikipedia.org/wiki/Pesadelo_na_Cozinha")
    assert len(eps) == 1 and eps[0].restaurant == "Cantina Teste" and eps[0].air_year == 2019
    src = ResearchSource(provider="wikimedia", title="Wikipedia", url=eps[0].source_url)
    return build_story(eps[0], src, "Chef")


def test_story_classifies_stages_and_marks_pending():
    story = _story()
    stages = {f.stage for f in story.facts}
    assert {"contexto", "conflito", "intervencao", "transformacao", "resultado"} <= stages
    assert not any(f.verified for f in story.facts)  # nada entra no roteiro sem verificação
    assert any(f.category == "posterior_verificado" for f in story.facts if f.stage == "resultado")
    assert all(s.visual_type != "material_terceiros" for s in story.scenes)


def test_script_uses_only_verified_facts_and_cites_year():
    story = _story()
    story.facts[0].verified = True  # só o contexto
    script = build_script(story)
    text = " ".join(s.narration for s in script.sections)
    assert "2019" in text and "brigam" not in text
    assert "não vai inventar" in text  # resultado ausente não é preenchido
    report = review_script(script, None, story, {})
    codes = {c.code: c.status for c in report.checks}
    assert codes["fatos_verificados"] == "pass" and codes["ano_exibicao"] == "pass"
    assert codes["materiais_autorizados"] == "pass"


def test_unauthorized_third_party_scene_blocks_approval_and_render():
    story = _story()
    for f in story.facts:
        f.verified = True
    story.scenes.append(Scene(stage="conflito", description="Trecho do episódio original", visual_type="material_terceiros"))
    get_store().put("kitchen_stories", story)
    orch = Orchestrator(store=get_store())
    wf = orch.create_workflow("kitchen_short", {"story_id": story.id}, "teste")
    orch.run_until_idle()
    report = review_script(get_store().list("scripts", Script)[0], None, story, {})
    assert report.blocking
    gate = next(t for t in orch.tasks_of(wf) if t.type == "editorial_approval")
    assert gate.status == TaskStatus.awaiting_approval
    with pytest.raises(Exception):
        orch.approve(gate.id)
    # com licença registrada a cena deixa de bloquear
    asset = LicensedAsset(name="clip", origin="emissora", license="contrato X", scope="1 trecho de 5s")
    story.scenes[-1].asset_id = asset.id
    assert not review_script(build_script(story), None, story, {asset.id: asset}).blocking
