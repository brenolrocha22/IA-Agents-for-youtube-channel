import { test } from "node:test";
import assert from "node:assert/strict";
import { cameraAt, EARTH_START_HEIGHT, easeInOutCubic, frameTimes, lonDelta, startFor } from "../src/camera.ts";
import { resolveDestination } from "../src/destinations.ts";

test("resolve país em português, inglês e ISO (Austrália inclui a Tasmânia)", () => {
  for (const q of ["Austrália", "australia", "AUS"]) {
    const d = resolveDestination(q);
    assert.equal(d.name, "Austrália");
    assert.ok(d.bbox[1] < -43 && d.bbox[3] > -11 && d.bbox[0] > 112 && d.bbox[2] < 155, `caixa ${d.bbox}`);
  }
});

test("resolve região personalizada e coordenadas; erro claro para desconhecido", () => {
  assert.equal(resolveDestination("amazonia").kind, "regiao");
  const c = resolveDestination("-25.27, 133.77");
  assert.equal(c.kind, "coordenadas");
  assert.ok(Math.abs(c.center.lat + 25.27) < 1e-9);
  assert.throws(() => resolveDestination("Atlântida"), /não encontrado/);
  assert.throws(() => resolveDestination("95,10"), /fora do intervalo/);
});

test("suavização: começa e termina parada", () => {
  assert.equal(easeInOutCubic(0), 0);
  assert.equal(easeInOutCubic(1), 1);
  assert.ok(easeInOutCubic(0.01) < 0.001 && 1 - easeInOutCubic(0.99) < 0.001);
});

test("trajetória: começa com a Terra inteira, termina no destino, sem saltos", () => {
  const end = { lon: 133.4, lat: -27.2, height: 7_000_000 };
  const spec = { start: startFor(end), end };
  const times = frameTimes(8, 30);
  assert.equal(times.length, 240);
  const states = times.map((t) => cameraAt(spec, t));
  assert.ok(Math.abs(states[0].height - EARTH_START_HEIGHT) < 1, `altura inicial ${states[0].height}`);
  const last = states.at(-1)!;
  assert.ok(Math.abs(last.lon - end.lon) < 1e-6 && Math.abs(last.lat - end.lat) < 1e-6 && Math.abs(last.height - end.height) < 1);
  // Continuidade: nenhum passo entre quadros maior que 3× a mediana dos passos (sem trancos)
  const steps = states.slice(1).map((s, i) => Math.abs(Math.log(s.height) - Math.log(states[i].height)) + Math.abs(lonDelta(states[i].lon, s.lon)) / 50);
  const median = [...steps].sort((a, b) => a - b)[Math.floor(steps.length / 2)];
  assert.ok(Math.max(...steps) < median * 3 + 0.02, `passo máximo ${Math.max(...steps)} vs mediana ${median}`);
  // Altura nunca aumenta (aproximação contínua)
  assert.ok(states.every((s, i) => i === 0 || s.height <= states[i - 1].height + 1e-6));
});

test("longitude pelo caminho mais curto (atravessa o antimeridiano)", () => {
  assert.equal(lonDelta(170, -170), 20);
  assert.equal(lonDelta(-170, 170), -20);
});
