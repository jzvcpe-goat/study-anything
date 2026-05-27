import { createReadStream, existsSync } from "node:fs";
import { stat } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(fileURLToPath(new URL(".", import.meta.url)), "dist");
const port = Number(process.env.PORT ?? process.env.WEB_PORT ?? 5173);
const host = process.env.HOST ?? "0.0.0.0";
const apiProxyTarget = (process.env.API_PROXY_TARGET ?? "http://api:8000").replace(/\/$/, "");

const contentTypes = new Map([
  [".css", "text/css; charset=utf-8"],
  [".html", "text/html; charset=utf-8"],
  [".ico", "image/x-icon"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".map", "application/json; charset=utf-8"],
  [".png", "image/png"],
  [".svg", "image/svg+xml"],
  [".webp", "image/webp"]
]);

function send(response, status, body, headers = {}) {
  response.writeHead(status, headers);
  response.end(body);
}

function safePath(pathname) {
  const decoded = decodeURIComponent(pathname);
  const normalized = normalize(decoded).replace(/^(\.\.[/\\])+/, "");
  return join(root, normalized === "/" ? "index.html" : normalized);
}

async function serveStatic(request, response) {
  const requestUrl = new URL(request.url ?? "/", `http://${request.headers.host ?? "localhost"}`);
  let assetPath = safePath(requestUrl.pathname);
  if (!existsSync(assetPath)) {
    assetPath = join(root, "index.html");
  }
  const fileStat = await stat(assetPath);
  if (!fileStat.isFile()) {
    assetPath = join(root, "index.html");
  }
  const extension = extname(assetPath);
  response.writeHead(200, {
    "Cache-Control": assetPath.endsWith("index.html") ? "no-store" : "public, max-age=31536000, immutable",
    "Content-Type": contentTypes.get(extension) ?? "application/octet-stream"
  });
  createReadStream(assetPath).pipe(response);
}

async function proxyApi(request, response) {
  const requestUrl = new URL(request.url ?? "/", `http://${request.headers.host ?? "localhost"}`);
  const target = new URL(`${apiProxyTarget}${requestUrl.pathname}${requestUrl.search}`);
  const headers = new Headers();
  for (const [key, value] of Object.entries(request.headers)) {
    if (Array.isArray(value)) {
      headers.set(key, value.join(","));
    } else if (value !== undefined && !["host", "connection", "content-length"].includes(key.toLowerCase())) {
      headers.set(key, value);
    }
  }

  const upstream = await fetch(target, {
    body: request.method === "GET" || request.method === "HEAD" ? undefined : request,
    duplex: "half",
    headers,
    method: request.method
  });

  response.writeHead(upstream.status, Object.fromEntries(upstream.headers.entries()));
  if (upstream.body) {
    for await (const chunk of upstream.body) {
      response.write(chunk);
    }
  }
  response.end();
}

const server = createServer(async (request, response) => {
  try {
    const requestUrl = new URL(request.url ?? "/", `http://${request.headers.host ?? "localhost"}`);
    if (requestUrl.pathname.startsWith("/v1/")) {
      await proxyApi(request, response);
      return;
    }
    await serveStatic(request, response);
  } catch (error) {
    send(response, 502, JSON.stringify({ error: error instanceof Error ? error.message : String(error) }), {
      "Content-Type": "application/json; charset=utf-8"
    });
  }
});

server.listen(port, host, () => {
  console.log(`Study Anything web listening on http://${host}:${port}`);
  console.log(`Proxying /v1 to ${apiProxyTarget}`);
});
