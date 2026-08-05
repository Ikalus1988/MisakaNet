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

// ── GitHub API fetch with token ──
async function fetchFromGitHub(token, path, ref = "data") {
  const url = `${GITHUB_API}/repos/${REPO}/contents/${path}?ref=${encodeURIComponent(ref)}`;
  const resp = await fetch(url, {
    headers: { Authorization: `Bearer ${token}`, "User-Agent": "MisakaNet-Worker", Accept: "application/vnd.github.v3+json" },
  });
  if (!resp.ok) throw new Error(`GitHub API ${resp.status}`);
  const data = await resp.json();
  if (!data.content || data.encoding !== "base64") throw new Error("Unexpected GitHub response");
  return JSON.parse(atob(data.content));
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
// Unsolved failure map (Issue #788)
//
// Shows which failure families have no effective lesson. Aggregate-only by
// construction: a query is classified into a task family in memory and then
// discarded — no raw query, prompt, log, path, or identifier is ever written.
// ═══════════════════════════════════════════════════════════════════════════

const UNSOLVED_KV_PREFIX = "unsolved:family:";
const UNSOLVED_STALE_PREFIX = "unsolved:lesson:";
const UNSOLVED_WINDOW_DAYS = 30;
const UNSOLVED_MAX_STALE_LESSONS = 20;
const UNSOLVED_LOW_SCORE = 0.35; // matches the frontend's "low confidence" band

// Reason enum — the only values that may ever reach storage or output.
const UNSOLVED_REASONS = ["no_match", "low_confidence", "not_helpful", "outdated_lesson", "missing_runtime_path"];

// Task families and the keyword clusters that derive them. Labels come from
// this table, never from user input.
const UNSOLVED_FAMILIES = [
  ["github-auth", ["github", "gh auth", "401", "403", "permission denied", "pat", "token expired", "dco", "sign-off", "signoff"]],
  ["npm-publish", ["npm", "yarn", "pnpm", "eotp", "publish", "registry", "package.json"]],
  ["cloudflare-worker", ["cloudflare", "worker", "wrangler", "kv namespace", "durable object", "pages"]],
  ["mcp-registry", ["mcp", "model context protocol", "stdio", "tools/list", "tools/call", "mcp server"]],
  ["glama-release", ["glama", "listing", "release", "changelog", "tag"]],
  ["python-env", ["pip", "venv", "virtualenv", "conda", "poetry", "modulenotfounderror", "importerror", "pytest", "python"]],
  ["database-lock", ["database is locked", "database locked", "sqlite", "deadlock", "lock timeout", "busy timeout", "postgres", "mysql"]],
  ["crawler-block", ["crawler", "scrape", "robots.txt", "cloudflare challenge", "captcha", "rate limit", "429", "blocked"]],
  ["agent-tooling", ["agent", "claude", "cursor", "copilot", "codex", "aider", "prompt", "context window", "tool call"]],
  ["ci-pipeline", ["ci", "github actions", "workflow", "runner", "pipeline", "build failed", "job failed"]],
  ["encoding-locale", ["gbk", "utf-8", "unicodedecodeerror", "encoding", "locale", "mojibake", "codec"]],
  ["container-deploy", ["docker", "container", "ghcr", "image", "kubernetes", "k8s", "crashloopbackoff", "compose"]],
];
const UNSOLVED_FALLBACK_FAMILY = "unclassified";
const UNSOLVED_FAMILY_WHITELIST = [...UNSOLVED_FAMILIES.map(([family]) => family), UNSOLVED_FALLBACK_FAMILY];

// Derives a family label from query text. The text is never returned or stored:
// only the label leaves this function.
function classifyTaskFamily(text) {
  const haystack = String(text || "").toLowerCase();
  if (!haystack.trim()) return UNSOLVED_FALLBACK_FAMILY;

  let best = UNSOLVED_FALLBACK_FAMILY;
  let bestScore = 0;
  for (const [family, keywords] of UNSOLVED_FAMILIES) {
    let score = 0;
    for (const keyword of keywords) {
      // Multi-word keywords are stronger evidence than single tokens.
      if (haystack.includes(keyword)) score += keyword.includes(" ") ? 2 : 1;
    }
    if (score > bestScore) {
      best = family;
      bestScore = score;
    }
  }
  return best;
}

function normalizeUnsolvedReason(reason) {
  return UNSOLVED_REASONS.includes(reason) ? reason : "no_match";
}

function unsolvedDay(date = new Date()) {
  return date.toISOString().slice(0, 10);
}

function pruneUnsolvedDays(days, windowDays = UNSOLVED_WINDOW_DAYS) {
  const cutoff = Date.now() - windowDays * 86_400_000;
  for (const day of Object.keys(days)) {
    if (new Date(`${day}T00:00:00Z`).getTime() < cutoff) delete days[day];
  }
  return days;
}

// Writes one aggregate signal. Callers must pass a derived family and an enum
// reason — never raw text.
async function recordUnsolvedSearch(env, { taskFamily, reason, day } = {}) {
  if (!env.MISAKANET_KV) return null;
  const family = UNSOLVED_FAMILY_WHITELIST.includes(taskFamily) ? taskFamily : UNSOLVED_FALLBACK_FAMILY;
  const normalizedReason = normalizeUnsolvedReason(reason);
  const bucketDay = day || unsolvedDay();
  const kvKey = `${UNSOLVED_KV_PREFIX}${family}`;

  const stored = await env.MISAKANET_KV.get(kvKey, "json");
  const record = stored && typeof stored === "object" && stored.days ? stored : { days: {} };
  pruneUnsolvedDays(record.days);

  const dayBucket = record.days[bucketDay] || (record.days[bucketDay] = { reasons: {} });
  dayBucket.reasons[normalizedReason] = (dayBucket.reasons[normalizedReason] || 0) + 1;

  await env.MISAKANET_KV.put(kvKey, JSON.stringify(record), { expirationTtl: (UNSOLVED_WINDOW_DAYS + 7) * 86_400 });
  return { taskFamily: family, reason: normalizedReason, day: bucketDay };
}

// Tracks lessons that keep drawing not-helpful feedback. Lesson IDs are public
// repository identifiers, not user data.
async function recordStaleLesson(env, lessonId, day) {
  if (!env.MISAKANET_KV || !lessonId) return;
  const kvKey = `${UNSOLVED_STALE_PREFIX}${lessonId}`;
  const stored = await env.MISAKANET_KV.get(kvKey, "json");
  const record = stored && typeof stored === "object" && stored.days ? stored : { days: {} };
  pruneUnsolvedDays(record.days);
  const bucketDay = day || unsolvedDay();
  record.days[bucketDay] = (record.days[bucketDay] || 0) + 1;
  await env.MISAKANET_KV.put(kvKey, JSON.stringify(record), { expirationTtl: (UNSOLVED_WINDOW_DAYS + 7) * 86_400 });
}

function sumUnsolvedDays(days, windowDays) {
  const cutoff = Date.now() - windowDays * 86_400_000;
  let total = 0;
  const reasons = {};
  let lastSeen = null;

  for (const [day, bucket] of Object.entries(days || {})) {
    const dayTime = new Date(`${day}T00:00:00Z`).getTime();
    const entries = typeof bucket === "number" ? { total: bucket } : (bucket.reasons || {});
    const dayCount = Object.values(entries).reduce((sum, n) => sum + (n || 0), 0);
    if (dayCount > 0 && (!lastSeen || day > lastSeen)) lastSeen = day;
    if (dayTime < cutoff) continue;
    total += dayCount;
    for (const [reason, count] of Object.entries(entries)) {
      reasons[reason] = (reasons[reason] || 0) + count;
    }
  }
  return { total, reasons, lastSeen };
}

async function buildUnsolvedMap(env) {
  const families = [];
  for (const family of UNSOLVED_FAMILY_WHITELIST) {
    const record = await env.MISAKANET_KV.get(`${UNSOLVED_KV_PREFIX}${family}`, "json");
    if (!record || !record.days) continue;
    const { total: unsolved30d, reasons, lastSeen } = sumUnsolvedDays(record.days, UNSOLVED_WINDOW_DAYS);
    if (unsolved30d <= 0) continue;
    const { total: unsolved7d } = sumUnsolvedDays(record.days, 7);
    families.push({ taskFamily: family, unsolved7d, unsolved30d, reasons, lastSeen });
  }
  families.sort((a, b) => b.unsolved30d - a.unsolved30d || a.taskFamily.localeCompare(b.taskFamily));

  const staleLessons = [];
  let cursor;
  do {
    const listed = await env.MISAKANET_KV.list({ prefix: UNSOLVED_STALE_PREFIX, cursor });
    for (const key of listed.keys || []) {
      const record = await env.MISAKANET_KV.get(key.name, "json");
      if (!record || !record.days) continue;
      const { total: notHelpful30d, lastSeen } = sumUnsolvedDays(record.days, UNSOLVED_WINDOW_DAYS);
      if (notHelpful30d <= 0) continue;
      staleLessons.push({ lessonId: key.name.slice(UNSOLVED_STALE_PREFIX.length), notHelpful30d, lastSeen });
    }
    cursor = listed.list_complete ? null : listed.cursor;
  } while (cursor);
  staleLessons.sort((a, b) => b.notHelpful30d - a.notHelpful30d || a.lessonId.localeCompare(b.lessonId));

  return { families, staleLessons: staleLessons.slice(0, UNSOLVED_MAX_STALE_LESSONS) };
}

// GET /api/insights/unsolved-map — public, aggregate-only.
async function handleUnsolvedMap(env) {
  const available = !!env.MISAKANET_KV;
  const data = available ? await buildUnsolvedMap(env) : { families: [], staleLessons: [] };
  return jsonResponse({
    success: true,
    available,
    windowDays: UNSOLVED_WINDOW_DAYS,
    taskFamilies: UNSOLVED_FAMILY_WHITELIST,
    reasons: UNSOLVED_REASONS,
    families: data.families,
    staleLessons: data.staleLessons,
    meta: { privacy: "aggregate-only", raw_query: false, prompts: false, logs: false, paths: false, pii: false },
  });
}

// POST /api/search-signal — records that a search went unsolved. The query is
// classified here and dropped; only the derived family + reason are persisted.
async function handleSearchSignal(request, env) {
  if (!env.MISAKANET_KV) return jsonResponse({ error: "KV not configured" }, 503);

  if (parseInt(request.headers.get("content-length") || "0", 10) > 4096) {
    return jsonResponse({ error: "Request too large" }, 413);
  }

  // IP rate limit: 30 signals per IP per minute.
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const rateKey = `rate:signal:${ip}`;
  const rateCount = parseInt((await env.MISAKANET_KV.get(rateKey, "text")) || "0", 10) || 0;
  if (rateCount >= 30) return jsonResponse({ error: "Rate limited. Try again later." }, 429);
  await env.MISAKANET_KV.put(rateKey, String(rateCount + 1), { expirationTtl: 60 });

  let body;
  try { body = await request.json(); } catch { return jsonResponse({ error: "Invalid JSON" }, 400); }

  const { query, result_count: resultCount, top_score: topScore, reason, lesson_id: lessonId } = body || {};
  if (typeof query !== "string" || !query.trim()) return jsonResponse({ error: "Missing 'query'" }, 400);

  // Solved searches are not recorded at all — the map only tracks gaps.
  const count = Number.isFinite(Number(resultCount)) ? Number(resultCount) : 0;
  const score = Number.isFinite(Number(topScore)) ? Number(topScore) : 0;
  let derivedReason = reason;
  if (!UNSOLVED_REASONS.includes(derivedReason)) {
    if (count <= 0) derivedReason = "no_match";
    else if (score < UNSOLVED_LOW_SCORE) derivedReason = "low_confidence";
    else return jsonResponse({ recorded: false, reason: "search_was_solved" });
  }

  const recorded = await recordUnsolvedSearch(env, {
    taskFamily: classifyTaskFamily(query),
    reason: derivedReason,
  });
  if (derivedReason === "not_helpful" && lessonId) {
    await recordStaleLesson(env, sanitizeIdentifier(lessonId, 200));
  }

  // Log the derived label only — never the query itself.
  console.log(`[unsolved] ${recorded.taskFamily} ${recorded.reason}`);
  return jsonResponse({ recorded: true, taskFamily: recorded.taskFamily, reason: recorded.reason });
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

        // Unsolved failure map (#788): a not-helpful verdict means the lesson
        // did not close the gap. Aggregate-only — the query is classified and
        // dropped, and only the public lesson ID is counted.
        if (feedback === "irrelevant" || feedback === "too_basic") {
          await recordUnsolvedSearch(env, { taskFamily: classifyTaskFamily(query), reason: "not_helpful" });
          await recordStaleLesson(env, sanitizeIdentifier(record.lesson_id, 200));
        }
      }

      return jsonResponse({ accepted: accepted.length });
    }

    // POST /api/search-signal — unsolved-search intake for the failure map (#788)
    if (request.method === "POST" && url.pathname === "/api/search-signal") {
      return handleSearchSignal(request, env);
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

    // GET /api/insights/unsolved-map — public aggregate failure map (#788)
    if (request.method === "GET" && url.pathname === "/api/insights/unsolved-map") {
      return handleUnsolvedMap(env);
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

// Named exports for unit tests only (workers/unsolved-map.test.mjs). Wrangler
// deploys this file for its default export; the extra exports are inert there.
export {
  UNSOLVED_FAMILY_WHITELIST,
  UNSOLVED_REASONS,
  UNSOLVED_WINDOW_DAYS,
  buildUnsolvedMap,
  classifyTaskFamily,
  handleSearchSignal,
  handleUnsolvedMap,
  recordStaleLesson,
  recordUnsolvedSearch,
};
