"""Estilo visual "nat_wild" (canal Clip+ Nat): documentário moderno + Shorts virais.

Símbolo próprio: folha-bússola (folha cuja nervura é uma seta) dentro de um anel de exploração aberto.
Linguagem gráfica: curvas de nível (relevo), silhuetas de cordilheiras e luz cinematográfica.
Reaproveita tipografia, texto e camadas do brand_clip (sem duplicar código).
"""
from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .brand_clip import (SAFE_BANNER, SS, WHITE, band, cap_height, diagonal_gradient, draw_plus, draw_runs, fit_title, font,
                         mix, overlay, plus_size, radial_glow, runs_width, speed_lines, _highlight)

VARIANTS = {
    "vida_selvagem": "VIDA SELVAGEM",
    "curiosidades": "CURIOSIDADE",
    "cinematografica": "NATUREZA",
}
WILD_WORDS = ("predador", "tubarão", "leão", "onça", "veneno", "cobra", "serpente", "crocodilo", "lobo", "caça", "ataque",
              "sobreviv", "raro", "perigos", "mortal", "garras")
CINE_WORDS = ("floresta", "oceano", "mar ", "montanha", "vulcão", "aurora", "deserto", "rio ", "cachoeira", "geleira",
              "paisagem", "céu", "tempestade", "recife", "biodiversidade")


def colors(channel: dict[str, Any]) -> dict[str, tuple[int, ...]]:
    p = channel["palette"]
    top, bottom, green, sky = (tuple(p[k]) for k in ("top", "bottom", "accent", "accent2"))
    return {"deep": mix(top, (0, 0, 0), 0.25), "top": top, "forest": bottom, "green": green, "sky": sky,
            "green_light": mix(green, WHITE, 0.35), "green_dark": mix(green, bottom, 0.55),
            # chaves usadas pelos helpers compartilhados (draw_plus): "+" verde com profundidade verde-escura
            "yellow": green, "red": mix(bottom, (0, 0, 0), 0.3)}


def choose_variant(title: str) -> str:
    low = f" {title.lower()} "
    if any(w in low for w in WILD_WORDS):
        return "vida_selvagem"
    if any(w in low for w in CINE_WORDS):
        return "cinematografica"
    return "curiosidades"


# ---------------- linguagem gráfica ----------------

def contours(d: ImageDraw.ImageDraw, cx: float, cy: float, n: int, r0: float, step: float, color: tuple[int, ...],
             alpha: int, width: int, seed: int = 7) -> None:
    """Curvas de nível orgânicas (relevo topográfico)."""
    rnd = random.Random(seed)
    k1, k2, p1, p2 = rnd.randint(3, 5), rnd.randint(6, 9), rnd.random() * 6, rnd.random() * 6
    for i in range(n):
        r = r0 + i * step
        pts = []
        for a in range(0, 361, 3):
            t = math.radians(a)
            rr = r * (1 + 0.07 * math.sin(k1 * t + p1 + i * 0.25) + 0.035 * math.sin(k2 * t + p2))
            pts.append((cx + rr * math.cos(t), cy + rr * 0.78 * math.sin(t)))
        d.line(pts, fill=(*color, alpha), width=width)


def ridge(d: ImageDraw.ImageDraw, w: float, h: float, base: float, amp: float, color: tuple[int, ...], alpha: int, seed: int) -> None:
    """Silhueta de cordilheira (camada de profundidade)."""
    rnd = random.Random(seed)
    f1, f2, f3 = rnd.uniform(1.5, 2.5), rnd.uniform(4, 6), rnd.uniform(9, 13)
    p = [rnd.random() * 6 for _ in range(3)]
    pts = [(0, h)]
    for i in range(0, 201):
        x = w * i / 200
        t = i / 200 * math.pi
        y = base - amp * (0.55 * abs(math.sin(f1 * t + p[0])) + 0.3 * abs(math.sin(f2 * t + p[1])) + 0.15 * abs(math.sin(f3 * t + p[2])))
        pts.append((x, y))
    pts.append((w, h))
    d.polygon(pts, fill=(*color, alpha))


