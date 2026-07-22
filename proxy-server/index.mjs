// Local loopback-only proxy for the Gemini API.
//
// Why this exists: on this machine, the browser's direct HTTPS requests to
// generativelanguage.googleapis.com come back with a 401
// "ACCESS_TOKEN_TYPE_UNSUPPORTED" error, while the identical request made
// from curl or a plain Node process succeeds every time. That split points
// at browser-specific HTTPS interception (a locally installed security
// product's root CA was found in the Windows trust store). Routing the
// actual Gemini call through this Node process sidesteps that: the browser
// only ever talks to localhost, and this process makes the real outbound
// call the same way our working curl tests did.
//
// The API key is supplied by the browser on every request and is never
// stored here — this process only forwards it to Google.
import { createServer } from "node:http";

const PORT = process.env.PORT ? Number(process.env.PORT) : 3000;
const GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta";
const LOCAL_ORIGIN = /^https?:\/\/(localhost|127\.0\.0\.1):\d+$/;

function applyCors(req, res) {
  const origin = req.headers.origin;
  // "null" is the Origin Chromium sends for file:// pages - this proxy is
  // used both by the Vite dev server (http://localhost:5173) and by
  // BLIP's singlefile dist/index.html build, opened via a plain
  // double-click, whose fetches carry Origin: null instead.
  if (origin && (LOCAL_ORIGIN.test(origin) || origin === "null")) {
    res.setHeader("Access-Control-Allow-Origin", origin);
  }
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
}

async function readJsonBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const raw = Buffer.concat(chunks).toString("utf-8");
  return raw ? JSON.parse(raw) : {};
}

function sendJson(res, status, payload) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(payload));
}

const server = createServer(async (req, res) => {
  applyCors(req, res);

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  if (req.method !== "POST" || req.url !== "/api/generate") {
    sendJson(res, 404, { error: "Not found" });
    return;
  }

  let body;
  try {
    body = await readJsonBody(req);
  } catch {
    sendJson(res, 400, { error: "Invalid JSON body" });
    return;
  }

  // TEMP DEBUG: verify the apiKey field survives browser -> proxy -> Google intact.
  // Logs length + first 4 chars only, never the full key.
  console.log(`[proxy] received body keys: ${Object.keys(body).join(", ")}`);
  const { apiKey, model, systemInstruction, contents, generationConfig } = body;
  if (typeof apiKey === "string") {
    console.log(`[proxy] apiKey from browser: length=${apiKey.length}, prefix="${apiKey.slice(0, 4)}"`);
  } else {
    console.log(`[proxy] apiKey from browser: NOT A STRING, typeof=${typeof apiKey}, value=${JSON.stringify(apiKey)}`);
  }

  if (!apiKey || !model || !contents) {
    sendJson(res, 400, { error: "apiKey, model, and contents are required" });
    return;
  }

  try {
    const url = `${GEMINI_BASE_URL}/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(apiKey)}`;
    console.log(
      `[proxy] apiKey sent to Google: length=${apiKey.length}, prefix="${apiKey.slice(0, 4)}", ` +
        `encodedLength=${encodeURIComponent(apiKey).length}, model=${model}`,
    );
    const upstream = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ systemInstruction, contents, generationConfig }),
    });
    console.log(`[proxy] Google responded: HTTP ${upstream.status}`);

    const text = await upstream.text();
    // Forward retry-after so the browser can honor Gemini's own suggested
    // wait time on 429s instead of guessing with a fixed backoff - Gemini's
    // free-tier quota errors have been observed asking for anywhere from
    // under a second to 45+ seconds depending on quota state.
    const headers = { "Content-Type": "application/json" };
    const retryAfter = upstream.headers.get("retry-after");
    if (retryAfter) headers["Retry-After"] = retryAfter;
    res.writeHead(upstream.status, headers);
    res.end(text);
  } catch (error) {
    sendJson(res, 502, {
      error: `Failed to reach Gemini API: ${error instanceof Error ? error.message : String(error)}`,
    });
  }
});

// HOST defaults to 127.0.0.1 (loopback-only) for local dev, matching the
// original design intent - set HOST=0.0.0.0 in the deployment environment
// (e.g. Render) so the platform's router can actually reach this process
// from outside the container; a loopback-only bind is unreachable there.
const HOST = process.env.HOST ?? "127.0.0.1";

server.listen(PORT, HOST, () => {
  console.log(`Gemini proxy listening on http://${HOST}:${PORT}`);
});
