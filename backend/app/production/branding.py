"""Despacho da identidade visual por estilo de canal. Canais sem `style` usam o visual padrão (visuals.py)."""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from ..channels import palette
from ..config import ROOT

IMAGES_DIR = ROOT / "imagens"
from . import brand_clip, brand_nat, visuals

NAT_SAMPLES = {
    "curiosidades": "Por que esse animal *brilha* no escuro?",
    "vida_selvagem": "O predador mais *silencioso* da floresta",
    "cinematografica": "Onde o oceano encontra o *gelo*",
}


def export_to_images(channel: dict[str, Any], folder: Path) -> Path:
    """Cópia de conveniência para o proprietário: <projeto>/imagens/<nome do canal>/ (pedido de 2026-10-30)."""
    dest = IMAGES_DIR / re.sub(r'[<>:"/\\|?*]', "", channel["name"]).strip()
    dest.mkdir(parents=True, exist_ok=True)
    for f in folder.iterdir():
        if f.suffix.lower() in (".png", ".svg") and not f.name.startswith("_"):
            shutil.copy2(f, dest / f.name)
    return dest


def render_brand_assets(channel: dict[str, Any], folder: Path) -> None:
    _render_brand_assets(channel, folder)
    if IMAGES_DIR.parent.exists() and folder.is_relative_to(ROOT):  # testes usam pastas temporárias: não exportar
        export_to_images(channel, folder)


def _render_brand_assets(channel: dict[str, Any], folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    if channel.get("style") == "nat_wild":
        brand_nat.render_avatar(folder / "avatar_800x800.png", channel)
        brand_nat.render_banner(folder / "banner_2560x1440.png", channel)
        # Modelo padrão (curiosidades) mantém o nome de arquivo existente; as outras variações ganham sufixo.
        brand_nat.render_cover(folder / "capa_modelo_1080x1920.png", (1080, 1920), NAT_SAMPLES["curiosidades"], channel, "curiosidades")
        for v in ("vida_selvagem", "cinematografica"):
            brand_nat.render_cover(folder / f"capa_modelo_{v}_1080x1920.png", (1080, 1920), NAT_SAMPLES[v], channel, v)
        brand_nat.render_logo_svg(folder / "logo.svg", channel)
        return
    if channel.get("style") == "clip_reality":
        brand_clip.render_avatar(folder / "avatar_800x800.png", channel)
        brand_clip.render_banner(folder / "banner_2560x1440.png", channel)
        brand_clip.render_cover(folder / "capa_modelo_1080x1920.png", (1080, 1920), "O dia em que a cozinha *parou*", channel)
        brand_clip.render_logo_svg(folder / "logo.svg", channel)
        return
    colors = palette(channel)
    visuals.render_avatar(folder / "avatar_800x800.png", channel["name"], colors, channel["icon"])
    visuals.render_banner(folder / "banner_2560x1440.png", channel["name"], channel["tagline"], colors, channel["icon"])
    visuals.render_cover(folder / "capa_modelo_1080x1920.png", (1080, 1920), "Título do Short aqui", channel["name"], colors, channel["icon"])


def render_channel_cover(channel: dict[str, Any], path: Path, size: tuple[int, int], title: str) -> None:
    if channel.get("style") == "clip_reality" and size[1] > size[0]:
        brand_clip.render_cover(path, size, title, channel)
    elif channel.get("style") == "nat_wild" and size[1] > size[0]:
        brand_nat.render_cover(path, size, title, channel)  # variação escolhida pelo título
    else:
        visuals.render_cover(path, size, title, channel["name"], palette(channel), channel["icon"])
