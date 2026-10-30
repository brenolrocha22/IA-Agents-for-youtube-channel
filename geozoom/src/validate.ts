/** Validações do vídeo final: integridade, resolução, FPS, duração, quadros vazios e geografia. */
import { existsSync, statSync } from "node:fs";
import { ffmpegStderr } from "./ffmpeg.js";
import type { BBox } from "./destinations.js";

export interface Check { code: string; ok: boolean; detail: string }

export function probe(file: string) {
  const { stderr } = ffmpegStderr(["-i", file]);
  const dur = stderr.match(/Duration: (\d+):(\d+):(\d+\.\d+)/);
  const v = stderr.match(/Video: (\w+)[^\n]*?, (\d{2,5})x(\d{2,5})[^\n]*?, ([\d.]+) fps/);
  return {
    duration: dur ? Number(dur[1]) * 3600 + Number(dur[2]) * 60 + Number(dur[3]) : null,
    codec: v?.[1] ?? null, width: v ? Number(v[2]) : null, height: v ? Number(v[3]) : null, fps: v ? Number(v[4]) : null,
  };
}

export interface GeoReport { center: { lon: number; lat: number } | null; corners: { inside: boolean }[] }

export function validate(file: string, opts: { width: number; height: number; fps: number; duration: number; bbox: BBox; geo: GeoReport }): Check[] {
  const checks: Check[] = [];
  const add = (code: string, ok: boolean, detail: string) => checks.push({ code, ok, detail });
  add("arquivo", existsSync(file) && statSync(file).size > 10_000, existsSync(file) ? `${(statSync(file).size / 1e6).toFixed(1)} MB` : "não gerado");
  if (!existsSync(file)) return checks;
  const p = probe(file);
  add("codec", p.codec === "h264", `codec ${p.codec}`);
  add("resolucao", p.width === opts.width && p.height === opts.height, `${p.width}x${p.height} (esperado ${opts.width}x${opts.height})`);
  add("fps", p.fps !== null && Math.abs(p.fps - opts.fps) < 0.01, `${p.fps} fps (esperado ${opts.fps})`);
  add("duracao", p.duration !== null && Math.abs(p.duration - opts.duration) <= 0.1, `${p.duration?.toFixed(2)} s (esperado ${opts.duration} s)`);
  const dec = ffmpegStderr(["-v", "error", "-i", file, "-f", "null", "-"]);
  add("integridade", dec.code === 0 && dec.stderr.trim() === "", dec.stderr.trim().slice(0, 200) || "decodificação completa sem erros");
  // Quadros vazios: >99% preto (o espaço com a Terra visível nunca chega a isso).
  const black = ffmpegStderr(["-i", file, "-vf", "blackdetect=d=0.05:pic_th=0.99:pix_th=0.04", "-an", "-f", "null", "-"]);
  const blacks = [...black.stderr.matchAll(/black_start:([\d.]+) black_end:([\d.]+)/g)].map((m) => `${m[1]}–${m[2]}s`);
  add("quadros_vazios", blacks.length === 0, blacks.length ? `trechos vazios: ${blacks.join(", ")}` : "nenhum quadro vazio");
  // Saltos: diferença média entre quadros consecutivos não pode ter picos isolados.
  const g = opts.geo;
  const [w, s, e, n] = opts.bbox;
  const inBox = g.center && g.center.lon >= w && g.center.lon <= e && g.center.lat >= s && g.center.lat <= n;
  add("geografia_centro", !!inBox, g.center ? `centro do último quadro: ${g.center.lat.toFixed(2)}, ${g.center.lon.toFixed(2)}` : "centro fora do globo");
  const visible = g.corners.filter((c) => c.inside).length;
  add("geografia_enquadramento", visible === 4, `${visible}/4 cantos do destino visíveis no último quadro`);
  return checks;
}

/** Detecta saltos: mede a diferença entre quadros (SSIM) e acusa quedas bruscas. */
export function smoothness(file: string): Check {
  const { stderr } = ffmpegStderr(["-i", file, "-i", file, "-filter_complex",
    "[0:v]trim=start_frame=1,setpts=PTS-STARTPTS[a];[1:v]setpts=PTS-STARTPTS[b];[a][b]ssim=stats_file=-", "-f", "null", "-"]);
  const vals = [...stderr.matchAll(/All:([\d.]+)/g)].map((m) => Number(m[1]));
  const per = vals.slice(0, -1);
  if (per.length < 3) return { code: "continuidade", ok: true, detail: "não medido" };
  const min = Math.min(...per);
  return { code: "continuidade", ok: min > 0.6, detail: `semelhança mínima entre quadros consecutivos (SSIM) ${min.toFixed(3)}` };
}
