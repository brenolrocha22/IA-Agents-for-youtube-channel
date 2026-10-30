/** Uso: npm run render -- "Austrália" [--duration 8] [--fps 30] [--margin 1.15] */
import { renderGeoZoom } from "./render.js";

const args = process.argv.slice(2);
const flag = (name: string, def: number) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 ? Number(args[i + 1]) : def;
};
const destination = args.find((a, i) => !a.startsWith("--") && !(i > 0 && args[i - 1].startsWith("--")));
if (!destination) {
  console.error('Informe o destino: npm run render -- "Austrália" (país pt/en, região de data/regions.json ou "lat,lon")');
  process.exit(2);
}
const t0 = Date.now();
renderGeoZoom({ destination, durationS: flag("duration", 8), fps: flag("fps", 30), margin: flag("margin", 1.15) })
  .then((r) => {
    console.log(`\nVídeo: ${r.video}\nValidação: ${r.ok ? "APROVADO" : "COM FALHAS"} · ${((Date.now() - t0) / 1000).toFixed(0)} s`);
    process.exit(r.ok ? 0 : 1);
  })
  .catch((e) => { console.error(`[geozoom] ERRO: ${e instanceof Error ? e.message : e}`); process.exit(1); });
