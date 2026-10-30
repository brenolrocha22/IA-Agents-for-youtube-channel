"""Montagem documental: filmagens reais por cena, sincronizadas com a narração (timestamps do TTS).

ROTEIRO → CENAS → NARRAÇÃO (marcas por palavra) → TRECHOS DAS FILMAGENS → TIMELINE → LEGENDAS → TRILHA → RENDER.
Cenas sem filmagem validada aparecem como "CENA PENDENTE" (versão de revisão) e o QA bloqueia a aprovação.
"""
from __future__ import annotations

import re
import shutil
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageDraw

from ..channels import get_channel
from ..config import ROOT, get_policy, output_dir
from ..models import ProductionJob, Script, VisualPlan
from . import audio, brand_nat, ffmpeg
from .brand_clip import cap_height, font
from .captions import write_srt
from .tts import concat_wavs, get_tts, wav_duration

W, H = 1080, 1920
FPS = 30
GAP_S = 0.12  # pausa curta entre falas: transição mais fluida (pedido do proprietário)
OUTRO_S = 1.6
VOICE_RATE = 1  # SAPI: 0 = normal; +1 ≈ 10% mais rápido (leve, sem distorcer a voz)
FG_H = 1500  # filmagem ocupa ~78% da altura (o animal precisa aparecer grande); fundo desfocado só nas bordas
MIN_SHOT_S = 2.2  # cortes por cena: cada tomada dura pelo menos isso


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else str(p)


def caption_chunks(words: list[dict], offset: float, end: float, max_words: int = 3, max_chars: int = 22) -> list[dict]:
    """Agrupa palavras com tempo real; cada legenda vai até o início da seguinte."""
    chunks, cur = [], []
    for i, w in enumerate(words):
        # Números ("5") às vezes vêm do sintetizador junto com a palavra seguinte, que depois vem de novo.
        toks = w["word"].split()
        if len(toks) > 1 and i + 1 < len(words) and words[i + 1]["word"].split()[:1] == toks[1:2]:
            w = {**w, "word": toks[0]}
        text = " ".join(x["word"] for x in cur + [w])
        if cur and (len(cur) >= max_words or len(text) > max_chars):
            chunks.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.!?,:]$", w["word"]):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    cues = []
    for i, ch in enumerate(chunks):
        start = offset + ch[0]["t"]
        stop = offset + chunks[i + 1][0]["t"] if i + 1 < len(chunks) else end
        cues.append({"start": round(start, 3), "end": round(max(stop, start + 0.2), 3), "text": " ".join(x["word"] for x in ch)})
    return cues


def keywords(script: Script) -> set[str]:
    ks = {re.sub(r"\W", "", w.lower()) for s in script.sections for w in s.on_screen_text.split() if len(w) > 3}
    return ks | {"polvo", "polvos", "tinta", "cor", "textura", "camuflagem", "ventosas", "presas", "predadores"}


def _ass_time(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}"


