"""Estilo visual "clip_reality" (canal Clip+): reality gastronômico, tensão e entretenimento.

Formas desenhadas por código (vetoriais) e renderizadas em 2x com redução LANCZOS para bordas suaves.
O chapéu de chef é sempre branco puro; amarelo só como destaque secundário.
"""
from __future__ import annotations

import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..config import ROOT

SS = 2  # supersampling
FONT_FILES = [ROOT / "assets" / "fonts" / "anton" / "Anton-Regular.ttf", Path(r"C:\Windows\Fonts\impact.ttf"),
              Path(r"C:\Windows\Fonts\seguibl.ttf")]
WHITE = (255, 255, 255)
SAFE_BANNER = (507, 508, 2053, 931)  # área segura central 1546x423 do banner 2560x1440


def colors(channel: dict[str, Any]) -> dict[str, tuple[int, int, int]]:
    p = channel["palette"]
    return {"black": tuple(p["top"]), "wine": tuple(p["bottom"]), "red": tuple(p["accent"]), "yellow": tuple(p["accent2"])}


@lru_cache
def font(size: int) -> ImageFont.FreeTypeFont:
    for f in FONT_FILES:
        if f.exists():
            return ImageFont.truetype(str(f), size)
    return ImageFont.load_default(size=size)


def cap_height(f: ImageFont.FreeTypeFont) -> int:
    return -f.getbbox("H", anchor="ls")[1]


def mix(a: tuple[int, ...], b: tuple[int, ...], t: float) -> tuple[int, ...]:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ---------------- camadas de fundo ----------------

def diagonal_gradient(size: tuple[int, int], c1: tuple[int, ...], c2: tuple[int, ...]) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size, c1)
    d = ImageDraw.Draw(img)
    total = w + h
    for i in range(0, total, 4):
        d.line([(i, 0), (i - h, h)], fill=mix(c1, c2, i / total), width=6)
    return img


