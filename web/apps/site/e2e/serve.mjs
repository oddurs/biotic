// Serves dist/ the way the deploy does, for the end-to-end tests. `astro preview` daemonises
// itself in some environments, so the tests bring their own dependency-free server.
import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const dist = fileURLToPath(new URL("../dist/", import.meta.url));
const port = Number(process.env.PORT ?? 6969);
const base = (process.env.SITE_BASE ?? "/").replace(/\/$/, "");
const types = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css",
  ".js": "text/javascript",
  ".mjs": "text/javascript",
  ".json": "application/json",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".xml": "application/xml",
  ".txt": "text/plain; charset=utf-8",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
  ".wasm": "application/wasm",
  ".pf_meta": "application/octet-stream",
  ".pf_index": "application/octet-stream",
  ".pf_fragment": "application/octet-stream",
};

function resolve(url) {
  let path = decodeURIComponent(new URL(url, "http://x").pathname);
  if (base && path.startsWith(base)) path = path.slice(base.length) || "/";
  const file = normalize(join(dist, path));
  if (!file.startsWith(dist)) return null;
  if (existsSync(file) && statSync(file).isDirectory()) return join(file, "index.html");
  if (existsSync(file)) return file;
  if (existsSync(`${file}.html`)) return `${file}.html`;
  return null;
}

createServer((req, res) => {
  const file = resolve(req.url ?? "/");
  const found = file && existsSync(file);
  const target = found ? file : join(dist, "404.html");
  res.writeHead(found ? 200 : 404, {
    "content-type": types[extname(target)] ?? "application/octet-stream",
  });
  createReadStream(target).pipe(res);
}).listen(port, () => console.log(`serving ${dist} at http://localhost:${port}${base}/`));
