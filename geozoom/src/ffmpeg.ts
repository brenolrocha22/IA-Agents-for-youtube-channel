/** FFmpeg: reutiliza o binário do projeto (FFMPEG_PATH ou o do imageio-ffmpeg no venv do backend). */
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const PROJECT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");

export function ffmpegPath(): string {
  if (process.env.FFMPEG_PATH && existsSync(process.env.FFMPEG_PATH)) return process.env.FFMPEG_PATH;
  const dir = join(PROJECT, "backend", ".venv", "Lib", "site-packages", "imageio_ffmpeg", "binaries");
  const exe = existsSync(dir) ? readdirSync(dir).find((f) => f.startsWith("ffmpeg") && f.endsWith(".exe")) : undefined;
  if (exe) return join(dir, exe);
  const which = spawnSync(process.platform === "win32" ? "where" : "which", ["ffmpeg"], { encoding: "utf-8" });
  if (which.status === 0) return which.stdout.split(/\r?\n/)[0].trim();
  throw new Error("FFmpeg não encontrado: defina FFMPEG_PATH ou instale as dependências do backend (imageio-ffmpeg).");
}

export function ffmpeg(args: string[], timeoutMs = 600_000): string {
  return execFileSync(ffmpegPath(), ["-hide_banner", "-nostdin", ...args], { encoding: "utf-8", timeout: timeoutMs, stdio: ["ignore", "pipe", "pipe"] });
}

/** Saída de diagnóstico (stderr) mesmo quando o ffmpeg retorna sucesso. */
export function ffmpegStderr(args: string[], timeoutMs = 600_000): { code: number | null; stderr: string } {
  const r = spawnSync(ffmpegPath(), ["-hide_banner", "-nostdin", ...args], { encoding: "utf-8", timeout: timeoutMs });
  return { code: r.status, stderr: r.stderr ?? "" };
}
