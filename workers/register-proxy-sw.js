// MisakaNet Register Proxy — Cloudflare Worker
// 职责: 校验输入 → 创建注册 Issue → 返回结果
// counter、头像、欢迎词由 register.yml workflow 处理
// 环境变量: REGISTER_TOKEN (GitHub PAT, 需 issues:write)

const REPO = "Ikalus1988/MisakaNet";
const GITHUB_API = "https://api.github.com";
const PROXY_CACHE_TTL = 30_000;
const KEEPALIVE_ENDPOINTS = [
  { name: "health", url: "https://misakanet.org/api/health", json: true },
  { name: "counter", url: "https://misakanet.org/api/counter", json: true },
  { name: "lessons", url: "https://misakanet.org/api/lessons", json: true, metadataOnly: true },
  { name: "journey", url: "https://misakanet.org/journey/", json: false, metadataOnly: true },
];

// IP 限流: 每个 IP 每 30 秒最多 1 次
const RATE_LIMIT_WINDOW = 30_000;
const rateMap = new Map();

function cleanRateMap() {
  const cutoff = Date.now() - RATE_LIMIT_WINDOW;
  for (const [ip, time] of rateMap) {
    if (time < cutoff) rateMap.delete(ip);
  }
}

// 输入校验
const MAX_AGENT_TYPE = 30;
const MAX_NODE_NAME = 50;

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json",
      ...CORS_HEADERS,
      "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
      "Pragma": "no-cache",
      "Expires": "0",
    },
  });
}

// atob() yields one char per byte, so multi-byte UTF-8 (the Chinese lessons)
// would come back as mojibake without decoding the bytes explicitly.
function decodeBase64Utf8(b64) {
  const binary = atob(String(b64).replace(/\s/g, ""));
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new TextDecoder("utf-8").decode(bytes);
}

// ── GitHub API fetch with token ──
async function fetchTextFromGitHub(token, path, ref = "data") {
  const url = `${GITHUB_API}/repos/${REPO}/contents/${path}?ref=${encodeURIComponent(ref)}`;
  const resp = await fetch(url, {
    headers: { Authorization: `Bearer ${token}`, "User-Agent": "MisakaNet-Worker", Accept: "application/vnd.github.v3+json" },
  });
  if (!resp.ok) throw new Error(`GitHub API ${resp.status}`);
  const data = await resp.json();
  if (!data.content || data.encoding !== "base64") throw new Error("Unexpected GitHub response");
  return decodeBase64Utf8(data.content);
}

async function fetchFromGitHub(token, path, ref = "data") {
  return JSON.parse(await fetchTextFromGitHub(token, path, ref));
}

// ── KV cache wrapper ──
async function getWithCache(env, cacheKey, fetchFn) {
  if (env.MISAKANET_KV) {
    try {
      const cached = await env.MISAKANET_KV.get(cacheKey, "json");
      if (cached && cached.ts && Date.now() - cached.ts < PROXY_CACHE_TTL) return cached.data;
    } catch {}
  }
  const data = await fetchFn();
  if (env.MISAKANET_KV) {
    try { await env.MISAKANET_KV.put(cacheKey, JSON.stringify({ ts: Date.now(), data }), { expirationTtl: Math.ceil(PROXY_CACHE_TTL / 1000) + 30 }); } catch {}
  }
  return data;
}

function sanitizeIdentifier(val, maxLen) {
  if (!val) return "";
  if (val.length > maxLen) val = val.slice(0, maxLen);
  // 只允许字母、数字、下划线、连字符、中文
  return val.replace(/[^\w\u4e00-\u9fa5\-]/g, "");
}

// ═══════════════════════════════════════════════════════════════════════════
// Remote MCP endpoint — POST /mcp (Issue #804)
//
// Streamable HTTP transport, Phase 1 = read-only: misakanet_search and
// misakanet_get_lesson. Any MCP client (Claude, Cursor, Copilot, Glama) can
// connect without cloning the repo. Writes (submit_usage, usage_status) are
// deliberately out of scope here.
// ═══════════════════════════════════════════════════════════════════════════

const MCP_PATH = "/mcp";
const MCP_DEFAULT_PROTOCOL = "2025-06-18";
// Newest first — 2026-07-28 is the forward-compat RC, 2025-03-26 the legacy fallback.
const MCP_SUPPORTED_PROTOCOLS = ["2026-07-28", "2025-06-18", "2025-03-26"];
// Used when the MCP_VERSION secret is unset. Kept in sync with pyproject.toml
// by tests/test_mcp_remote_worker.py.
const MCP_FALLBACK_VERSION = "2.15.0";
const MCP_LESSON_REF = "main";
const MCP_INDEX_PATH = "lessons.json";
const MCP_INDEX_REF = "data";
const MCP_MAX_BODY = 65_536;
const MCP_MAX_RESULTS = 20;
const MCP_LESSON_MAX_CHARS = 5000;

// Origin allowlist (DNS rebinding protection). Non-browser MCP clients send no
// Origin header at all; only a *present and unknown* Origin is rejected.
const MCP_ALLOWED_ORIGINS = [
  "https://misakanet.org",
  "https://www.misakanet.org",
  "https://ikalus1988.github.io",
  "https://glama.ai",
  "https://claude.ai",
  "https://cursor.com",
];

