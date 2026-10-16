// Staged review API bridge with request logging and an outbound call cap.
import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";
import http from "node:http";

const port = Number(process.argv[2] ?? 4318);
const logPath = process.argv[3];
const apiKey = process.env.OPENROUTER_API_KEY;
const CAP = Number(process.env.REVIEW_CALL_CAP ?? 30);

const UPSTREAM_URL = process.env.JEV_API_URL ?? "https://openrouter.ai/api/alpha/decisions";
const UPSTREAM_MODEL = process.env.JEV_MODEL ?? "~typesafe/jev-latest";

if (!apiKey) {
  console.error("OPENROUTER_API_KEY is not set");
  process.exit(1);
}
if (!Number.isInteger(CAP) || CAP < 1) throw new Error("REVIEW_CALL_CAP must be a positive integer");
mkdirSync(dirname(logPath), { recursive: true });

let seq = 0;
const seenModels = new Set();

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

const server = http.createServer(async (req, res) => {
  if (req.method === "GET" && req.url === "/v1/models") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ models: [] }));
    return;
  }
  if (req.method === "GET" && req.url === "/cap") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ calls: seq, cap: CAP, models: [...seenModels] }));
    return;
  }
  if (req.method !== "POST" || req.url !== "/v1/systemone") {
    res.writeHead(404, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: "not found" }));
    return;
  }
  if (seq >= CAP) {
    res.writeHead(503, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: `call cap reached (${CAP})`, calls: seq }));
    return;
  }
  let payload;
  try { payload = JSON.parse(await readBody(req)); }
  catch {
    res.writeHead(400, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: "invalid JSON request" }));
    return;
  }
  // Reading the body yields control; reserve a slot before forwarding.
  if (seq >= CAP) {
    res.writeHead(503, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: `call cap reached (${CAP})`, calls: seq }));
    return;
  }
  const callSeq = ++seq;
  const clientModel = payload.model;
  payload.model = UPSTREAM_MODEL;

  const started = Date.now();
  let text, status;
  try {
    const upstream = await fetch(UPSTREAM_URL, {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify(payload), signal: AbortSignal.timeout(60000),
    });
    text = await upstream.text();
    status = upstream.status;
  } catch {
    status = 502;
    text = JSON.stringify({ error: "upstream request failed" });
  }
  let parsed = null;
  try { parsed = JSON.parse(text); } catch { parsed = { raw: text }; }
  if (parsed && parsed.model) seenModels.add(parsed.model);
  appendFileSync(logPath, JSON.stringify({
    seq: callSeq, at: new Date().toISOString(), ms: Date.now() - started, clientModel,
    request: payload, status, response: parsed,
    response_model: parsed?.model ?? null,
    mode: "inference", runtime: { backend: "jev", node: process.version,
      model: parsed?.model ?? null, precision: "provider-managed" },
  }) + "\n");
  res.writeHead(status, { "content-type": "application/json" });
  res.end(text);
});

server.listen(port, "127.0.0.1", () => {
  console.log(`live-shim on http://127.0.0.1:${port} -> ${UPSTREAM_URL} (cap ${CAP})`);
});
