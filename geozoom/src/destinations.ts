/** Resolução de destino: país (Natural Earth, pt/en/ISO), região personalizada ou coordenadas "lat,lon". */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

export type BBox = [west: number, south: number, east: number, north: number];

export interface Destination {
  name: string;
  kind: "pais" | "regiao" | "coordenadas";
  bbox: BBox;
  center: { lon: number; lat: number };
  source: string;
}

const DATA = join(dirname(fileURLToPath(import.meta.url)), "..", "data");

interface Country { name_pt: string; name_en: string; iso_a3: string; bbox: BBox }
interface Region { name: string; aliases: string[]; bbox: BBox }

export const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

function load<T>(file: string): T {
  return JSON.parse(readFileSync(join(DATA, file), "utf-8")) as T;
}

export function centerOf(b: BBox): { lon: number; lat: number } {
  return { lon: (b[0] + b[2]) / 2, lat: (b[1] + b[3]) / 2 };
}

/** Interpreta a entrada; lança erro claro se não reconhecer. */
export function resolveDestination(input: string, spanDeg = 6): Destination {
  const raw = input.trim();
  const coord = raw.match(/^\s*(-?\d+(?:\.\d+)?)\s*[,;\s]\s*(-?\d+(?:\.\d+)?)\s*$/);
  if (coord) {
    const lat = Number(coord[1]), lon = Number(coord[2]);
    if (Math.abs(lat) > 90 || Math.abs(lon) > 180) throw new Error(`Coordenadas fora do intervalo: ${raw} (use "lat,lon")`);
    const h = spanDeg / 2;
    return { name: `${lat.toFixed(3)}, ${lon.toFixed(3)}`, kind: "coordenadas", center: { lon, lat },
             bbox: [lon - h, Math.max(-89, lat - h), lon + h, Math.min(89, lat + h)], source: "coordenadas informadas" };
  }
  const key = norm(raw);
  const regions = load<{ regions: Region[] }>("regions.json").regions;
  const region = regions.find((r) => norm(r.name) === key || r.aliases.map(norm).includes(key));
  if (region) return { name: region.name, kind: "regiao", bbox: region.bbox, center: centerOf(region.bbox), source: "data/regions.json" };
  const countries = load<Country[]>("countries.json");
  const country = countries.find((c) => norm(c.name_pt) === key || norm(c.name_en) === key || norm(c.iso_a3) === key);
  if (country) {
    return { name: country.name_pt, kind: "pais", bbox: country.bbox, center: centerOf(country.bbox),
             source: "Natural Earth 1:50m (domínio público)" };
  }
  const hints = countries.filter((c) => norm(c.name_pt).includes(key) || norm(c.name_en).includes(key)).slice(0, 5).map((c) => c.name_pt);
  throw new Error(`Destino "${raw}" não encontrado.${hints.length ? ` Você quis dizer: ${hints.join(", ")}?` : ""} ` +
                  `Use o nome de um país (pt/en), uma região de data/regions.json ou coordenadas "lat,lon".`);
}