const MCP_TOOLS = [
  {
    name: "misakanet_search",
    description:
      "Search MisakaNet's public failure-lesson index by error text, keyword, or topic. " +
      "Use when you need to discover relevant lessons and do not already know a lesson ID. " +
      "Input: query is required; domain optionally filters by lesson domain; top limits ranked " +
      "results (default 5, max 20). Output: JSON with results[] of ranked lesson summaries " +
      "(id, title, domain, tags, status, path, score) plus count and source. Error cases: missing " +
      "query, or upstream index unavailable. Side effects: none — read-only. Do not send private " +
      "logs or prompts; search with redacted snippets only. Use misakanet_get_lesson for full content.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Required redacted error message, keyword, or topic (for example: 'database is locked')." },
        domain: { type: "string", description: "Optional domain filter such as devops, python, network, rag, or mcp." },
        top: { type: "integer", description: "Maximum ranked results to return. Defaults to 5, capped at 20." },
      },
      required: ["query"],
    },
  },
  {
    name: "misakanet_get_lesson",
    description:
      "Fetch one public MisakaNet lesson as markdown, by repository path or lesson ID. Use after " +
      "misakanet_search returns a promising result, or when a lesson is explicitly referenced; not " +
      "for broad discovery. Input: provide either path (lessons/<dir>/<id>.md) or id. Output: JSON " +
      "with path, content (truncated to 5000 characters), length, and truncated flag. Error cases: " +
      "missing path/id, or lesson not found. Side effects: none — read-only.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Lesson path relative to the repository, for example lessons/core/auto-merge-ci-pipeline.md." },
        id: { type: "string", description: "Lesson ID, usually the filename without .md, for example auto-merge-ci-pipeline." },
      },
    },
  },
];

function mcpTimingSafeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length || a.length === 0) return false;
  let mismatch = 0;
  for (let i = 0; i < a.length; i++) mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return mismatch === 0;
}

function mcpBearerToken(request) {
  const header = (request.headers.get("Authorization") || "").trim();
  const match = /^Bearer\s+(.+)$/i.exec(header);
  return match ? match[1].trim() : "";
}

function mcpOriginAllowed(origin, env = {}) {
  if (!origin) return true; // curl / native MCP hosts never send Origin
  const extra = String(env.MCP_ALLOWED_ORIGINS || "").split(",").map((o) => o.trim()).filter(Boolean);
  return MCP_ALLOWED_ORIGINS.includes(origin) || extra.includes(origin);
}

function mcpCorsHeaders(origin, env) {
  const headers = {
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type, MCP-Protocol-Version, Mcp-Session-Id",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
  // Only echo an Origin that already passed the allowlist above.
  if (origin && mcpOriginAllowed(origin, env)) headers["Access-Control-Allow-Origin"] = origin;
  return headers;
}

function mcpJson(body, status, origin, env, extraHeaders = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json",
      "Cache-Control": "no-store",
      ...mcpCorsHeaders(origin, env),
      ...extraHeaders,
    },
  });
}

function mcpErrorBody(id, code, message) {
  return { jsonrpc: "2.0", id: id ?? null, error: { code, message } };
}

function mcpServerVersion(env) {
  return String(env.MCP_VERSION || MCP_FALLBACK_VERSION);
}

// ── Ranking ──
// Lightweight keyword scoring over the lessons.json index. CJK queries have no
// whitespace, so CJK tokens also contribute their character bigrams.
function mcpTokenize(text) {
  const tokens = [];
  for (const raw of String(text).toLowerCase().split(/[^\p{L}\p{N}_]+/u)) {
    if (!raw) continue;
    const isCjk = /[\u3400-\u9fff\u3040-\u30ff]/.test(raw); // CJK ideographs + kana
    if (raw.length >= 2 || isCjk) tokens.push(raw);
    if (isCjk && raw.length > 2) {
      for (let i = 0; i < raw.length - 1; i++) tokens.push(raw.slice(i, i + 2));
    }
  }
  return [...new Set(tokens)];
}

const MCP_FIELD_WEIGHTS = [
  ["title", 5],
  ["tags", 4],
  ["id", 3],
  ["domain", 3],
  ["summary", 2],
  ["preview", 1],
];

function mcpScoreLesson(lesson, tokens, phrase) {
  const fields = {
    title: String(lesson.title || ""),
    tags: Array.isArray(lesson.tags) ? lesson.tags.join(" ") : String(lesson.tags || ""),
    id: String(lesson.id || ""),
    domain: String(lesson.domain || ""),
    summary: String(lesson.summary || ""),
    preview: String(lesson.preview || ""),
  };

  let score = 0;
  for (const [field, weight] of MCP_FIELD_WEIGHTS) {
    const hay = fields[field].toLowerCase();
    if (!hay) continue;
    for (const token of tokens) if (hay.includes(token)) score += weight;
    if (phrase.length >= 3 && hay.includes(phrase)) score += weight * 2;
  }
  if (score === 0) return 0;

  if (lesson.verified) score += 1;
  if (lesson.status && lesson.status !== "active") score -= 1;
  const confidence = typeof lesson.confidence === "number" ? lesson.confidence : 0.5;
  return Math.round((score + confidence) * 1000) / 1000;
}

