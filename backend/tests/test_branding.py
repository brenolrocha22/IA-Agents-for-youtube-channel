from PIL import Image

from app.agents.reality_kitchen import build_script, build_story, parse_episode_tables
from app.channels import get_channel
from app.models import ResearchSource
from app.production import brand_clip
from app.production.branding import render_brand_assets


def test_clip_branding_sizes_and_white_hat(tmp_path):
    ch = get_channel("clips_plus")
    render_brand_assets(ch, tmp_path)
    sizes = {"avatar_800x800": (800, 800), "banner_2560x1440": (2560, 1440), "capa_modelo_1080x1920": (1080, 1920)}
    for name, size in sizes.items():
        assert Image.open(tmp_path / f"{name}.png").size == size
    assert (tmp_path / "logo.svg").exists()
    # Centro do corpo do chapéu no avatar: branco puro
    avatar = Image.open(tmp_path / "avatar_800x800.png").convert("RGB")
    assert avatar.getpixel((400, int(800 * 0.27))) == (255, 255, 255)


def test_each_channel_uses_its_own_style(tmp_path):
    assert get_channel("clips_plus")["style"] == "clip_reality"
    assert get_channel("natureza")["style"] == "nat_wild"
    clip_dir, nat_dir = tmp_path / "clip", tmp_path / "nat"
    render_brand_assets(get_channel("clips_plus"), clip_dir)
    before = {p.name: p.read_bytes() for p in clip_dir.glob("*.png")}
    render_brand_assets(get_channel("natureza"), nat_dir)
    assert {p.name: p.read_bytes() for p in clip_dir.glob("*.png")} == before  # gerar o Nat não altera o Clip+


def test_nat_branding_three_variants(tmp_path):
    from app.production import brand_nat
    render_brand_assets(get_channel("natureza"), tmp_path)
    expected = {"avatar_800x800": (800, 800), "banner_2560x1440": (2560, 1440), "capa_modelo_1080x1920": (1080, 1920),
                "capa_modelo_vida_selvagem_1080x1920": (1080, 1920), "capa_modelo_cinematografica_1080x1920": (1080, 1920)}
    for name, size in expected.items():
        assert Image.open(tmp_path / f"{name}.png").size == size
    assert (tmp_path / "logo.svg").exists()
    assert brand_nat.choose_variant("O predador mais rápido") == "vida_selvagem"
    assert brand_nat.choose_variant("A floresta que respira") == "cinematografica"
    assert brand_nat.choose_variant("Por que o polvo tem três corações?") == "curiosidades"


def test_long_cover_title_fits():
    f, lines, _ = brand_clip.fit_title("palavra " * 40, 900, 900, range(170, 60, -6))
    assert all(sum(f.getlength(w) for w in ["palavra"] * len(l)) <= 900 for l in lines)
    assert len(lines) <= 6


def test_english_facts_never_reach_pt_narration():
    html = ('<table class="wikitable"><tr><th>No.</th><th>Restaurant</th><th>Location</th><th>Original air date</th></tr>'
            '<tr><th>1</th><td>Diner X</td><td>Town, OH</td><td>May 1, 2012</td></tr>'
            '<tr><td class="description">The owners argue about debt. Robert renovates the dining room.</td></tr></table>')
    ep = parse_episode_tables(html, "restaurant_impossible", "S.O.S. Restaurante", "https://en.wikipedia.org/x")[0]
    story = build_story(ep, ResearchSource(provider="wikimedia", title="w", url=ep.source_url), "Robert Irvine", "en")
    for f in story.facts:
        f.verified = True
    text = " ".join(s.narration for s in build_script(story).sections)
    assert "argue" not in text and "Diner X" in text
