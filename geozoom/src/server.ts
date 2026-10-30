/** Servidor HTTP local mínimo (somente leitura, só 127.0.0.1) para a página, o Cesium e os dados. */
import { createServer, type Server } from "node:http";
import { createReadStream, existsSync, statSync } from "node:fs";
import { extname, join, normalize, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const MOUNTS: Record<string, string> = {
  "/cesium/": join(ROOT, "node_modules", "cesium", "Build", "Cesium"),
  "/data/": join(ROOT, "data"),
  "/": join(ROOT, "web"),
};
const TYPES: Record<string, string> = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
  ".jpg": "image/jpeg", ".png": "image/png", ".svg": "image/svg+xml", ".wasm": "application/wasm", ".glb": "model/gltf-binary",
};

export function startServer(): Promise<{ server: Server; url: string }> {
  const server = createServer((req, res) => {
    const path = decodeURIComponent((req.url ?? "/").split("?")[0]);
    const prefix = Object.keys(MOUNTS).find((p) => path.startsWith(p))!;
    const base = MOUNTS[prefix];
    let file = normalize(join(base, path.slice(prefix.length) || "index.html"));
    if (!file.startsWith(base)) { res.writeHead(403).end(); return; } // impede sair das pastas montadas
    if (existsSync(file) && statSync(file).isDirectory()) file = join(file, "index.html");
    if (!existsSync(file)) { res.writeHead(404).end(); return; }
    res.writeHead(200, { "Content-Type": TYPES[extname(file).toLowerCase()] ?? "application/octet-stream" });
    createReadStream(file).pipe(res);
  });
  return new Promise((ok) => server.listen(0, "127.0.0.1", () => {
    const addr = server.address();
    ok({ server, url: `http://127.0.0.1:${typeof addr === "object" && addr ? addr.port : 0}` });
  }));
}