function mcpRankLessons(lessons, { query, domain, top = 5 } = {}) {
  const tokens = mcpTokenize(query);
  const phrase = String(query).toLowerCase().trim();
  const wantedDomain = domain ? String(domain).toLowerCase() : null;

  const scored = [];
  for (const lesson of Array.isArray(lessons) ? lessons : []) {
    if (!lesson || typeof lesson !== "object") continue;
    if (wantedDomain && String(lesson.domain || "").toLowerCase() !== wantedDomain) continue;
    const score = mcpScoreLesson(lesson, tokens, phrase);
    if (score > 0) scored.push({ lesson, score });
  }

  scored.sort((a, b) => b.score - a.score || String(a.lesson.id || "").localeCompare(String(b.lesson.id || "")));
  return scored.slice(0, top).map(({ lesson, score }) => ({
    id: lesson.id || null,
    title: lesson.title || null,
    domain: lesson.domain || null,
    tags: Array.isArray(lesson.tags) ? lesson.tags : [],
    status: lesson.status || null,
    verified: !!lesson.verified,
    path: lesson.url || null,
    score,
  }));
}

// Only repository lesson markdown is reachable — no traversal, no other paths.
function mcpSafeLessonPath(candidate) {
  const path = String(candidate || "").replace(/^\.\//, "").trim();
  if (path.includes("..")) return null;
  if (!/^lessons\/[A-Za-z0-9._/-]+\.md$/.test(path)) return null;
  return path;
}

async function mcpLoadLessons(env) {
  const token = env.REGISTER_TOKEN;
  if (!token) throw new Error("REGISTER_TOKEN not configured");
  // Same cache key as GET /api/lessons — one index fetch serves both.
  return getWithCache(env, "proxy:lessons", () => fetchFromGitHub(token, MCP_INDEX_PATH, MCP_INDEX_REF));
}

async function mcpToolSearch(args, env) {
  const query = typeof args.query === "string" ? args.query.trim() : "";
  if (!query) return { error: "query is required" };

  const requestedTop = parseInt(args.top, 10);
  const top = Math.min(Math.max(Number.isFinite(requestedTop) ? requestedTop : 5, 1), MCP_MAX_RESULTS);
  const lessons = await mcpLoadLessons(env);
  const results = mcpRankLessons(lessons, { query, domain: args.domain, top });

  return { query, count: results.length, results, source: "misakanet-worker" };
}

// path wins when given; otherwise resolve the ID through the index, falling
// back to the two conventional lesson directories.
async function mcpLessonCandidates(args, env) {
  const explicit = mcpSafeLessonPath(args.path);
  if (explicit) return [explicit];

  const raw = typeof args.id === "string" && args.id ? args.id : args.path;
  const id = sanitizeIdentifier(String(raw || "").replace(/\.md$/, ""), 120);
  if (!id) return [];

  const candidates = [];
  try {
    const lessons = await mcpLoadLessons(env);
    const hit = (Array.isArray(lessons) ? lessons : []).find(
      (lesson) => lesson && String(lesson.id || "").toLowerCase() === id.toLowerCase(),
    );
    const indexed = hit && mcpSafeLessonPath(hit.url);
    if (indexed) candidates.push(indexed);
  } catch { /* index unavailable — fall through to the conventional paths */ }

  for (const dir of ["core", "contrib"]) {
    const guess = mcpSafeLessonPath(`lessons/${dir}/${id}.md`);
    if (guess && !candidates.includes(guess)) candidates.push(guess);
  }
  return candidates;
}

async function mcpToolGetLesson(args, env) {
  if (!args.path && !args.id) return { error: "path or id is required" };

  const token = env.REGISTER_TOKEN;
  if (!token) throw new Error("REGISTER_TOKEN not configured");

  const candidates = await mcpLessonCandidates(args, env);
  if (!candidates.length) return { error: `Lesson not found: ${String(args.path || args.id).slice(0, 120)}` };

  for (const path of candidates) {
    let markdown;
    try {
      markdown = await fetchTextFromGitHub(token, path, MCP_LESSON_REF);
    } catch {
      continue;
    }
    const truncated = markdown.length > MCP_LESSON_MAX_CHARS;
    return {
      path,
      length: markdown.length,
      truncated,
      content: truncated ? markdown.slice(0, MCP_LESSON_MAX_CHARS) : markdown,
    };
  }

  return { error: `Lesson not found: ${String(args.path || args.id).slice(0, 120)}` };
}

async function mcpCallTool(name, args, env) {
  const handlers = {
    misakanet_search: mcpToolSearch,
    misakanet_get_lesson: mcpToolGetLesson,
  };
  const handler = handlers[name];
  if (!handler) return null;

  let payload;
  try {
    payload = await handler(args && typeof args === "object" ? args : {}, env);
  } catch (err) {
    payload = { error: `Upstream failure: ${err.message}` };
  }

  // Tool-level failures stay inside the result with isError, per MCP spec —
  // only protocol failures become JSON-RPC errors.
  return {
    content: [{ type: "text", text: JSON.stringify(payload, null, 2) }],
    isError: !!payload.error,
  };
}

// Returns a JSON-RPC response object, or null for notifications (nothing to send back).
async function mcpDispatch(message, env) {
  const id = message.id ?? null;
  const method = String(message.method || "");
  const params = message.params && typeof message.params === "object" ? message.params : {};

  if (method.startsWith("notifications/")) return null;

  switch (method) {
    case "initialize": {
      const requested = String(params.protocolVersion || "");
      const negotiated = MCP_SUPPORTED_PROTOCOLS.includes(requested) ? requested : MCP_DEFAULT_PROTOCOL;
      return {
        jsonrpc: "2.0",
        id,
        result: {
          protocolVersion: negotiated,
          capabilities: { tools: { listChanged: false } },
          serverInfo: { name: "misakanet", title: "MisakaNet", version: mcpServerVersion(env) },
          instructions:
            "MisakaNet is a cross-agent index of failure lessons. Search it with misakanet_search " +
            "before debugging a recurring error, then read the full lesson with misakanet_get_lesson. " +
            "Read-only: never send private logs, prompts, or secrets.",
        },
      };
    }

    case "ping":
      return { jsonrpc: "2.0", id, result: {} };

    case "tools/list":
      return { jsonrpc: "2.0", id, result: { tools: MCP_TOOLS } };

    case "tools/call": {
      const name = String(params.name || "");
      const result = await mcpCallTool(name, params.arguments, env);
      if (!result) return mcpErrorBody(id, -32602, `Unknown tool: ${name}`);
      console.log(`[mcp] tools/call ${name}`);
      return { jsonrpc: "2.0", id, result };
    }

    default:
      return mcpErrorBody(id, -32601, `Method not found: ${method}`);
  }
}

async function handleMcpRequest(request, env) {
  const origin = request.headers.get("Origin");

  // 1. Origin allowlist — DNS rebinding protection, checked before auth.
  if (!mcpOriginAllowed(origin, env)) {
    return mcpJson(mcpErrorBody(null, -32000, "Forbidden origin"), 403, null, env);
  }

  // 2. Bearer auth.
  if (!env.MCP_TOKEN) {
    return mcpJson(mcpErrorBody(null, -32000, "MCP endpoint not configured (MCP_TOKEN missing)"), 503, origin, env);
  }
  if (!mcpTimingSafeEqual(mcpBearerToken(request), String(env.MCP_TOKEN))) {
    return mcpJson(mcpErrorBody(null, -32001, "Unauthorized"), 401, origin, env, {
      "WWW-Authenticate": 'Bearer realm="misakanet-mcp"',
    });
  }

  // 3. Transport-level validation.
  const headerVersion = request.headers.get("MCP-Protocol-Version");
  if (headerVersion && !MCP_SUPPORTED_PROTOCOLS.includes(headerVersion)) {
    return mcpJson(mcpErrorBody(null, -32000, `Unsupported MCP-Protocol-Version: ${headerVersion}`), 400, origin, env);
  }
  if (parseInt(request.headers.get("content-length") || "0", 10) > MCP_MAX_BODY) {
    return mcpJson(mcpErrorBody(null, -32600, "Request too large"), 413, origin, env);
  }

  let message;
  try {
    message = await request.json();
  } catch {
    return mcpJson(mcpErrorBody(null, -32700, "Parse error"), 400, origin, env);
  }
  if (Array.isArray(message)) {
    return mcpJson(mcpErrorBody(null, -32600, "JSON-RPC batching is not supported (removed in MCP 2025-06-18)"), 400, origin, env);
  }
  if (!message || typeof message !== "object" || message.jsonrpc !== "2.0" || typeof message.method !== "string") {
    return mcpJson(mcpErrorBody(message && message.id, -32600, "Invalid Request"), 400, origin, env);
  }

  const responseHeaders = { "MCP-Protocol-Version": headerVersion || MCP_DEFAULT_PROTOCOL };

  let response;
  try {
    response = await mcpDispatch(message, env);
  } catch (err) {
    console.error("[mcp] internal error", err.message);
    return mcpJson(mcpErrorBody(message.id, -32603, `Internal error: ${err.message}`), 500, origin, env, responseHeaders);
  }

  // Notifications carry no response body.
  if (!response) return new Response(null, { status: 202, headers: { ...mcpCorsHeaders(origin, env), ...responseHeaders } });
  return mcpJson(response, 200, origin, env, responseHeaders);
}

// GET/DELETE /mcp — no server-initiated SSE stream is offered, so the spec
// requires 405 plus Accept-Post advertising the POST content type.
function mcpMethodNotAllowed(request, env) {
  return mcpJson(mcpErrorBody(null, -32000, "Method not allowed. Use POST /mcp (Streamable HTTP)."), 405, request.headers.get("Origin"), env, {
    "Accept-Post": "application/json",
    Allow: "POST, OPTIONS",
  });
}

async function probeKeepaliveEndpoint(endpoint) {
  const resp = await fetch(endpoint.url, {
    headers: { "User-Agent": "MisakaNet-Register-Proxy-Keepalive/1.0" },
  });
  if (!resp.ok) {
    throw new Error(`${endpoint.name} returned HTTP ${resp.status}`);
  }

  const contentType = resp.headers.get("content-type") || "";
  if (endpoint.json && !contentType.includes("application/json")) {
    throw new Error(`${endpoint.name} returned non-JSON content-type: ${contentType || "unknown"}`);
  }

  // Only parse the tiny control-plane responses. For larger pages/feeds, headers
  // are enough to prove the route is alive without buffering an unbounded body.
  if (endpoint.json && !endpoint.metadataOnly) {
    await resp.json();
  } else if (resp.body) {
    await resp.body.cancel();
  }

  return {
    name: endpoint.name,
    status: resp.status,
    contentType,
  };
}

async function runKeepaliveSweep(cron = "manual") {
  const results = await Promise.allSettled(KEEPALIVE_ENDPOINTS.map(probeKeepaliveEndpoint));
  const failures = results
    .filter((item) => item.status === "rejected")
    .map((item) => item.reason?.message || String(item.reason));

  if (failures.length) {
    console.error("[keepalive] failed", JSON.stringify({ cron, failures }));
    throw new Error(`[keepalive] failed: ${failures.join("; ")}`);
  }

  console.log("[keepalive] ok", JSON.stringify({ cron, endpoints: KEEPALIVE_ENDPOINTS.length }));
  return { ok: true, failures: [] };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Remote MCP endpoint (#804) — own auth/CORS rules, so it goes before the
    // generic OPTIONS handler and every /api route.
    if (url.pathname === MCP_PATH || url.pathname === `${MCP_PATH}/`) {
      if (request.method === "OPTIONS") {
        return new Response(null, { status: 204, headers: mcpCorsHeaders(request.headers.get("Origin"), env) });
      }
      if (request.method === "POST") {
        return handleMcpRequest(request, env);
      }
      return mcpMethodNotAllowed(request, env);
    }

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
    }

    if (request.method === "GET" && url.pathname === "/api/health") {
      return jsonResponse({
        status: "ok",
        worker: "misakanet-register-proxy",
        scheduled_keepalive: true,
        hasToken: !!env.REGISTER_TOKEN,
        hasKV: !!env.MISAKANET_KV,
        timestamp: new Date().toISOString(),
      });
    }

    // GET /api/counter — node registration counter (KV or GitHub)
    if (request.method === "GET" && (url.pathname === "/api/counter" || url.pathname === "/api/counter.json")) {
      const token = env.REGISTER_TOKEN;
      if (!token) return jsonResponse({ error: "REGISTER_TOKEN not configured" }, 500);
      try {
        const data = await getWithCache(env, "proxy:counter", async () => {
          if (env.MISAKANET_KV) {
            const kvCounter = await env.MISAKANET_KV.get("node_counter", "text");
            if (kvCounter) return { current: parseInt(kvCounter), updated: new Date().toISOString().slice(0, 10) };
          }
          return fetchFromGitHub(token, "data/counter.json");
        });
        return jsonResponse(data);
      } catch (e) { return jsonResponse({ error: e.message }, 502); }
    }

    // GET /api/lessons — lessons index (GitHub with KV cache)
    if (request.method === "GET" && (url.pathname === "/api/lessons" || url.pathname === "/api/lessons.json")) {
      const token = env.REGISTER_TOKEN;
      if (!token) return jsonResponse({ error: "REGISTER_TOKEN not configured" }, 500);
      try {
        const data = await getWithCache(env, "proxy:lessons", () => fetchFromGitHub(token, "lessons.json", "data"));
        return jsonResponse(data);
      } catch (e) { return jsonResponse({ error: e.message }, 502); }
    }

    if (request.method === "GET" && url.pathname === "/ping") {
      return new Response("pong", {
        status: 200,
        headers: { "content-type": "text/plain;charset=utf-8", ...CORS_HEADERS },
      });
    }

    // GET /api/helpful?lesson_id=<id> — return helpful count
    if (request.method === "GET" && url.pathname === "/api/helpful") {
      if (!env.MISAKANET_KV) return jsonResponse({ error: "KV not configured" }, 503);
      const lessonId = sanitizeIdentifier(url.searchParams.get("lesson_id"), 100);
      if (!lessonId) return jsonResponse({ error: "Missing lesson_id" }, 400);
      const raw = await env.MISAKANET_KV.get(`helpful:${lessonId}`, "text");
      return jsonResponse({ lesson_id: lessonId, count: raw ? parseInt(raw, 10) || 0 : 0 });
    }

    // POST /api/helpful — record a helpful vote
    if (request.method === "POST" && url.pathname === "/api/helpful") {
      if (!env.MISAKANET_KV) return jsonResponse({ error: "KV not configured" }, 503);
      let voteBody;
      try { voteBody = await request.json(); } catch { return jsonResponse({ error: "Invalid JSON" }, 400); }
      const lessonId = sanitizeIdentifier(voteBody.lesson_id, 100);
      if (!lessonId) return jsonResponse({ error: "Missing lesson_id" }, 400);
      const kvKey = `helpful:${lessonId}`;
      const cur = parseInt(await env.MISAKANET_KV.get(kvKey, "text") || "0", 10) || 0;
      const newCount = cur + 1;
      await env.MISAKANET_KV.put(kvKey, String(newCount));
      return jsonResponse({ lesson_id: lessonId, count: newCount });
    }

    // POST /api/feedback — search result feedback intake
    if (request.method === "POST" && url.pathname === "/api/feedback") {
      if (!env.MISAKANET_KV) return jsonResponse({ error: "KV not configured" }, 503);

      // IP rate limit: 10 feedbacks per IP per minute
      const fbIp = request.headers.get("CF-Connecting-IP") || "unknown";
      const fbRateKey = `rate:feedback:${fbIp}`;
      const fbRateRaw = await env.MISAKANET_KV.get(fbRateKey, "text");
      const fbRateCount = fbRateRaw ? parseInt(fbRateRaw, 10) || 0 : 0;
      if (fbRateCount >= 10) return jsonResponse({ error: "Rate limited. Try again later." }, 429);
      await env.MISAKANET_KV.put(fbRateKey, String(fbRateCount + 1), { expirationTtl: 60 });

      let fbBody;
      try { fbBody = await request.json(); } catch { return jsonResponse({ error: "Invalid JSON" }, 400); }
      const entries = Array.isArray(fbBody) ? fbBody : [fbBody];
      const accepted = [];

      for (const entry of entries) {
        const { query, lesson_id, feedback, ts } = entry || {};
        if (!query || !lesson_id || !feedback) continue;
        if (!["irrelevant", "too_basic", "helpful"].includes(feedback)) continue;

        const feedbackId = crypto.randomUUID();
        const record = {
          feedbackId,
          query: String(query).slice(0, 200),
          lesson_id: String(lesson_id).slice(0, 200),
          feedback,
          ts: ts || new Date().toISOString(),
          ip: fbIp,
        };

        await env.MISAKANET_KV.put(
          `feedback:${feedbackId}`,
          JSON.stringify(record),
          { expirationTtl: 7776000 }, // 90 days
        );
        accepted.push(feedbackId);
        console.log(`Feedback ${feedbackId}: ${feedback} on ${lesson_id} for "${query}"`);
      }

      return jsonResponse({ accepted: accepted.length });
    }

    // POST /api/intake — general-purpose intake for MCP, agents, sandbox (#589)
    // Redacts secrets before persistence. Records demand signals for unmatched items.
    if (request.method === "POST" && url.pathname === "/api/intake") {
      if (!env.MISAKANET_KV) return jsonResponse({ error: "KV not configured" }, 503);

      // Max body 8KB
      const contentLength = parseInt(request.headers.get("content-length") || "0");
      if (contentLength > 8192) return jsonResponse({ error: "Request too large (max 8KB)" }, 413);

      // IP rate limit: 10 per hour
      const intakeIp = request.headers.get("CF-Connecting-IP") || "unknown";
      const intakeRateKey = `rate:intake:${intakeIp}`;
      const intakeRateRaw = await env.MISAKANET_KV.get(intakeRateKey, "text");
      const intakeRateCount = intakeRateRaw ? parseInt(intakeRateRaw, 10) || 0 : 0;
      if (intakeRateCount >= 10) return jsonResponse({ error: "Rate limited (10/hour). Try again later." }, 429);
      await env.MISAKANET_KV.put(intakeRateKey, String(intakeRateCount + 1), { expirationTtl: 3600 });

      let intakeBody;
      try { intakeBody = await request.json(); } catch { return jsonResponse({ error: "Invalid JSON" }, 400); }

      // Field whitelist + validation
      const VALID_TYPES = ["diagnostic", "lesson_candidate", "friction", "bug", "node_join"];
      const VALID_SOURCES = ["mcp", "curl", "frontend", "agent"];
      const VALID_CONSENT = ["private_only", "allow_anonymous_publish"];

      const { type, source, message, context, lesson_id, contact, consent, ts } = intakeBody || {};
      if (!type || !VALID_TYPES.includes(type)) return jsonResponse({ error: "Invalid or missing 'type'. Must be one of: " + VALID_TYPES.join(", ") }, 400);
      if (!source || !VALID_SOURCES.includes(source)) return jsonResponse({ error: "Invalid or missing 'source'. Must be one of: " + VALID_SOURCES.join(", ") }, 400);
      if (!message || typeof message !== "string" || !message.trim()) return jsonResponse({ error: "Missing 'message'" }, 400);

      // Secret redaction (inline — mirrors scripts/intake_redact.py patterns)
      const REDACT_PATTERNS = [
        [/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END(?: RSA | EC | OPENSSH )?PRIVATE KEY-----/gi, "[REDACTED:private_key]"],
        [/(?:ghp|gho|ghu|ghs|ghr|github_pat)_[a-zA-Z0-9]{10,}/g, "[REDACTED:github_token]"],
        [/xox[bpras]-[a-zA-Z0-9\-]{10,}/g, "[REDACTED:slack_token]"],
        [/(?:AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}/g, "[REDACTED:aws_key]"],
        [/(?:sk|pk|rk|ak)[_-][a-zA-Z0-9]{10,}/g, "[REDACTED:api_key]"],
        [/(?:Bearer|Authorization)\s+[a-zA-Z0-9\-._~+/]+=*/gi, "[REDACTED:bearer_token]"],
        [/(?:password|passwd|secret|token|api[_-]?key|apikey|database[_-]?url)\s*[:=]\s*\S+/gi, "[REDACTED:credential]"],
        [/:[^:]+:[^@]+@[^\s]+/g, "://[REDACTED:url_credential]@host"],
        [/\b(?:\d[ -]*?){13,19}\b/g, "[REDACTED:card_number]"],
      ];
      function redactSecrets(text) {
        let result = String(text).slice(0, 2000);
        for (const [pat, repl] of REDACT_PATTERNS) result = result.replace(pat, repl);
        return result;
      }

      const intakeId = crypto.randomUUID();
      const record = {
        intakeId,
        type,
        source,
        message: redactSecrets(message),
        context: context ? JSON.parse(redactSecrets(JSON.stringify(context)).slice(0, 1000)) : {},
        lesson_id: lesson_id ? String(lesson_id).slice(0, 200) : null,
        contact: contact ? String(contact).slice(0, 200) : null,
        consent: VALID_CONSENT.includes(consent) ? consent : "private_only",
        ts: ts || new Date().toISOString(),
        received_at: new Date().toISOString(),
      };

      // Store intake record
      await env.MISAKANET_KV.put(`intake:${intakeId}`, JSON.stringify(record), { expirationTtl: 7776000 });

      // Record demand signal for the task family (maps type to family)
      const FAMILY_MAP = { diagnostic: "unclassified", lesson_candidate: "lesson-feedback", friction: "unclassified", bug: "bug-report", node_join: "unclassified" };
      const family = FAMILY_MAP[type] || "unclassified";
      const demandKey = `demand:family:${family}`;
      const demandRaw = await env.MISAKANET_KV.get(demandKey, "json");
      const demand = demandRaw && typeof demandRaw === "object" ? demandRaw : { days: {} };
      const day = new Date().toISOString().slice(0, 10);
      demand.days[day] = demand.days[day] || { reasons: {}, count: 0 };
      demand.days[day].count++;
      const reasonKey = String(message).slice(0, 64);
      demand.days[day].reasons[reasonKey] = (demand.days[day].reasons[reasonKey] || 0) + 1;
      await env.MISAKANET_KV.put(demandKey, JSON.stringify(demand), { expirationTtl: 2592000 });

      console.log(`Intake ${intakeId}: type=${type} source=${source} family=${family}`);
      return jsonResponse({ accepted: true, intake_id: intakeId, consent: record.consent });
    }

    // GET /api/insights/demand-board — public aggregate view of intake clusters
    if (request.method === "GET" && url.pathname === "/api/insights/demand-board") {
      if (!env.MISAKANET_KV) return jsonResponse({ success: true, available: false, summary: [] });

      const DEMAND_PREFIX = "demand:family:";
      const WINDOW_DAYS = 30;
      const cutoff = Date.now() - WINDOW_DAYS * 86_400_000;
      const summary = [];

      const families = [
        "github-auth", "npm-publish", "cloudflare-worker", "mcp-registry",
        "glama-release", "python-env", "database-lock", "crawler-block",
        "agent-tooling", "lesson-feedback", "bug-report", "unclassified",
      ];

      for (const family of families) {
        const record = await env.MISAKANET_KV.get(`${DEMAND_PREFIX}${family}`, "json");
        if (!record || !record.days) continue;

        let total30d = 0, total7d = 0, lastSeen = null;
        for (const [day, bucket] of Object.entries(record.days)) {
          const dayTime = new Date(`${day}T00:00:00Z`).getTime();
          const dayCount = Object.values(bucket.reasons || {}).reduce((s, r) => s + (r.count || 0), 0);
          if (dayTime >= cutoff) total30d += dayCount;
          if (dayTime >= Date.now() - 7 * 86_400_000) total7d += dayCount;
          if (dayCount > 0 && (!lastSeen || day > lastSeen)) lastSeen = day;
        }

        if (total30d > 0) {
          summary.push({ taskFamily: family, unsolved7d: total7d, unsolved30d: total30d, lastSeen });
        }
      }

      summary.sort((a, b) => b.unsolved30d - a.unsolved30d);
      return jsonResponse({ success: true, available: true, windowDays: WINDOW_DAYS, summary });
    }

    // GET /api/github/* - authenticated GitHub API proxy for the org frontend.
    // Keep this before the HTML landing page; otherwise the frontend receives
    // HTML and fails with: Unexpected token '<' while parsing JSON.
    if (request.method === "GET" && url.pathname.startsWith("/api/github/")) {
      const token = env.REGISTER_TOKEN;
      if (!token) return jsonResponse({ error: "REGISTER_TOKEN not configured" }, 500);

      const ghPath = url.pathname.slice("/api/github/".length);
      const repoApiPrefix = `repos/${REPO}/`;
      if (!ghPath) return jsonResponse({ error: "Missing GitHub API path" }, 400);
      if (!ghPath.startsWith(repoApiPrefix)) return jsonResponse({ error: "Forbidden" }, 403);

      const resp = await fetch(`${GITHUB_API}/${ghPath}${url.search}`, {
        headers: {
          Authorization: `Bearer ${token}`,
          "User-Agent": "MisakaNet-Worker",
          Accept: "application/vnd.github.v3+json",
        },
      });

      return new Response(resp.body, {
        status: resp.status,
        headers: {
          "content-type": resp.headers.get("content-type") || "application/json",
          ...CORS_HEADERS,
          "Cache-Control": resp.ok ? "public, max-age=30" : "no-store",
          "X-GitHub-Proxy": "misakanet",
        },
      });
    }

    // API routes must never fall through to the HTML landing page.
    if (request.method === "GET" && url.pathname.startsWith("/api/")) {
      return jsonResponse({ error: "Not found" }, 404);
    }

    // Catch-all GET — landing page (must be after all API routes)
    if (request.method === "GET") {
      return new Response(`<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>MisakaNet Register Proxy</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #0d1117; color: #e6edf3; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; }
  .card { max-width: 500px; text-align: center; background: #161b22; border: 1px solid #30363d; border-radius: 16px; padding: 40px; }
  h1 { color: #f0c040; font-size: 28px; margin-bottom: 8px; }
  p { color: #8b949e; font-size: 14px; line-height: 1.7; }
  code { background: #0d1117; padding: 3px 8px; border-radius: 4px; font-size: 13px; color: #7ee787; }
  .btn { display: inline-block; margin-top: 20px; padding: 12px 24px; background: #238636; color: white; text-decoration: none; border-radius: 8px; font-weight: 600; }
</style></head>
<body>
<div class="card">
  <h1>⚡ MisakaNet</h1>
  <p>这是御坂网络的注册代理端点。</p>
  <p>前端表单通过此端点提交注册请求，<br>GitHub Token <strong>不会暴露给浏览器</strong>。</p>
  <p style="margin-top:16px;font-size:12px;color:#484f58;">
    用法: <code>POST /</code> 携带 <code>{"agent_type":"...", "node_name":"..."}</code>
  </p>
  <a class="btn" href="https://misakanet.org/">← 返回注册页面</a>
</div>
</body>
</html>`, {
        status: 200,
        headers: { "content-type": "text/html;charset=utf-8" },
      });
    }

    if (request.method !== "POST") {
      return jsonResponse({ error: "Method not allowed" }, 405);
    }

    if (!["/", "/api/register", "/api/register/"].includes(url.pathname)) {
      return jsonResponse({ error: "Not found" }, 404);
    }

    // 定期清理 rateMap
    if (Math.random() < 0.02) cleanRateMap();

    // IP 限流
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    const now = Date.now();
    const last = rateMap.get(ip) || 0;
    if (now - last < RATE_LIMIT_WINDOW) {
      const remaining = Math.ceil((RATE_LIMIT_WINDOW - (now - last)) / 1000);
      return jsonResponse({ error: `Rate limited. Try again in ${remaining}s.` }, 429);
    }
    rateMap.set(ip, now);

    // 解析请求体（限制大小）
    let body;
    try {
      if (parseInt(request.headers.get("content-length") || "0") > 10000) {
        return jsonResponse({ error: "Request too large" }, 413);
      }
      body = await request.json();
    } catch {
      return jsonResponse({ error: "Invalid JSON" }, 400);
    }

    // 校验必填字段 + 输入清洗
    if (!body.agent_type) {
      return jsonResponse({ error: "Missing agent_type" }, 400);
    }
    const agentType = sanitizeIdentifier(body.agent_type, MAX_AGENT_TYPE);
    if (!agentType) {
      return jsonResponse({ error: "Invalid agent_type" }, 400);
    }
    const nodeName = sanitizeIdentifier(body.node_name, MAX_NODE_NAME);

    const token = env.REGISTER_TOKEN;
    if (!token) {
      return jsonResponse({ error: "Server misconfigured" }, 500);
    }

    // 构造 Issue
    const nameLine = nodeName ? `\n注册名称: **${nodeName}**` : "";
    const agentLine = `\nAgent 类型: **${agentType.toUpperCase()}**`;
    const issueTitle = nodeName ? `join: ${nodeName}` : "join";
    const issueBody = `## 🧠 通过公开通道加入御坂网络${nameLine}${agentLine}\n\n已确认条款。`;

    // 创建 Issue（设 15s 超时，防止 Worker 挂死）
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    let resp;
    try {
      resp = await fetch(`${GITHUB_API}/repos/${REPO}/issues`, {
        method: "POST",
        signal: controller.signal,
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          Accept: "application/vnd.github.v3+json",
          "User-Agent": "MisakaNet-Worker",
        },
        body: JSON.stringify({
          title: issueTitle,
          body: issueBody,
          labels: ["registration"],
        }),
      });
    } catch (err) {
      clearTimeout(timeoutId);
      if (err.name === "AbortError") {
        return jsonResponse({ error: "GitHub API timeout" }, 504);
      }
      return jsonResponse({ error: "GitHub API error: " + err.message }, 502);
    }
    clearTimeout(timeoutId);

    const data = await resp.json();
    if (!resp.ok) {
      return jsonResponse({ error: data.message || "GitHub API error" }, resp.status);
    }

    return jsonResponse({
      success: true,
      issue_url: data.html_url,
      issue_number: data.number,
      message: "Registration issue created. Counter, avatar, and welcome will be handled by the registration workflow.",
    });
  },

  async scheduled(controller, env, ctx) {
    ctx.waitUntil(runKeepaliveSweep(controller.cron));
  },
};

// Named exports for unit tests only (workers/mcp-remote.test.mjs). Wrangler
// deploys this file for its default export; the extra exports are inert there.
export {
  MCP_PATH,
  MCP_TOOLS,
  MCP_DEFAULT_PROTOCOL,
  MCP_SUPPORTED_PROTOCOLS,
  MCP_FALLBACK_VERSION,
  decodeBase64Utf8,
  handleMcpRequest,
  mcpMethodNotAllowed,
  mcpOriginAllowed,
  mcpRankLessons,
  mcpSafeLessonPath,
  mcpTimingSafeEqual,
  mcpTokenize,
};