def radial_glow(img: Image.Image, center: tuple[float, float], radius: float, color: tuple[int, ...], alpha: int) -> None:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = center
    d.ellipse([cx - radius, cy - radius * 0.7, cx + radius, cy + radius * 0.7], fill=(*color, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(radius * 0.45))
    img.paste(Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB"))


def overlay(img: Image.Image, draw_fn, blur: float = 0) -> None:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer), layer.size)
    if blur:
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
    img.paste(Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB"))


def texture_lines(d: ImageDraw.ImageDraw, size: tuple[int, int], step: int, alpha: int) -> None:
    w, h = size
    for x in range(-h, w, step):
        d.line([(x, h), (x + h, 0)], fill=(255, 255, 255, alpha), width=max(1, step // 14))


def speed_lines(d: ImageDraw.ImageDraw, x: float, y: float, length: float, n: int, gap: float, color: tuple[int, ...],
                alpha: int, width: int) -> None:
    for i in range(n):
        l = length * (1 - i * 0.18)
        yy = y + i * gap
        d.line([(x, yy), (x + l * math.cos(math.radians(-20)), yy + l * math.sin(math.radians(-20)))],
               fill=(*color, alpha), width=width)


def band(d: ImageDraw.ImageDraw, x0: float, y0: float, x1: float, y1: float, slant: float, color: tuple[int, ...], alpha: int) -> None:
    """Faixa em paralelogramo (diagonal)."""
    d.polygon([(x0 + slant, y0), (x1 + slant, y0), (x1, y1), (x0, y1)], fill=(*color, alpha))


# ---------------- chapéu de chef (branco) ----------------

def hat_mask(s: int) -> Image.Image:
    m = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(m)
    for cx, cy, r in ((0.30, 0.40, 0.20), (0.50, 0.30, 0.25), (0.70, 0.40, 0.20)):
        d.ellipse([s * (cx - r), s * (cy - r), s * (cx + r), s * (cy + r)], fill=255)
    d.polygon([(s * 0.24, s * 0.44), (s * 0.76, s * 0.44), (s * 0.72, s * 0.72), (s * 0.28, s * 0.72)], fill=255)
    d.rounded_rectangle([s * 0.26, s * 0.76, s * 0.74, s * 0.92], radius=int(s * 0.04), fill=255)
    return m


def paste_hat(img: Image.Image, cx: float, cy: float, s: float, shadow: bool = True) -> None:
    s = int(s)
    m = hat_mask(s)
    x, y = int(cx - s / 2), int(cy - s / 2)
    if shadow:
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sh.paste((0, 0, 0, 170), (x + s // 40, y + s // 28), m)
        sh = sh.filter(ImageFilter.GaussianBlur(s / 30))
        img.paste(Image.alpha_composite(img.convert("RGBA"), sh).convert("RGB"))
    img.paste(WHITE, (x, y), m)


# ---------------- texto ----------------

def draw_runs(img: Image.Image, x: float, baseline: float, runs: list[tuple[str, tuple[int, ...]]], f: ImageFont.FreeTypeFont,
              depth: tuple[int, ...] | None = None, stroke: int = 0) -> float:
    """Texto multicolorido com sombra 3D (deslocada) e contorno. Retorna a largura total."""
    d = ImageDraw.Draw(img)
    off = max(2, f.size // 22)
    cx = x
    if depth:
        for text, _ in runs:
            d.text((cx + off, baseline + off), text, font=f, fill=depth, anchor="ls", stroke_width=stroke, stroke_fill=depth)
            cx += d.textlength(text, font=f)
    cx = x
    for text, color in runs:
        d.text((cx, baseline), text, font=f, fill=color, anchor="ls", stroke_width=stroke, stroke_fill=(10, 10, 14))
        cx += d.textlength(text, font=f)
    return cx - x


def runs_width(runs: list[tuple[str, tuple[int, ...]]], f: ImageFont.FreeTypeFont) -> float:
    return sum(f.getlength(t) for t, _ in runs)


def logo_runs(c: dict[str, tuple[int, ...]], text: str = "CLIP") -> list[tuple[str, tuple[int, ...]]]:
    return [(text, WHITE), ("+", c["yellow"])]


def plus_size(f: ImageFont.FreeTypeFont) -> float:
    return cap_height(f) * 0.52


def logo_width(f: ImageFont.FreeTypeFont, text: str = "CLIP") -> float:
    return f.getlength(text) + cap_height(f) * 0.06 + plus_size(f)


def draw_plus(img: Image.Image, x: float, top: float, s: float, c: dict[str, tuple[int, ...]], depth: bool = True) -> None:
    """'+' geométrico: proporcional às letras (o glifo '+' da fonte é pequeno demais para a marca)."""
    d = ImageDraw.Draw(img)
    t = s * 0.34
    def shape(dx: float, dy: float, fill: tuple[int, ...], grow: float = 0) -> None:
        cx, cy = x + s / 2 + dx, top + s / 2 + dy
        d.rectangle([cx - t / 2 - grow, cy - s / 2 - grow, cx + t / 2 + grow, cy + s / 2 + grow], fill=fill)
        d.rectangle([cx - s / 2 - grow, cy - t / 2 - grow, cx + s / 2 + grow, cy + t / 2 + grow], fill=fill)
    off = max(2, s * 0.09)
    if depth:
        shape(off, off, c["red"], grow=s * 0.03)
    shape(0, 0, (10, 10, 14), grow=s * 0.035)
    shape(0, 0, c["yellow"])


def draw_logo(img: Image.Image, x: float, baseline: float, f: ImageFont.FreeTypeFont, c: dict[str, tuple[int, ...]],
              text: str = "CLIP", stroke: int = 0, depth: bool = True) -> float:
    """Palavra branca + '+' amarelo alinhado ao topo das letras. Retorna a largura."""
    w = draw_runs(img, x, baseline, [(text, WHITE)], f, depth=c["red"] if depth else None, stroke=stroke)
    ch = cap_height(f)
    draw_plus(img, x + w + ch * 0.06, baseline - ch, plus_size(f), c, depth)
    return logo_width(f, text)


# ---------------- peças ----------------

def emblem(c: dict[str, tuple[int, ...]], size: int) -> Image.Image:
    """Logomarca circular (RGBA). Legível em tamanho de avatar: poucos elementos, C+ protagonista."""
    S = size * SS
    img = Image.new("RGB", (S, S), c["black"])
    radial_glow(img, (S / 2, S * 0.55), S * 0.62, c["wine"], 255)
    radial_glow(img, (S / 2, S * 0.62), S * 0.32, c["red"], 70)
    overlay(img, lambda d, sz: texture_lines(d, sz, int(S * 0.05), 10))
    d = ImageDraw.Draw(img)
    m, ring = S * 0.045, int(S * 0.062)
    d.ellipse([m, m, S - m, S - m], outline=c["red"], width=ring)
    d.arc([m - ring * 0.2, m - ring * 0.2, S - m + ring * 0.2, S - m + ring * 0.2], start=-58, end=-18, fill=c["yellow"], width=int(ring * 0.45))
    d.arc([m - ring * 0.2, m - ring * 0.2, S - m + ring * 0.2, S - m + ring * 0.2], start=122, end=150, fill=c["yellow"], width=int(ring * 0.45))
    paste_hat(img, S / 2, S * 0.27, S * 0.30)
    f = font(int(S * 0.50))
    draw_logo(img, (S - logo_width(f, "C")) / 2, S * 0.43 + cap_height(f), f, c, text="C", stroke=int(S * 0.008))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, S, S], fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out.resize((size, size), Image.LANCZOS)


def render_avatar(path: Path, channel: dict[str, Any], size: int = 800) -> None:
    c = colors(channel)
    em = emblem(c, size)
    bg = Image.new("RGB", (size, size), c["black"])  # YouTube recorta em círculo; cantos escuros
    bg.paste(em, (0, 0), em)
    bg.save(path, "PNG")


def render_banner(path: Path, channel: dict[str, Any]) -> None:
    c = colors(channel)
    W, H = 2560 * SS, 1440 * SS
    img = diagonal_gradient((W, H), c["black"], c["wine"])
    sx0, sy0, sx1, sy1 = (v * SS for v in SAFE_BANNER)

    def beams(d: ImageDraw.ImageDraw, sz: tuple[int, int]) -> None:
        band(d, W * 0.52, 0, W * 0.62, H, -W * 0.18, c["red"], 46)
        band(d, W * 0.66, 0, W * 0.69, H, -W * 0.18, c["red"], 30)
        band(d, W * 0.08, 0, W * 0.12, H, -W * 0.18, c["red"], 22)
    overlay(img, beams, blur=18 * SS)
    overlay(img, lambda d, sz: texture_lines(d, sz, 36 * SS, 9))
    radial_glow(img, ((sx0 + sx1) / 2, (sy0 + sy1) / 2), 900 * SS, c["red"], 60)

    def frame_bands(d: ImageDraw.ImageDraw, sz: tuple[int, int]) -> None:
        band(d, -W * 0.05, H * 0.86, W * 0.42, H, W * 0.04, c["red"], 210)
        band(d, -W * 0.05, H * 0.835, W * 0.30, H * 0.85, W * 0.03, c["yellow"], 230)
        band(d, W * 0.62, 0, W * 1.05, H * 0.13, -W * 0.04, c["red"], 210)
        speed_lines(d, W * 0.80, H * 0.62, 420 * SS, 4, 26 * SS, WHITE, 70, 6 * SS)
        speed_lines(d, W * 0.05, H * 0.40, 360 * SS, 4, 26 * SS, WHITE, 50, 6 * SS)
    overlay(img, frame_bands)

    # Composição dentro da área segura: emblema à esquerda, nome e slogan à direita.
    pad = 14 * SS
    em_size = (sy1 - sy0) - 2 * pad
    em = emblem(c, em_size // SS).resize((em_size, em_size), Image.LANCZOS)
    ex, ey = sx0 + pad, sy0 + pad
    radial_glow(img, (ex + em_size / 2, ey + em_size / 2), em_size * 0.75, c["red"], 90)
    img.paste(em, (int(ex), int(ey)), em)

    tx0, tx1 = ex + em_size + 56 * SS, sx1 - pad
    avail_w, top, bottom = tx1 - tx0, sy0 + pad, sy1 - pad
    lines = [[("RESTAURANTES EM CRISE.", WHITE)], [("HISTÓRIAS EM ", WHITE), ("60 SEGUNDOS.", c["yellow"])]]
    for scale in [x / 100 for x in range(100, 40, -4)]:
        tf, sf = font(int(250 * SS * scale)), font(int(66 * SS * scale))
        th, sh, gap, bar = cap_height(tf), cap_height(sf), int(26 * SS * scale), int(12 * SS * scale)
        total = th + gap + bar + gap + sh + int(sh * 0.45) + sh
        fits_w = logo_width(tf) <= avail_w and all(runs_width(l, sf) <= avail_w for l in lines)
        if fits_w and total <= bottom - top:
            break
    y = top + ((bottom - top) - total) / 2
    draw_logo(img, tx0, y + th, tf, c, stroke=3 * SS)
    y += th + gap
    d = ImageDraw.Draw(img)
    d.polygon([(tx0 + bar, y), (tx1, y), (tx1 - bar, y + bar), (tx0, y + bar)], fill=c["red"])
    d.polygon([(tx0 + bar, y), (tx0 + avail_w * 0.18, y), (tx0 + avail_w * 0.18 - bar, y + bar), (tx0, y + bar)], fill=c["yellow"])
    y += bar + gap
    for i, line in enumerate(lines):
        draw_runs(img, tx0, y + sh, line, sf, depth=(0, 0, 0))
        y += sh + (int(sh * 0.45) if i == 0 else 0)
    img.resize((2560, 1440), Image.LANCZOS).save(path, "PNG")


def _highlight(words: list[str]) -> set[int]:
    """Palavras em *asteriscos* ou com números viram amarelo; senão a palavra mais longa (≥ 5 letras)."""
    marked = {i for i, w in enumerate(words) if w.startswith("*") or w.endswith("*")}
    if marked:
        return marked
    digits = {i for i, w in enumerate(words) if any(ch.isdigit() for ch in w)}
    if digits:
        return digits
    longest = max(range(len(words)), key=lambda i: len(words[i])) if words else -1
    return {longest} if longest >= 0 and len(words[longest]) >= 5 else set()


def fit_title(title: str, max_w: float, max_h: float, sizes: range) -> tuple[ImageFont.FreeTypeFont, list[list[int]], list[str]]:
    words = re.sub(r"\s+", " ", title.upper()).strip().split(" ")
    clean = [w.strip("*") for w in words]
    for size in sizes:
        f = font(size)
        space = f.getlength(" ")
        lines, cur, cur_w = [], [], 0.0
        ok = True
        for i, w in enumerate(clean):
            ww = f.getlength(w)
            if ww > max_w:
                ok = False
                break
            if cur and cur_w + space + ww > max_w:
                lines.append(cur)
                cur, cur_w = [], 0.0
            cur_w = cur_w + (space if cur else 0) + ww
            cur.append(i)
        if not ok:
            continue
        if cur:
            lines.append(cur)
        if len(lines) * cap_height(f) * 1.32 <= max_h and len(lines) <= 6:
            return f, lines, words
    # Último recurso: menor fonte e reticências, sem cortar letras.
    f = font(sizes[-1])
    return fit_title(" ".join(clean[: max(1, len(clean) - 1)]) + "…", max_w, max_h, range(sizes[-1], sizes[-1] - 1, -1)) \
        if len(clean) > 1 else (f, [[0]], words)


def render_cover(path: Path, size: tuple[int, int], title: str, channel: dict[str, Any]) -> None:
    c = colors(channel)
    w, h = size
    W, H = w * SS, h * SS
    img = Image.new("RGB", (W, H), c["black"])
    d0 = ImageDraw.Draw(img)
    for y in range(0, H, 4):
        d0.rectangle([0, y, W, y + 4], fill=mix(c["black"], c["wine"], (y / H) ** 1.4))
    radial_glow(img, (W * 0.5, H * 0.5), W * 0.75, c["red"], 75)

    def deco(d: ImageDraw.ImageDraw, sz: tuple[int, int]) -> None:
        texture_lines(d, sz, 40 * SS, 9)
        band(d, W * 0.48, 0, W * 1.1, H * 0.085, -W * 0.06, c["red"], 235)
        band(d, W * 0.62, H * 0.092, W * 1.1, H * 0.102, -W * 0.06, c["yellow"], 240)
        band(d, -W * 0.1, H * 0.905, W * 0.55, H, W * 0.06, c["red"], 235)
        band(d, -W * 0.1, H * 0.888, W * 0.38, H * 0.897, W * 0.06, c["yellow"], 240)
        speed_lines(d, W * 0.70, H * 0.30, 300 * SS, 3, 24 * SS, WHITE, 60, 5 * SS)
        speed_lines(d, W * 0.04, H * 0.78, 300 * SS, 3, 24 * SS, WHITE, 45, 5 * SS)
    overlay(img, deco)

    # Topo: marca pequena com chapéu branco.
    bf = font(int(96 * SS))
    hat_s = 130 * SS
    bw = hat_s * 0.8 + 22 * SS + logo_width(bf)
    bx, by = (W - bw) / 2, H * 0.165  # abaixo das faixas do topo
    paste_hat(img, bx + hat_s * 0.4, by, hat_s)
    draw_logo(img, bx + hat_s * 0.8 + 22 * SS, by + cap_height(bf) / 2, bf, c, stroke=2 * SS)

    # Centro: título com ajuste automático (sem cortes).
    area = (70 * SS, int(H * 0.25), W - 70 * SS, int(H * 0.80))
    max_w, max_h = area[2] - area[0], area[3] - area[1]
    f, lines, words = fit_title(title, max_w * 0.94, max_h * 0.9, range(170 * SS, 60 * SS, -6 * SS))
    hl = _highlight(words)
    ch = cap_height(f)
    lh = int(ch * 1.32)
    block_h = lh * len(lines) - (lh - ch)
    panel_pad = 34 * SS

    def panel(d: ImageDraw.ImageDraw, sz: tuple[int, int]) -> None:
        y0 = area[1] + (max_h - block_h) / 2 - panel_pad
        y1 = y0 + block_h + 2 * panel_pad
        band(d, area[0] - 20 * SS, y0, area[2] + 20 * SS, y1, 40 * SS, (0, 0, 0), 120)
        d.rectangle([area[0] - 20 * SS + 40 * SS, y0, area[0] - 6 * SS + 40 * SS, y0 + (y1 - y0) * 0.55], fill=(*c["red"], 255))
    overlay(img, panel)
    y = area[1] + (max_h - block_h) / 2
    space = f.getlength(" ")
    for line in lines:
        runs: list[tuple[str, tuple[int, ...]]] = []
        for k, i in enumerate(line):
            runs.append((words[i].strip("*") + (" " if k < len(line) - 1 else ""), c["yellow"] if i in hl else WHITE))
        lw = runs_width(runs, f)
        draw_runs(img, (W - lw) / 2, y + ch, runs, f, depth=c["red"], stroke=4 * SS)
        y += lh
    _ = space

    # Base: assinatura.
    sf = font(int(46 * SS))
    rest = [("  ·  RESTAURANTES EM CRISE", WHITE)]
    sw = logo_width(sf) + runs_width(rest, sf)
    sx = (W - sw) / 2
    lw = draw_logo(img, sx, H * 0.865, sf, c, depth=False)
    draw_runs(img, sx + lw, H * 0.865, rest, sf, depth=(0, 0, 0))
    img.resize(size, Image.LANCZOS).save(path, "PNG")


def render_logo_svg(path: Path, channel: dict[str, Any]) -> None:
    """Versão vetorial da logomarca (fonte Anton, com alternativas, no visualizador)."""
    c = {k: "#%02X%02X%02X" % v for k, v in colors(channel).items()}
    path.write_text(f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" width="800" height="800">
  <defs>
    <radialGradient id="bg" cx="50%" cy="56%" r="60%"><stop offset="0" stop-color="{c['wine']}"/><stop offset="1" stop-color="{c['black']}"/></radialGradient>
    <filter id="sh"><feDropShadow dx="6" dy="9" stdDeviation="8" flood-color="#000" flood-opacity="0.65"/></filter>
  </defs>
  <circle cx="400" cy="400" r="400" fill="url(#bg)"/>
  <circle cx="400" cy="400" r="337" fill="none" stroke="{c['red']}" stroke-width="50"/>
  <path d="M 668 226 A 375 375 0 0 1 760 340" fill="none" stroke="{c['yellow']}" stroke-width="22"/>
  <g filter="url(#sh)" fill="#FFFFFF" transform="translate(280 96) scale(2.4)">
    <circle cx="30" cy="40" r="20"/><circle cx="50" cy="30" r="25"/><circle cx="70" cy="40" r="20"/>
    <polygon points="24,44 76,44 72,72 28,72"/><rect x="26" y="76" width="48" height="16" rx="4"/>
  </g>
  <g font-family="Anton, Impact, 'Arial Black', sans-serif" font-size="400" text-anchor="middle">
    <text x="412" y="702" fill="{c['red']}">C<tspan fill="{c['red']}">+</tspan></text>
    <text x="400" y="690" fill="#FFFFFF" stroke="#0A0A0E" stroke-width="6">C<tspan fill="{c['yellow']}">+</tspan></text>
  </g>
</svg>
""", encoding="utf-8")
