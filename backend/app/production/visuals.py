"""Imagens geradas localmente com Pillow (obra própria): quadros do vídeo, capas e identidade dos canais."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_CANDIDATES = [r"C:\Windows\Fonts\seguibl.ttf", r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf"]
DEFAULT_COLORS = ((24, 26, 33), (58, 18, 24), (239, 68, 68), (250, 204, 21))
RGB = tuple[int, ...]


@lru_cache
def font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def variant(colors: tuple[RGB, ...], idx: int) -> tuple[RGB, RGB, RGB]:
    """Variações da paleta do canal para alternar o visual a cada legenda sem perder a identidade."""
    top, bottom, a1, a2 = colors
    return [(top, bottom, a1), (top, bottom, a2), (bottom, top, a1), (bottom, top, a2)][idx % 4]


def _wrap(draw: ImageDraw.ImageDraw, text: str, f, max_w: int) -> list[str]:
    lines, cur = [], ""
    for w in text.split():
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=f) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def gradient(size: tuple[int, int], top: RGB, bottom: RGB) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size, top)
    d = ImageDraw.Draw(img)
    for y in range(0, h, 4):
        t = y / h
        d.rectangle([0, y, w, y + 4], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return img


def draw_icon(d: ImageDraw.ImageDraw, kind: str, cx: float, cy: float, s: float, color: RGB, width: int = 0) -> None:
    """Ícones geométricos originais: chapéu de chef ou folha."""
    if kind == "chef":
        r = s * 0.22
        for dx in (-r * 1.1, 0, r * 1.1):
            d.ellipse([cx + dx - r, cy - s * 0.32 - r, cx + dx + r, cy - s * 0.32 + r], fill=color)
        d.rounded_rectangle([cx - s * 0.36, cy - s * 0.32, cx + s * 0.36, cy + s * 0.22], radius=int(s * 0.05), fill=color)
        d.rectangle([cx - s * 0.36, cy + s * 0.08, cx + s * 0.36, cy + s * 0.12], fill=(0, 0, 0))
    else:  # folha
        pts = [(cx, cy - s * 0.5), (cx + s * 0.32, cy - s * 0.2), (cx + s * 0.3, cy + s * 0.18), (cx, cy + s * 0.42),
               (cx - s * 0.3, cy + s * 0.18), (cx - s * 0.32, cy - s * 0.2)]
        d.polygon(pts, fill=color)
        d.line([(cx, cy - s * 0.4), (cx, cy + s * 0.5)], fill=(0, 0, 0), width=max(3, int(s * 0.03)))
        for k in (-0.2, 0.0, 0.2):
            d.line([(cx, cy + s * k), (cx + s * 0.18, cy + s * (k - 0.14))], fill=(0, 0, 0), width=max(2, int(s * 0.02)))
            d.line([(cx, cy + s * k), (cx - s * 0.18, cy + s * (k - 0.14))], fill=(0, 0, 0), width=max(2, int(s * 0.02)))


def render_frame(path: Path, size: tuple[int, int], caption: str, label: str, palette_idx: int,
                 progress: float, footer: str, colors: tuple[RGB, ...] = DEFAULT_COLORS, icon: str = "chef",
                 icon_color: RGB | None = None) -> None:
    w, h = size
    top, bottom, accent = variant(colors, palette_idx)
    img = gradient(size, top, bottom)
    d = ImageDraw.Draw(img)
    r = int(min(w, h) * 0.35)
    d.ellipse([w - r, -r // 2, w + r // 2, r], outline=accent, width=6)
    draw_icon(d, icon, w * 0.12, h * 0.9 if h > w else h * 0.85, min(w, h) * 0.07, icon_color or accent)

    vertical = h > w
    if label:
        lf = font(int(w * (0.05 if vertical else 0.028)))
        lw = d.textlength(label, font=lf)
        pad = 24
        y0 = int(h * (0.12 if vertical else 0.08))
        d.rounded_rectangle([(w - lw) / 2 - pad, y0 - pad / 2, (w + lw) / 2 + pad, y0 + lf.size + pad / 2], radius=18, fill=accent)
        d.text(((w - lw) / 2, y0), label, font=lf, fill=(15, 15, 18))

    cf = font(int(w * (0.085 if vertical else 0.05)))
    lines = _wrap(d, caption, cf, int(w * 0.84))
    lh = int(cf.size * 1.2)
    y = (h - lh * len(lines)) // 2
    for i, line in enumerate(lines):
        lw = d.textlength(line, font=cf)
        d.text(((w - lw) / 2, y), line, font=cf, fill=(255, 255, 255) if i < len(lines) - 1 else accent,
               stroke_width=6, stroke_fill=(0, 0, 0))
        y += lh

    bar_y = int(h * (0.94 if not vertical else 0.95))
    d.rectangle([int(w * 0.22), bar_y, int(w * 0.92), bar_y + 10], fill=(60, 60, 66))
    d.rectangle([int(w * 0.22), bar_y, int(w * 0.22 + w * 0.70 * progress), bar_y + 10], fill=accent)
    ff = font(int(w * (0.03 if vertical else 0.016)))
    d.text((int(w * 0.22), bar_y - ff.size - 14), footer, font=ff, fill=(200, 200, 208))
    img.save(path, "PNG")


def render_cover(path: Path, size: tuple[int, int], title: str, channel_name: str, colors: tuple[RGB, ...], icon: str) -> None:
    """Capa do Short/vídeo: título grande, selo do canal e ícone."""
    w, h = size
    top, bottom, a1, a2 = colors
    img = gradient(size, top, bottom)
    glow = Image.new("RGB", size, (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([w * 0.1, h * 0.25, w * 0.9, h * 0.65], fill=a1)
    img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(int(w * 0.12))), 0.35)
    d = ImageDraw.Draw(img)
    draw_icon(d, icon, w / 2, h * 0.2, min(w, h) * 0.22, a2)
    tf = font(int(w * 0.1))
    lines = _wrap(d, title.upper(), tf, int(w * 0.86))[:5]
    lh = int(tf.size * 1.15)
    y = int(h * 0.36)
    for i, line in enumerate(lines):
        lw = d.textlength(line, font=tf)
        d.text(((w - lw) / 2, y), line, font=tf, fill=a2 if i == len(lines) - 1 else (255, 255, 255), stroke_width=8, stroke_fill=(0, 0, 0))
        y += lh
    bf = font(int(w * 0.045))
    bw = d.textlength(channel_name, font=bf)
    d.rounded_rectangle([(w - bw) / 2 - 30, h * 0.86 - 16, (w + bw) / 2 + 30, h * 0.86 + bf.size + 16], radius=40, fill=a1)
    d.text(((w - bw) / 2, h * 0.86), channel_name, font=bf, fill=(15, 15, 18))
    img.save(path, "PNG")


def render_avatar(path: Path, name: str, colors: tuple[RGB, ...], icon: str, size: int = 800) -> None:
    top, bottom, a1, a2 = colors
    img = gradient((size, size), bottom, top)
    d = ImageDraw.Draw(img)
    d.ellipse([size * 0.06, size * 0.06, size * 0.94, size * 0.94], outline=a1, width=int(size * 0.035))
    draw_icon(d, icon, size * 0.5, size * 0.3, size * 0.3, a2)
    mono = "C+"
    f = font(int(size * 0.3))
    tw = d.textlength(mono, font=f)
    d.text(((size - tw) / 2, size * 0.43), mono, font=f, fill=(255, 255, 255), stroke_width=6, stroke_fill=(0, 0, 0))
    img.save(path, "PNG")


def render_banner(path: Path, name: str, tagline: str, colors: tuple[RGB, ...], icon: str) -> None:
    """Banner 2560x1440. Conteúdo importante dentro da área segura central de 1546x423 (exigência do YouTube)."""
    w, h = 2560, 1440
    top, bottom, a1, a2 = colors
    img = gradient((w, h), top, bottom)
    d = ImageDraw.Draw(img)
    for i in range(-h, w, 120):  # listras diagonais discretas
        d.line([(i, h), (i + h, 0)], fill=tuple(min(255, c + 10) for c in top), width=18)
    safe_w, safe_h = 1500, 400  # um pouco menor que 1546x423 para margem
    sy0 = (h - safe_h) // 2
    icon_s, gap, nsize = 230, 40, 170
    while nsize > 80 and icon_s + gap + d.textlength(name, font=font(nsize)) > safe_w:
        nsize -= 4
    nf = font(nsize)
    nw = d.textlength(name, font=nf)
    x0 = (w - (icon_s + gap + nw)) / 2
    draw_icon(d, icon, x0 + icon_s / 2, sy0 + 120, icon_s, a2)
    d.text((x0 + icon_s + gap, sy0 + 20), name, font=nf, fill=(255, 255, 255), stroke_width=6, stroke_fill=(0, 0, 0))
    size = 64
    while size > 30 and d.textlength(tagline, font=font(size)) > safe_w:
        size -= 2
    tf = font(size)
    d.text(((w - d.textlength(tagline, font=tf)) / 2, sy0 + 290), tagline, font=tf, fill=a1)
    img.save(path, "PNG")