def write_ass(cues: list[dict], path: Path, keys: set[str], colors: dict) -> None:
    """Legendas ASS (libass): grandes, contorno escuro, palavras-chave em destaque, tamanho ajustado para não cortar."""
    r, g, b = colors["green_light"][:3]
    hl = f"&H00{b:02X}{g:02X}{r:02X}&"
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
        "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Cap,Anton,92,&H00FFFFFF,&H00FFFFFF,&H00080A05,&H96000000,0,0,0,0,100,100,1,0,1,6,3,2,40,40,250,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for cue in cues:
        words = cue["text"].upper().split()
        size = 92
        while size > 48 and sum(font(size).getlength(w + " ") for w in words) > W * 0.88:
            size -= 4
        body = " ".join(f"{{\\c{hl}}}{w}{{\\c&H00FFFFFF&}}" if re.sub(r"\W", "", w.lower()) in keys else w for w in words)
        lines.append(f"Dialogue: 0,{_ass_time(cue['start'])},{_ass_time(cue['end'])},Cap,,0,0,0,,{{\\fs{size}}}{body}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def caption_png(path: Path, text: str, keys: set[str], colors: dict) -> None:
    """Legenda grande, com destaque de palavras-chave, cabendo na largura (sem cortes)."""
    img = Image.new("RGBA", (W, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    size = 92
    words = text.upper().split()
    while size > 48:
        f = font(size)
        if sum(f.getlength(w + " ") for w in words) <= W * 0.9:
            break
        size -= 4
    f = font(size)
    total = sum(f.getlength(w + " ") for w in words) - f.getlength(" ")
    x, base = (W - total) / 2, 150 + cap_height(f) / 2
    for w in words:
        key = re.sub(r"\W", "", w.lower()) in keys
        d.text((x + 4, base + 5), w, font=f, fill=(0, 0, 0, 170), anchor="ls")
        d.text((x, base), w, font=f, fill=colors["green_light"] + (255,) if key else (255, 255, 255, 255), anchor="ls",
               stroke_width=6, stroke_fill=(5, 10, 8, 255))
        x += f.getlength(w + " ")
    img.save(path)


def badge_png(path: Path, channel: dict) -> None:
    c = brand_nat.colors(channel)
    f = font(46)
    w = int(70 + 14 + brand_nat.wordmark_width(f, c) + 36)
    img = Image.new("RGB", (w, 92), c["deep"])
    brand_nat.draw_symbol(img, 52, 46, 44, c, ring=True)
    brand_nat.draw_wordmark(img, 96, 46 + cap_height(f) / 2, f, c, depth=False)
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, 91], radius=46, fill=205)
    out = img.convert("RGBA")
    out.putalpha(mask)
    out.save(path)


def endcard_png(path: Path, channel: dict, work: Path) -> None:
    c = brand_nat.colors(channel)
    img = Image.new("RGBA", (W, H), (*c["deep"], 215))
    av = work / "_avatar.png"
    brand_nat.render_avatar(av, channel, 520)
    a = Image.open(av).convert("RGBA")
    m = Image.new("L", a.size, 0)
    ImageDraw.Draw(m).ellipse([0, 0, a.size[0] - 1, a.size[1] - 1], fill=255)
    a.putalpha(m)
    img.alpha_composite(a, ((W - a.size[0]) // 2, 560))
    rgb = Image.new("RGB", (W, 300), c["deep"])
    f = font(120)
    brand_nat.draw_wordmark(rgb, (W - brand_nat.wordmark_width(f, c)) / 2, 150, f, c)
    tf = font(46)
    tag = channel["tagline"].upper()
    ImageDraw.Draw(rgb).text(((W - tf.getlength(tag)) / 2, 250), tag, font=tf, fill=c["green_light"], anchor="ls")
    img.paste(rgb, (0, 1140))
    av.unlink(missing_ok=True)
    img.save(path)


def pending_png(path: Path, scene_no: int, action: str, colors: dict) -> None:
    img = brand_nat.scene((W, H), colors).convert("RGB")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 760, W, 1160], fill=(0, 0, 0))
    f, s = font(80), font(40)
    for i, (txt, ff, col) in enumerate([(f"CENA {scene_no} PENDENTE", f, (255, 210, 26)),
                                        (f"falta filmagem licenciada: {action}", s, (255, 255, 255)),
                                        ("versão de revisão — não publicar", s, (200, 200, 200))]):
        d.text(((W - ff.getlength(txt)) / 2, 880 + i * 95), txt, font=ff, fill=col, anchor="ls")
    img.save(path)


def scene_clip(src: Path, out: Path, start: float, need: float, src_dur: float, timeout_s: int) -> str:
    """Recorta, enquadra (nítido + fundo desfocado), aplica pan suave e transições curtas. Retorna nota de tratamento."""
    note, speed = "", 1.0
    avail = max(0.1, src_dur - start)
    if avail < need:
        start = max(0.0, src_dur - need) if src_dur >= need else 0.0
        avail = src_dur - start
    if avail < need:
        speed = min(1.6, need / avail)
        note = f"câmera lenta {speed:.2f}x (material curto)"
    take = min(avail, need / speed)
    fade_out = max(0.0, need - 0.18)
    vf = (
        f"[0:v]setpts={speed:.4f}*(PTS-STARTPTS),fps={FPS},split=2[a][b];"
        # Fundo: desfoque numa cópia reduzida (rápido) e ampliada depois.
        f"[a]scale={W // 4}:{H // 4}:force_original_aspect_ratio=increase,crop={W // 4}:{H // 4},gblur=sigma=7,"
        f"scale={W}:{H},eq=brightness=-0.16:saturation=1.1[bg];"
        # Primeiro plano: preenche 1080x1500 (recorte central com pan suave de 30% a 70% da largura excedente).
        f"[b]scale=w='if(gt(a,{W}/{FG_H}),-2,{W})':h='if(gt(a,{W}/{FG_H}),{FG_H},-2)':flags=lanczos,"
        f"crop={W}:{FG_H}:x='(iw-ow)*(0.3+0.4*t/{need:.3f})':y='(ih-oh)/2',unsharp=5:5:0.6[fg];"
        f"[bg][fg]overlay=x=0:y={(H - FG_H) // 2 - 40},format=yuv420p,setsar=1,"
        f"fade=t=in:st=0:d=0.18,fade=t=out:st={fade_out:.3f}:d=0.18,trim=duration={need:.3f}[v]"
    )
    ffmpeg.run(["-y", "-ss", f"{start:.3f}", "-t", f"{take + 0.5:.3f}", "-i", str(src), "-filter_complex", vf, "-map", "[v]",
                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-r", str(FPS), str(out)], timeout_s)
    return note


def fit_clip(src: Path, out: Path, need: float, timeout_s: int) -> None:
    """Acelera/desacelera o clipe inteiro para caber em `need` (o zoom precisa chegar ao destino)."""
    factor = need / max(0.1, ffmpeg.probe(src).get("duration", need))
    ffmpeg.run(["-y", "-i", str(src), "-vf", f"setpts={factor:.4f}*(PTS-STARTPTS),scale={W}:{H},fps={FPS},format=yuv420p,"
                f"setsar=1,trim=duration={need:.3f}", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-r", str(FPS), str(out)], timeout_s)


def still_clip(img: Path, out: Path, need: float, timeout_s: int) -> None:
    ffmpeg.run(["-y", "-loop", "1", "-t", f"{need:.3f}", "-i", str(img), "-vf", f"scale={W}:{H},format=yuv420p,fps={FPS}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)], timeout_s)


def produce_documentary(job: ProductionJob, script: Script, plan: VisualPlan, update: Callable[[ProductionJob], None],
                        save_plan: Callable[[VisualPlan], None], check_cancelled: Callable[[], None]) -> ProductionJob:
    limits = get_policy().limits
    channel = get_channel(script.channel_id, "video")
    colors = brand_nat.colors(channel)
    work = output_dir() / "videos" / job.id
    tmp = work / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)

    def stage(name: str, progress: float, msg: str) -> None:
        check_cancelled()
        job.stage, job.progress = name, progress
        job.log.append(msg)
        update(job)

    job.status = "running"
    # 1) Narração por cena com marcas de tempo reais (sem acelerar a voz).
    tts = get_tts()
    stage("narration", 0.05, f"Narração ({tts.name}); marcas de tempo {tts.timestamps}")
    parts = [tmp / f"sec_{i:02}.wav" for i in range(len(script.sections))]
    narration = work / "narration.wav"
    limit = limits.max_short_duration_s if script.format == "short" else limits.max_video_duration_s
    for rate in (VOICE_RATE, 2):  # 2ª tentativa: fala ~12% mais rápida (leve), só se passar do limite
        marks = tts.synthesize_many([(s.narration, p) for s, p in zip(script.sections, parts)], script.language, rate=rate)
        spans = concat_wavs(parts, narration, GAP_S)
        speech = wav_duration(narration)
        total = speech + OUTRO_S
        if total <= limit + 0.5:
            break
        job.log.append(f"Narração com {total:.1f}s acima de {limit}s; nova síntese um pouco mais rápida")
    if total > limit + 0.5:
        # Para antes de gastar minutos renderizando um vídeo fora do limite.
        words = sum(len(s.narration.split()) for s in script.sections)
        cut = int(words * (1 - (limit - OUTRO_S - 1) / speech)) + 1
        raise ValueError(f"Narração de {total:.0f}s excede o limite de {limit}s mesmo com fala mais rápida. "
                         f"Corte cerca de {cut} palavras do roteiro ({words} hoje) e use 'Editar e refazer'.")

    # 2) Timeline por cena.
    starts = [0.0] + [spans[i][0] for i in range(1, len(spans))]
    ends = starts[1:] + [total]
    for sc, a, b in zip(plan.scenes, starts, ends):
        sc.start, sc.end = round(a, 3), round(b, 3)
    save_plan(plan)
    stage("timeline", 0.15, f"Narração {speech:.1f}s; vídeo {total:.1f}s; {len(plan.scenes)} cenas")
    if script.format == "short" and total > limits.max_short_duration_s + 0.5:
        job.log.append(f"Atenção: {total:.1f}s excede {limits.max_short_duration_s}s (voz não foi acelerada).")

    # 3) Trechos das filmagens.
    pieces, notes = [], []
    for sc in plan.scenes:
        need = sc.end - sc.start
        by_id = {c.id: c for c in sc.candidates}
        cand = by_id.get(sc.selected_id or "")
        stage("footage", 0.2 + 0.4 * sc.index / len(plan.scenes), f"Cena {sc.index + 1}: {cand.title[:50] if cand else 'PENDENTE'}")
        if sc.index == 0 and plan.intro_clip and (ROOT / plan.intro_clip).exists():
            out = tmp / "scene_00_geozoom.mp4"
            fit_clip(ROOT / plan.intro_clip, out, need, limits.max_render_seconds)
            pieces.append(out)
        elif cand and cand.local_path and sc.validation in ("validada", "revisao"):
            # Tomada principal + tomadas extras validadas = cortes dinâmicos dentro da cena.
            shots = [{"id": cand.id, "start": sc.clip_start}] + [s for s in sc.shots if by_id.get(s["id"]) and by_id[s["id"]].local_path]
            shots = shots[: max(1, int(need // MIN_SHOT_S))]
            base_len = need / len(shots)
            for k, shot in enumerate(shots):
                c = by_id[shot["id"]]
                length = need - base_len * (len(shots) - 1) if k == len(shots) - 1 else base_len
                src_dur = c.duration or ffmpeg.probe(ROOT / c.local_path).get("duration", length)
                start = shot.get("start")
                if start is None:
                    start = min(max(0.5, 0.12 * src_dur), max(0.0, src_dur - length))
                if k == 0:
                    sc.clip_start = round(start, 2)
                out = tmp / f"scene_{sc.index:02}_{k}.mp4"
                note = scene_clip(ROOT / c.local_path, out, start, length, src_dur, limits.max_render_seconds)
                if note:
                    notes.append(f"Cena {sc.index + 1}, tomada {k + 1}: {note}")
                pieces.append(out)
        else:
            out = tmp / f"scene_{sc.index:02}_p.mp4"
            png = tmp / f"pending_{sc.index}.png"
            pending_png(png, sc.index + 1, sc.action or "assunto", colors)
            still_clip(png, out, need, limits.max_render_seconds)
            notes.append(f"Cena {sc.index + 1}: sem filmagem validada (CENA PENDENTE)")
            pieces.append(out)
    save_plan(plan)
    listing = tmp / "scenes.txt"
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in pieces), encoding="utf-8")
    base = tmp / "base.mp4"
    ffmpeg.run(["-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(base)], limits.max_render_seconds)

    # 4) Legendas com tempo real de cada palavra.
    stage("captions", 0.65, "Legendas sincronizadas pelas marcas de tempo da narração")
    cues = []
    for i, (words, (s0, dur)) in enumerate(zip(marks, spans)):
        seg_end = spans[i + 1][0] if i + 1 < len(spans) else s0 + dur
        cues += caption_chunks(words, s0, min(seg_end, s0 + dur + 0.15))
    srt = work / "captions.srt"
    write_srt(cues, srt)
    ass = tmp / "captions.ass"
    write_ass(cues, ass, keywords(script), colors)
    fonts = ROOT / "assets" / "fonts" / "anton"
    if fonts.exists():
        shutil.copy2(fonts / "Anton-Regular.ttf", tmp / "Anton-Regular.ttf")
    badge, endcard = tmp / "badge.png", tmp / "endcard.png"
    badge_png(badge, channel)
    endcard_png(endcard, channel, tmp)

    # 5) Trilha e efeitos.
    stage("music", 0.75, "Trilha original de suspense, efeitos e ducking")
    music, sfx = work / "music.wav", work / "sfx.wav"
    audio.suspense_music(music, total, limits.max_render_seconds)
    # Transições sonoras entre falas desligadas por padrão (pedido do proprietário: som mais "clean").
    transitions = channel.get("audio", {}).get("transitions", False)
    ink = [sc.start for sc in plan.scenes if "ink" in (sc.action or "") and sc.start] if transitions else []
    audio.sfx_track(sfx, total, [sc.start for sc in plan.scenes[1:]] if transitions else [], ink, speech + 0.2)

    # 6) Render final.
    stage("render", 0.82, "Renderizando 1080x1920, 30 fps, H.264/AAC")
    video = work / "short_vertical.mp4"
    # Imagens fixas entram em loop (fluxo contínuo); legendas via libass a partir da pasta de trabalho (caminhos relativos).
    loop = ["-loop", "1", "-framerate", "1", "-t", f"{total:.3f}"]  # imagem fixa: 1 quadro/s basta (overlay repete)
    inputs = ["-i", str(base), "-i", str(narration), "-i", str(music), "-i", str(sfx),
              *loop, "-i", str(badge), *loop, "-i", str(endcard)]
    graph = [audio.MIX_FILTER.format(sr=audio.SR, dur=total, **audio.levels(channel)),
             "[0:v]tpad=stop_mode=clone:stop_duration=0.5,subtitles=captions.ass:fontsdir=.[v0]",
             f"[v0][4:v]overlay=x=40:y=60:enable='lt(t,{speech:.3f})'[v1]",
             f"[v1][5:v]overlay=0:0:enable='gte(t,{speech + 0.1:.3f})',trim=duration={total:.3f},format=yuv420p[v]"]
    script_file = tmp / "graph.txt"
    script_file.write_text(";\n".join(graph), encoding="utf-8")
    ffmpeg.run(["-y", *inputs, "-filter_complex_script", "graph.txt", "-map", "[v]", "-map", "[a]", "-r", str(FPS),
                "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", "-t", f"{total:.3f}", str(video)], limits.max_render_seconds, cwd=tmp)

    cover = work / "cover.png"
    sel = [c for sc in plan.scenes for c in sc.candidates if c.id == sc.selected_id and c.local_path]
    frame = tmp / "cover_frame.jpg"
    if sel:
        ffmpeg.run(["-y", "-ss", f"{(plan.scenes[0].clip_start or 1) + 1:.2f}", "-i", str(ROOT / sel[0].local_path),
                    "-frames:v", "1", str(frame)], 60)
    brand_nat.render_cover(cover, (W, H), script.title, channel, image=frame if frame.exists() else None)
    shutil.rmtree(tmp, ignore_errors=True)

    used = {c.id: c for c in used_footage(plan)}
    job.outputs = {"video": rel(video), "captions": rel(srt), "cover": rel(cover), "narration": rel(narration),
                   "music": rel(music), "sfx": rel(sfx)}
    job.media = {"duration_s": round(total, 2), "speech_s": round(speech, 2), "scenes": len(plan.scenes), "notes": notes,
                 "visual_plan_id": plan.id, "coverage": plan.coverage(), **ffmpeg.probe(video)}
    job.rights_manifest = [
        {"asset": "narração", "source": f"TTS {tts.name}", "license": tts.license, "status": "verify" if tts.name == "sapi" else "ok"},
        {"asset": "trilha e efeitos", "source": "Síntese local (FFmpeg aevalsrc + gerador do sistema)", "license": "Obra própria", "status": "ok"},
        {"asset": "gráficos, legendas e marca", "source": "Gerados pelo sistema", "license": "Obra própria", "status": "ok"},
        *[{"asset": f"filmagem: {c.title}", "source": c.page_url, "license": c.license,
           "status": "ok" if c.license_status == "aceita" else "verify", "credit": c.credit,
           "attribution_required": str(c.attribution_required)} for c in used.values()],
    ]
    if plan.intro_clip:
        job.rights_manifest.append({"asset": "abertura GeoZoom (Terra vista do espaço)",
                                    "source": "NASA Blue Marble + Natural Earth, renderizado localmente (CesiumJS)",
                                    "license": "Domínio público (NASA, Natural Earth); CesiumJS Apache-2.0", "status": "ok"})
    stage("rendered", 1.0, f"Vídeo pronto: {rel(video)} (cobertura visual validada: {plan.coverage():.0%})")
    job.status = "rendered"
    return job


CREDITS_HEADER = "Imagens (filmagens reais):"


def used_footage(plan: VisualPlan) -> list:
    """Tomada principal + tomadas extras de cada cena (todas precisam de crédito/licença)."""
    out = {}
    for sc in plan.scenes:
        ids = [sc.selected_id] + [s["id"] for s in sc.shots]
        for c in sc.candidates:
            if c.id in ids:
                out[c.id] = c
    return list(out.values())


def credits_block(plan: VisualPlan) -> str:
    used = used_footage(plan)
    if not used:
        return ""
    return CREDITS_HEADER + "\n" + "\n".join(f"- {line}" for line in sorted({c.credit for c in used}))


def with_credits(description: str, plan: VisualPlan) -> str:
    """Substitui (não acumula) o bloco de créditos na descrição."""
    base = description.split(CREDITS_HEADER)[0].rstrip()
    block = credits_block(plan)
    return f"{base}\n\n{block}".strip() if block else base
