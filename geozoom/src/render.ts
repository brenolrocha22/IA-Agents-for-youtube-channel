/** GeoZoom Agent: renderiza a aproximação da Terra até o destino e valida o MP4. */
import { existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer, { type Browser } from "puppeteer-core";
import { cameraAt, frameTimes, startFor, type CameraState } from "./camera.js";
import { resolveDestination, type Destination } from "./destinations.js";
import { ffmpeg } from "./ffmpeg.js";
import { startServer } from "./server.js";
import { smoothness, validate, type Check } from "./validate.js";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const PROJECT = resolve(ROOT, "..");

export interface GeoZoomOptions {
  destination: string;
  durationS?: number;
  fps?: number;
  width?: number;
  height?: number;
  margin?: number; // folga ao redor do destino no quadro final (1.15 = 15%)
  outDir?: string;
  maxTilePasses?: number;
  log?: (msg: string) => void;
}

export interface GeoZoomResult {
  video: string;
  destination: Destination;
  checks: Check[];
  ok: boolean;
  credits: string[];
  framesRendered: number;
  incompleteFrames: number;
}

const CREDITS = [
  "Imagens da Terra: NASA Blue Marble / NASA Earth Observatory — Goddard Space Flight Center (domínio público).",
  "Fronteiras e nomes de países: Natural Earth (domínio público).",
  "Globo 3D: CesiumJS (Apache License 2.0) — sem serviços do Cesium ion.",
  "Céu estrelado: gerado pelo Clip+ Nat (obra própria).",
];

export function browserPath(): string {
  const candidates = [process.env.CHROME_PATH, "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    "/usr/bin/google-chrome", "/usr/bin/chromium"].filter(Boolean) as string[];
  const found = candidates.find((p) => existsSync(p));
  if (!found) throw new Error("Chrome/Edge não encontrado. Defina CHROME_PATH com o caminho do navegador.");
  return found;
}

export async function renderGeoZoom(opts: GeoZoomOptions): Promise<GeoZoomResult> {
  const log = opts.log ?? ((m: string) => console.log(`[geozoom] ${m}`));
  const fps = opts.fps ?? 30, durationS = opts.durationS ?? 8, width = opts.width ?? 1080, height = opts.height ?? 1920;
  const margin = opts.margin ?? 1.15, maxPasses = opts.maxTilePasses ?? 120;
  if (!existsSync(join(ROOT, "data", "tiles", "0", "0", "0.jpg"))) {
    throw new Error("Tiles da Blue Marble ausentes: rode `backend/.venv/Scripts/python.exe geozoom/tools/prepare_assets.py all`.");
  }
  const dest = resolveDestination(opts.destination);
  const slug = dest.name.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^A-Za-z0-9]+/g, "_").toLowerCase();
  const outDir = opts.outDir ?? join(PROJECT, "output", "geozoom", `${slug}_${Date.now()}`);
  const framesDir = join(outDir, "frames");
  mkdirSync(framesDir, { recursive: true });
  log(`Destino: ${dest.name} (${dest.kind}) caixa=${dest.bbox.join(", ")} fonte=${dest.source}`);

  const { server, url } = await startServer();
  let browser: Browser | undefined;
  let incomplete = 0;
  try {
    browser = await puppeteer.launch({
      executablePath: browserPath(), headless: true,
      args: ["--ignore-gpu-blocklist", "--enable-webgl", "--use-angle=default", `--window-size=${width},${height}`, "--hide-scrollbars"],
      defaultViewport: { width, height, deviceScaleFactor: 1 },
    });
    const page = await browser.newPage();
    page.on("pageerror", (e) => log(`erro na página: ${e}`));
    await page.goto(`${url}/index.html`, { waitUntil: "load", timeout: 60_000 });
    const info = await page.evaluate(() => (window as any).geozoom.init({ maxLevel: 4 }));
    log(`Cesium ${info.cesium} pronto (FOV vertical ${(info.fov * 180 / Math.PI).toFixed(1)}°)`);

    const endHeight: number = await page.evaluate((b, m) => (window as any).geozoom.fitHeight(b, m), dest.bbox, margin);
    const end: CameraState = { lon: dest.center.lon, lat: dest.center.lat, height: endHeight };
    const spec = { start: startFor(end), end };
    log(`Câmera: início ${Math.round(spec.start.height / 1000)} km → fim ${Math.round(endHeight / 1000)} km de altitude`);

    const times = frameTimes(durationS, fps);
    for (let k = 0; k < times.length; k++) {
      const state = cameraAt(spec, times[k]);
      const r = await page.evaluate((s, p) => (window as any).geozoom.renderAt(s, p), state, maxPasses);
      if (!r.tilesLoaded) incomplete++;
      await page.screenshot({ path: join(framesDir, `f_${String(k).padStart(4, "0")}.png`) as `${string}.png`, type: "png",
                              clip: { x: 0, y: 0, width, height } });
      if (k % 30 === 0 || k === times.length - 1) log(`quadro ${k + 1}/${times.length} (tiles ${r.tilesLoaded ? "ok" : "incompletos"}, ${r.passes} passagens)`);
    }
    const geo = await page.evaluate((b) => (window as any).geozoom.checkGeo(b), dest.bbox);

    const video = join(outDir, `geozoom_${slug}.mp4`);
    log("Codificando MP4 (H.264, yuv420p)…");
    ffmpeg(["-y", "-framerate", String(fps), "-i", join(framesDir, "f_%04d.png"), "-c:v", "libx264", "-preset", "slow", "-crf", "16",
            "-pix_fmt", "yuv420p", "-r", String(fps), "-movflags", "+faststart", video]);
    const checks = [...validate(video, { width, height, fps, duration: durationS, bbox: dest.bbox, geo }), smoothness(video)];
    checks.push({ code: "tiles_completos", ok: incomplete === 0, detail: incomplete ? `${incomplete} quadro(s) capturados antes do carregamento total` : "todos os quadros com tiles carregados" });
    writeFileSync(join(outDir, "CREDITOS.txt"), CREDITS.join("\n") + "\n", "utf-8");
    writeFileSync(join(outDir, "relatorio.json"), JSON.stringify({ destination: dest, endHeight, checks, geo, credits: CREDITS }, null, 2), "utf-8");
    // Remove o último quadro só depois de usar como prévia (economiza espaço).
    const lastFrame = join(framesDir, `f_${String(times.length - 1).padStart(4, "0")}.png`);
    if (existsSync(lastFrame)) ffmpeg(["-y", "-i", lastFrame, join(outDir, "ultimo_quadro.jpg")]);
    rmSync(framesDir, { recursive: true, force: true });
    const ok = checks.every((c) => c.ok);
    for (const c of checks) log(`${c.ok ? "✔" : "✖"} ${c.code}: ${c.detail}`);
    return { video, destination: dest, checks, ok, credits: CREDITS, framesRendered: times.length, incompleteFrames: incomplete };
  } finally {
    await browser?.close();
    server.close();
  }
}