def leaf_points(cx: float, cy: float, s: float, angle: float) -> list[tuple[float, float]]:
    pts_l, pts_r = [], []
    for i in range(0, 41):
        t = i / 40
        along = (t - 0.5) * s
        half = 0.30 * s * math.sin(math.pi * t) ** 0.85 * (1 - 0.25 * t)
        pts_l.append((along, -half))
        pts_r.append((along, half))
    raw = pts_l + pts_r[::-1]
    ca, sa = math.cos(angle), math.sin(angle)
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in raw]


def draw_symbol(img: Image.Image, cx: float, cy: float, s: float, c: dict[str, tuple[int, ...]], ring: bool = True) -> None:
    """Folha-bússola: folha verde, nervura branca em forma de seta (descoberta + movimento), anel aberto."""
    d = ImageDraw.Draw(img)
    ang = math.radians(-40)
    if ring:
        r, wdt = s * 0.62, max(3, int(s * 0.07))
        d.arc([cx - r, cy - r, cx + r, cy + r], start=-20, end=250, fill=c["green"], width=wdt)
        d.arc([cx - r, cy - r, cx + r, cy + r], start=262, end=318, fill=c["sky"], width=wdt)
    # sombra
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).polygon(leaf_points(cx + s * 0.03, cy + s * 0.05, s, ang), fill=(0, 0, 0, 150))
    img.paste(Image.alpha_composite(img.convert("RGBA"), sh.filter(ImageFilter.GaussianBlur(s * 0.04))).convert("RGB"))
    d = ImageDraw.Draw(img)
    pts = leaf_points(cx, cy, s, ang)
    d.polygon(pts, fill=c["green"])
    half = len(pts) // 2
    d.polygon([pts[0], *pts[half:]], fill=c["green_dark"])  # metade sombreada = volume
    # nervura-seta
    ca, sa = math.cos(ang), math.sin(ang)
    p = lambda a, b: (cx + a * ca - b * sa, cy + a * sa + b * ca)  # noqa: E731
    lw = max(3, int(s * 0.055))
    d.line([p(-0.62 * s, 0), p(0.36 * s, 0)], fill=WHITE, width=lw)
    d.polygon([p(0.56 * s, 0), p(0.30 * s, -0.14 * s), p(0.30 * s, 0.14 * s)], fill=WHITE)
    for k in (-0.22, 0.02):
        d.line([p(k * s, 0), p((k + 0.16) * s, -0.15 * s)], fill=WHITE, width=max(2, lw // 2))
        d.line([p(k * s, 0), p((k + 0.16) * s, 0.15 * s)], fill=WHITE, width=max(2, lw // 2))


def wordmark_width(f, c) -> float:
    ch = cap_height(f)
    return f.getlength("CLIP") + ch * 0.06 + plus_size(f) + ch * 0.22 + f.getlength("NAT")


def draw_wordmark(img: Image.Image, x: float, baseline: float, f, c: dict[str, tuple[int, ...]], stroke: int = 0, depth: bool = True) -> float:
    """CLIP (branco) + '+' verde + NAT (verde-claro)."""
    dep = c["red"] if depth else None
    w = draw_runs(img, x, baseline, [("CLIP", WHITE)], f, depth=dep, stroke=stroke)
    ch = cap_height(f)
    draw_plus(img, x + w + ch * 0.06, baseline - ch, plus_size(f), c, depth)
    nx = x + w + ch * 0.06 + plus_size(f) + ch * 0.22
    draw_runs(img, nx, baseline, [("NAT", c["green_light"])], f, depth=dep, stroke=stroke)
    return wordmark_width(f, c)


def scene(size: tuple[int, int], c: dict[str, tuple[int, ...]], seed: int = 3) -> Image.Image:
    """Cena ilustrada original (céu, luz, cordilheiras em camadas, névoa) usada quando não há frame licenciado."""
    w, h = size
    img = Image.new("RGB", size, c["deep"])
    d = ImageDraw.Draw(img)
    for y in range(0, h, 4):
        t = y / h
        d.rectangle([0, y, w, y + 4], fill=mix(mix(c["sky"], c["deep"], 0.72), c["forest"], t ** 0.8))
    radial_glow(img, (w * 0.68, h * 0.30), w * 0.55, mix(c["sky"], WHITE, 0.3), 120)
    radial_glow(img, (w * 0.68, h * 0.30), w * 0.18, WHITE, 140)

    def layers(dd: ImageDraw.ImageDraw, sz: tuple[int, int]) -> None:
        ridge(dd, w, h, h * 0.52, h * 0.16, mix(c["forest"], c["sky"], 0.35), 255, seed)
        ridge(dd, w, h, h * 0.62, h * 0.14, mix(c["forest"], c["green"], 0.25), 255, seed + 1)
        ridge(dd, w, h, h * 0.74, h * 0.12, c["forest"], 255, seed + 2)
        ridge(dd, w, h, h * 0.86, h * 0.10, c["deep"], 255, seed + 3)
    overlay(img, layers)
    overlay(img, lambda dd, sz: [dd.rectangle([0, h * (0.55 + 0.1 * i), w, h * (0.58 + 0.1 * i)], fill=(255, 255, 255, 18)) for i in range(3)],
            blur=h * 0.02)
    return img


def cover_fit(src: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(src.convert("RGB"), size, Image.LANCZOS, centering=(0.5, 0.45))


# ---------------- peças ----------------

def render_avatar(path: Path, channel: dict[str, Any], size: int = 800) -> None:
    c = colors(channel)
    S = size * SS
    img = Image.new("RGB", (S, S), c["deep"])
    radial_glow(img, (S / 2, S * 0.46), S * 0.6, c["forest"], 255)
    radial_glow(img, (S * 0.66, S * 0.3), S * 0.3, c["sky"], 45)
    overlay(img, lambda d, sz: contours(d, S / 2, S * 0.45, 9, S * 0.12, S * 0.055, c["green"], 26, max(2, S // 400)))
    draw_symbol(img, S / 2, S * 0.43, S * 0.56, c)
    f = font(int(S * 0.15))
    tw = f.getlength("NAT")
    pad = S * 0.035
    d = ImageDraw.Draw(img)
    y0 = S * 0.74
    d.rounded_rectangle([(S - tw) / 2 - pad * 1.6, y0 - pad, (S + tw) / 2 + pad * 1.6, y0 + cap_height(f) + pad], radius=int(S * 0.04),
                        fill=c["green"])
    d.text(((S - tw) / 2, y0 + cap_height(f)), "NAT", font=f, fill=c["deep"], anchor="ls")
    img.resize((size, size), Image.LANCZOS).save(path, "PNG")


def render_banner(path: Path, channel: dict[str, Any]) -> None:
    c = colors(channel)
    W, H = 2560 * SS, 1440 * SS
    img = diagonal_gradient((W, H), c["deep"], c["forest"])
    radial_glow(img, (W * 0.25, H * 0.2), W * 0.35, c["sky"], 55)
    radial_glow(img, (W * 0.5, H * 0.5), W * 0.38, c["green"], 45)

    def bg(d: ImageDraw.ImageDraw, sz: tuple[int, int]) -> None:
        contours(d, W * 0.86, H * 0.38, 12, 90 * SS, 46 * SS, c["green"], 34, 3 * SS, seed=11)
        contours(d, W * 0.12, H * 0.70, 10, 80 * SS, 46 * SS, c["sky"], 26, 3 * SS, seed=5)
        ridge(d, W, H, H * 0.93, H * 0.12, c["deep"], 230, 21)
        speed_lines(d, W * 0.74, H * 0.66, 380 * SS, 3, 26 * SS, c["green_light"], 70, 5 * SS)
        speed_lines(d, W * 0.08, H * 0.34, 320 * SS, 3, 26 * SS, c["sky"], 55, 5 * SS)
    overlay(img, bg)
    overlay(img, lambda d, sz: [d.polygon(leaf_points(x, y, s, a), fill=(*c["deep"], 200)) for x, y, s, a in
                                ((W * 0.04, H * 0.18, 520 * SS, 0.9), (W * 0.97, H * 0.86, 600 * SS, -2.3), (W * 0.93, H * 0.08, 380 * SS, 2.2))],
            blur=6 * SS)

    sx0, sy0, sx1, sy1 = (v * SS for v in SAFE_BANNER)
    pad = 14 * SS
    sym = (sy1 - sy0) - 2 * pad
    radial_glow(img, (sx0 + pad + sym / 2, sy0 + pad + sym / 2), sym * 0.7, c["green"], 70)
    draw_symbol(img, sx0 + pad + sym / 2, sy0 + pad + sym / 2, sym * 0.62, c)
    tx0, tx1 = sx0 + pad + sym + 50 * SS, sx1 - pad
    avail_w, top, bottom = tx1 - tx0, sy0 + pad, sy1 - pad
    tagline = channel["tagline"]
    words = tagline.split()
    hl = {i for i, w in enumerate(words) if w.lower().strip(".,") in ("estranha", "incríveis", "surpreendente")}
    for scale in [x / 100 for x in range(100, 40, -4)]:
        tf, sf = font(int(210 * SS * scale)), font(int(62 * SS * scale))
        th, sh, gap = cap_height(tf), cap_height(sf), int(30 * SS * scale)
        runs = [(w + " ", c["green_light"] if i in hl else WHITE) for i, w in enumerate(words)]
        total = th + gap + 8 * SS + gap + sh
        if wordmark_width(tf, c) <= avail_w and runs_width(runs, sf) <= avail_w and total <= bottom - top:
            break
    y = top + ((bottom - top) - total) / 2
    draw_wordmark(img, tx0, y + th, tf, c, stroke=3 * SS)
    y += th + gap
    d = ImageDraw.Draw(img)
    # traço orgânico: linha fina com ponto (trilha de exploração)
    d.line([(tx0, y + 4 * SS), (tx1 - 40 * SS, y + 4 * SS)], fill=c["green"], width=6 * SS)
    d.ellipse([tx1 - 34 * SS, y - 8 * SS, tx1 - 10 * SS, y + 16 * SS], fill=c["sky"])
    y += 8 * SS + gap
    draw_runs(img, tx0, y + sh, runs, sf, depth=(0, 0, 0))
    img.resize((2560, 1440), Image.LANCZOS).save(path, "PNG")


def render_cover(path: Path, size: tuple[int, int], title: str, channel: dict[str, Any], variant: str | None = None,
                 image: Path | None = None) -> None:
    """Capa de Short. `image` (frame licenciado ou próprio) é o protagonista; sem ele, usa cena ilustrada original."""
    c = colors(channel)
    variant = variant or choose_variant(title)
    w, h = size
    W, H = w * SS, h * SS
    base = cover_fit(Image.open(image), (W, H)) if image and Path(image).exists() else scene((W, H), c, seed=len(title) % 9 + 2)
    img = base.copy()

    # Gradientes escuros só onde há texto, para não cobrir a imagem.
    def shade(d: ImageDraw.ImageDraw, sz: tuple[int, int]) -> None:
        top_h = H * 0.22
        for i in range(int(top_h), 0, -6):
            d.rectangle([0, top_h - i, W, top_h - i + 6], fill=(*c["deep"], int(200 * (i / top_h))))
        start = H * (0.50 if variant != "cinematografica" else 0.62)
        for y in range(int(start), H, 6):
            t = (y - start) / (H - start)
            d.rectangle([0, y, W, y + 6], fill=(*c["deep"], int(235 * min(1, t * 1.25))))
    overlay(img, shade)

    def deco(d: ImageDraw.ImageDraw, sz: tuple[int, int]) -> None:
        if variant == "vida_selvagem":
            band(d, -W * 0.1, H * 0.535, W * 0.62, H * 0.548, W * 0.05, c["green"], 255)
            band(d, W * 0.66, H * 0.535, W * 1.1, H * 0.548, W * 0.05, c["sky"], 230)
            speed_lines(d, W * 0.66, H * 0.34, 300 * SS, 3, 24 * SS, WHITE, 80, 5 * SS)
        elif variant == "curiosidades":
            contours(d, W * 0.85, H * 0.36, 6, 50 * SS, 34 * SS, c["green_light"], 70, 3 * SS, seed=4)
            speed_lines(d, W * 0.05, H * 0.47, 280 * SS, 3, 22 * SS, c["sky"], 120, 5 * SS)
        else:  # cinematográfica: barras discretas, linha fina
            d.rectangle([0, 0, W, H * 0.035], fill=(0, 0, 0, 200))
            d.rectangle([0, H * 0.965, W, H], fill=(0, 0, 0, 200))
    overlay(img, deco)

    # Topo: marca pequena.
    bf = font(int(68 * SS))
    sym = 110 * SS
    bw = sym + 16 * SS + wordmark_width(bf, c)
    bx, by = (W - bw) / 2, H * 0.085
    draw_symbol(img, bx + sym / 2, by, sym * 0.62, c, ring=True)
    draw_wordmark(img, bx + sym + 16 * SS, by + cap_height(bf) / 2, bf, c, stroke=2 * SS)

    # Etiqueta da variação.
    tag = VARIANTS.get(variant, "CURIOSIDADE")
    tf_tag = font(int(40 * SS))
    tagw = tf_tag.getlength(tag)
    ty = H * (0.555 if variant != "cinematografica" else 0.66)
    d = ImageDraw.Draw(img)
    tag_color = c["sky"] if variant == "curiosidades" else c["green"]
    d.rounded_rectangle([(W - tagw) / 2 - 22 * SS, ty, (W + tagw) / 2 + 22 * SS, ty + cap_height(tf_tag) + 26 * SS], radius=12 * SS, fill=tag_color)
    d.text(((W - tagw) / 2, ty + 13 * SS + cap_height(tf_tag)), tag, font=tf_tag, fill=c["deep"], anchor="ls")

    # Título: ajuste automático, sem cortes.
    if variant == "cinematografica":
        area, sizes = (80 * SS, int(H * 0.70), W - 80 * SS, int(H * 0.90)), range(118 * SS, 56 * SS, -4 * SS)
    else:
        area, sizes = (60 * SS, int(H * 0.61), W - 60 * SS, int(H * 0.91)), range(150 * SS, 60 * SS, -6 * SS)
    max_w, max_h = area[2] - area[0], area[3] - area[1]
    f, lines, words = fit_title(title, max_w, max_h, sizes)
    hl = _highlight(words)
    ch = cap_height(f)
    lh = int(ch * 1.3)
    block_h = lh * len(lines) - (lh - ch)
    y = area[1] + (max_h - block_h) / 2
    for line in lines:
        runs = [(words[i].strip("*") + (" " if k < len(line) - 1 else ""), c["green_light"] if i in hl else WHITE)
                for k, i in enumerate(line)]
        lw = runs_width(runs, f)
        draw_runs(img, (W - lw) / 2, y + ch, runs, f, depth=(0, 0, 0), stroke=3 * SS)
        y += lh
    if variant == "cinematografica":
        ImageDraw.Draw(img).line([(W * 0.4, y + 10 * SS), (W * 0.6, y + 10 * SS)], fill=c["green"], width=5 * SS)

    # Base: assinatura discreta.
    sf = font(int(36 * SS))
    sig = "DESCUBRA O LADO SURPREENDENTE DO PLANETA"
    draw_runs(img, (W - sf.getlength(sig)) / 2, H * 0.955, [(sig, mix(WHITE, c["green"], 0.25))], sf, depth=(0, 0, 0))
    img.resize(size, Image.LANCZOS).save(path, "PNG")


def render_logo_svg(path: Path, channel: dict[str, Any]) -> None:
    """Versão vetorial do símbolo folha-bússola com o nome."""
    c = {k: "#%02X%02X%02X" % v[:3] for k, v in colors(channel).items()}
    path.write_text(f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" width="800" height="800">
  <defs><radialGradient id="bg" cx="50%" cy="46%" r="62%"><stop offset="0" stop-color="{c['forest']}"/><stop offset="1" stop-color="{c['deep']}"/></radialGradient></defs>
  <rect width="800" height="800" fill="url(#bg)"/>
  <path d="M 610 270 A 248 248 0 1 1 520 132" fill="none" stroke="{c['green']}" stroke-width="31"/>
  <path d="M 545 145 A 248 248 0 0 1 600 205" fill="none" stroke="{c['sky']}" stroke-width="31"/>
  <g transform="translate(400 344) rotate(-40)">
    <path d="M -224 0 C -150 -120, 90 -125, 224 0 C 90 125, -150 120, -224 0 Z" fill="{c['green']}"/>
    <path d="M -224 0 C -150 120, 90 125, 224 0 Z" fill="{c['green_dark']}"/>
    <line x1="-280" y1="0" x2="160" y2="0" stroke="#FFFFFF" stroke-width="25"/>
    <polygon points="252,0 135,-63 135,63" fill="#FFFFFF"/>
  </g>
  <rect x="300" y="568" width="200" height="110" rx="28" fill="{c['green']}"/>
  <text x="400" y="655" text-anchor="middle" font-family="Anton, Impact, 'Arial Black', sans-serif" font-size="96" fill="{c['deep']}">NAT</text>
</svg>
""", encoding="utf-8")
