"""Prepara os recursos locais do GeoZoom (rodar com o Python do backend: backend/.venv).

1. Tiles geográficos (EPSG:4326) da NASA Blue Marble (domínio público) em data/tiles/{z}/{x}/{y}.jpg,
   512x512, y=0 no norte, níveis 0..4 (nível 4 = 16384 px de largura).
2. Céu estrelado original (obra própria, gerado aleatoriamente) em data/stars/{px,nx,py,ny,pz,nz}.jpg.
3. Índice compacto de países (Natural Earth, domínio público): data/countries.json com nomes pt/en,
   centro e caixa do MAIOR polígono (evita territórios ultramarinos esticarem a caixa).
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

Image.MAX_IMAGE_PIXELS = None
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TILE = 512
MAX_LEVEL = 4


def make_tiles(src: Path) -> None:
    img = Image.open(src)
    img.draft("RGB", (12000, 6000))  # decodificação JPEG reduzida: ~216 MB em vez de ~860 MB
    img = img.convert("RGB")
    print("Blue Marble carregada em", img.size)
    for z in range(MAX_LEVEL + 1):
        cols, rows = 2 ** (z + 1), 2 ** z
        level = img.resize((cols * TILE, rows * TILE), Image.LANCZOS)
        for x in range(cols):
            folder = DATA / "tiles" / str(z) / str(x)
            folder.mkdir(parents=True, exist_ok=True)
            for y in range(rows):
                level.crop((x * TILE, y * TILE, (x + 1) * TILE, (y + 1) * TILE)).save(folder / f"{y}.jpg", quality=88)
        print(f"nível {z}: {cols}x{rows} tiles")


def make_stars(size: int = 2048, seed: int = 7) -> None:
    folder = DATA / "stars"
    folder.mkdir(parents=True, exist_ok=True)
    for i, face in enumerate(("px", "nx", "py", "ny", "pz", "nz")):
        rnd = random.Random(seed + i)
        img = Image.new("RGB", (size, size), (2, 3, 8))
        d = ImageDraw.Draw(img)
        for _ in range(1400):
            x, y = rnd.random() * size, rnd.random() * size
            b = int(110 + 145 * rnd.random() ** 3)
            tint = rnd.choice(((b, b, b), (b, b, min(255, b + 25)), (min(255, b + 20), b, b - 10)))
            r = 0.6 if rnd.random() < 0.92 else 1.4
            d.ellipse([x - r, y - r, x + r, y + r], fill=tint)
        img = img.filter(ImageFilter.GaussianBlur(0.6))
        img.save(folder / f"{face}.jpg", quality=92)
    print("céu estrelado gerado")


def ring_area(ring: list[list[float]]) -> float:
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1]))) / 2


def make_countries(src: Path) -> None:
    gj = json.loads(src.read_text(encoding="utf-8"))
    out = []
    for f in gj["features"]:
        p, g = f["properties"], f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        main = max(polys, key=lambda poly: ring_area(poly[0]))[0]
        main_area = ring_area(main)
        mx0, my0 = min(c[0] for c in main), min(c[1] for c in main)
        mx1, my1 = max(c[0] for c in main), max(c[1] for c in main)
        # Inclui ilhas relevantes perto do território principal (ex.: Tasmânia), não territórios ultramarinos distantes.
        rings = [main]
        for poly in polys:
            ring = poly[0]
            if ring is main or ring_area(ring) < 0.005 * main_area:
                continue
            cx, cy = sum(c[0] for c in ring) / len(ring), sum(c[1] for c in ring) / len(ring)
            if mx0 - 8 <= cx <= mx1 + 8 and my0 - 8 <= cy <= my1 + 8:
                rings.append(ring)
        lons, lats = [c[0] for r in rings for c in r], [c[1] for r in rings for c in r]
        out.append({
            "name_pt": p.get("NAME_PT") or p.get("NAME"), "name_en": p.get("NAME_EN") or p.get("NAME"),
            "iso_a3": p.get("ISO_A3") if p.get("ISO_A3") not in (None, "-99") else p.get("ADM0_A3"),
            "bbox": [round(min(lons), 3), round(min(lats), 3), round(max(lons), 3), round(max(lats), 3)],
        })
    (DATA / "countries.json").write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(out)} países indexados")


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    if step in ("all", "tiles"):
        make_tiles(DATA / "source" / "bluemarble_24000.jpg")
    if step in ("all", "stars"):
        make_stars()
    if step in ("all", "countries"):
        make_countries(DATA / "source" / "ne_50m_admin_0_countries.geojson")
