/** Trajetória determinística da câmera (função pura do tempo). */

export interface CameraState { lon: number; lat: number; height: number }

export const EARTH_START_HEIGHT = 22_000_000; // m: a Terra inteira cabe na largura de um quadro 9:16

/** Suavização com velocidade zero no início e no fim (sem trancos). */
export function easeInOutCubic(x: number): number {
  const t = Math.min(1, Math.max(0, x));
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
}

export function easeInOutSine(x: number): number {
  const t = Math.min(1, Math.max(0, x));
  return -(Math.cos(Math.PI * t) - 1) / 2;
}

/** Diferença de longitude pelo caminho mais curto (−180..180). */
export function lonDelta(a: number, b: number): number {
  return ((b - a + 540) % 360) - 180;
}

export interface PathSpec {
  start: CameraState;
  end: CameraState;
  /** fração do vídeo em que a câmera termina de centralizar o destino (o zoom segue até o fim) */
  centerBy?: number;
  /** fração final parada no destino (respiro antes do corte) */
  hold?: number;
}

/** Posição da câmera em t ∈ [0, 1]. Altura interpolada em escala logarítmica (zoom de aparência constante). */
export function cameraAt(spec: PathSpec, t: number): CameraState {
  const hold = spec.hold ?? 0.08;
  const centerBy = spec.centerBy ?? 0.8;
  const p = Math.min(1, Math.max(0, t) / (1 - hold));
  const pos = easeInOutSine(p / centerBy);
  const zoom = easeInOutCubic(p);
  const { start, end } = spec;
  const lon = start.lon + lonDelta(start.lon, end.lon) * pos;
  return {
    lon: ((lon + 540) % 360) - 180,
    lat: start.lat + (end.lat - start.lat) * pos,
    height: Math.exp(Math.log(start.height) + (Math.log(end.height) - Math.log(start.height)) * zoom),
  };
}

/** Ponto de partida: Terra inteira, levemente deslocada do destino para dar sensação de viagem. */
export function startFor(end: CameraState, lonOffset = -35): CameraState {
  return { lon: ((end.lon + lonOffset + 540) % 360) - 180, lat: end.lat * 0.35, height: EARTH_START_HEIGHT };
}

/** Quadros nos tempos exatos k / fps (determinístico). */
export function frameTimes(durationS: number, fps: number): number[] {
  const n = Math.round(durationS * fps);
  return Array.from({ length: n }, (_, k) => (n === 1 ? 1 : k / (n - 1)));
}
