"""Pipeline local: narração → legendas → visuais → trilha → renderização (FFmpeg)."""
from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

from ..config import ROOT, get_policy, output_dir
from ..models import ProductionJob, Script
from . import ffmpeg
from .captions import build_cues, write_srt
from .tts import concat_wavs, get_tts, wav_duration
from ..channels import get_channel, palette
from .branding import render_channel_cover
from .visuals import render_frame

GAP_S = 0.25
SIZES = {"vertical": (1080, 1920), "horizontal": (1920, 1080)}


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else str(p)


def synth_music(out: Path, duration: float, timeout_s: int, loop: bool) -> None:
    """Trilha sintetizada (acordes simples com pulso). Obra própria gerada pelo FFmpeg."""
    expr = ("0.10*sin(2*PI*220*t)*(0.55+0.45*sin(2*PI*2*t))"
            "+0.06*sin(2*PI*277.18*t)*(0.6+0.4*sin(2*PI*1*t))"
            "+0.05*sin(2*PI*329.63*t)+0.04*sin(2*PI*110*t)")
    fade = 0.05 if loop else 1.0
    ffmpeg.run(["-y", "-f", "lavfi", "-i", f"aevalsrc={expr}:s=44100:d={duration:.2f}",
                "-af", f"afade=t=in:d={fade},afade=t=out:st={max(0, duration - fade):.2f}:d={fade}",
                str(out)], timeout_s)


def produce(job: ProductionJob, script: Script, update: Callable[[ProductionJob], None],
            check_cancelled: Callable[[], None]) -> ProductionJob:
    limits = get_policy().limits
    vertical = job.orientation == "vertical"
    size = SIZES[job.orientation]
    work = output_dir() / "videos" / job.id
    frames_dir = work / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    def stage(name: str, progress: float, msg: str) -> None:
        check_cancelled()
        job.stage, job.progress = name, progress
        job.log.append(msg)
        update(job)

    job.status = "running"
    # 1) Narração
    tts = get_tts()
    stage("narration", 0.05, f"Narração via provedor '{tts.name}'")
    parts = [work / f"sec_{i:02}.wav" for i in range(len(script.sections))]
    narration = work / "narration.wav"
    rate = 1 if vertical else 0
    for attempt in range(2):  # Short acima do limite: uma nova síntese, mais rápida (limitada)
        tts.synthesize_many([(s.narration, p) for s, p in zip(script.sections, parts)], script.language, rate=rate)
        spans = concat_wavs(parts, narration, GAP_S)
        total = wav_duration(narration)
        if not vertical or total <= limits.max_short_duration_s - 0.5 or attempt == 1:
            break
        rate += 2
        job.log.append(f"Narração com {total:.1f}s excede {limits.max_short_duration_s}s; nova síntese com velocidade {rate}")
    for p in parts:
        p.unlink(missing_ok=True)
    if total > limits.max_video_duration_s:
        raise RuntimeError(f"Duração {total:.0f}s excede o limite de {limits.max_video_duration_s}s")

    # 2) Legendas
    stage("captions", 0.25, f"Narração com {total:.1f}s; gerando legendas")
    cues, cue_section = [], []
    for idx, (sec, (start, dur)) in enumerate(zip(script.sections, spans)):
        for c in build_cues(sec.narration, start, dur, vertical):
            cues.append(c)
            cue_section.append(idx)
    for i in range(len(cues) - 1):  # cobre as pausas: cada legenda vai até a próxima
        cues[i]["end"] = cues[i + 1]["start"]
    cues[-1]["end"] = round(total, 3)
    srt = work / "captions.srt"
    write_srt(cues, srt)

    # 3) Visuais
    channel = get_channel(script.channel_id, "kitchen_short" if script.story_id else "video")
    colors = palette(channel)
    stage("visuals", 0.35, f"Gerando {len(cues)} quadros {size[0]}x{size[1]} na identidade do canal {channel['name']}")
    cover = work / "cover.png"
    render_channel_cover(channel, cover, size, script.title)
    icon_color = tuple(channel["icon_color"]) if channel.get("icon_color") else None
    concat_lines = []
    for i, (cue, sidx) in enumerate(zip(cues, cue_section)):
        sec = script.sections[sidx]
        # Gancho e loop compartilham a variação 0 para o corte do loop ficar contínuo.
        pal = 0 if sec.kind in ("hook", "loop") else 1 + (i % 3)
        frame = frames_dir / f"f_{i:04}.png"
        render_frame(frame, size, cue["text"], sec.on_screen_text, pal, cue["end"] / total, channel["name"], colors, channel["icon"], icon_color)
        concat_lines += [f"file '{frame.as_posix()}'", f"duration {cue['end'] - cue['start']:.3f}"]
    concat_lines.append(f"file '{frame.as_posix()}'")  # o demuxer concat exige repetir o último quadro
    concat_file = work / "frames.txt"
    concat_file.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")

    # 4) Trilha
    stage("music", 0.6, "Sintetizando trilha local")
    music = work / "music.wav"
    synth_music(music, total, limits.max_render_seconds, loop=script.loop)

    # 5) Renderização
    stage("render", 0.7, "Renderizando com FFmpeg (H.264/AAC)")
    video = work / ("short_vertical.mp4" if vertical else "video_horizontal.mp4")
    ffmpeg.run([
        "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-i", str(narration), "-i", str(music),
        "-filter_complex", "[1:a]aresample=44100,volume=1.6[n];[2:a]volume=0.35[m];[n][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]",
        "-map", "0:v", "-map", "[a]", "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-t", f"{total:.3f}", str(video),
    ], limits.max_render_seconds)
    shutil.rmtree(frames_dir, ignore_errors=True)
    concat_file.unlink(missing_ok=True)

    job.outputs = {"video": rel(video), "captions": rel(srt), "cover": rel(cover), "narration": rel(narration), "music": rel(music)}
    job.media = {"duration_s": round(total, 2), "frames": len(cues), **ffmpeg.probe(video)}
    job.rights_manifest = [
        {"asset": "narração", "source": f"TTS {tts.name}", "license": tts.license,
         "status": "verify" if tts.name == "sapi" else "ok"},
        {"asset": "visuais", "source": "Quadros gerados com Pillow pelo próprio sistema", "license": "Obra própria", "status": "ok"},
        {"asset": "tipografia", "source": "Fonte do sistema Windows renderizada em imagem",
         "license": "Uso de fonte instalada para renderizar texto; arquivo de fonte não é redistribuído", "status": "ok"},
        {"asset": "trilha", "source": "Síntese FFmpeg (aevalsrc)", "license": "Obra própria", "status": "ok"},
        *[{"asset": f"texto de referência: {s.title}", "source": s.url, "license": s.license or "fato (sem texto copiado)",
           "status": "ok"} for s in script.sources],
    ]
    stage("rendered", 1.0, f"Vídeo pronto: {rel(video)}")
    job.status = "rendered"
    return job
