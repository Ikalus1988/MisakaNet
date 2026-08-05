// MisakaNet Register + Data Proxy — Cloudflare Worker
// 部署方式: https://dash.cloudflare.com/ → Workers & Pages
// 环境变量: REGISTER_TOKEN (GitHub PAT, 需 contents+issues write)
//          MAINTAINER_KEY (可选, 保护 /api/insights/demand-map)
// KV Namespace: MISAKANET_KV (可选，用于缓存数据代理响应 + 需求看板聚合)

const REPO = "Ikalus1988/MisakaNet";
const GITHUB_API = "https://api.github.com";

// ── IP 限流 (for POST registration) ──
const RATE_LIMIT_WINDOW = 30_000;
const RATE_MAP_CLEAN_INTERVAL = 300_000;
const rateMap = new Map();

function cleanRateMap() {
  const cutoff = Date.now() - RATE_LIMIT_WINDOW;
  for (const [ip, time] of rateMap) {
    if (time < cutoff) rateMap.delete(ip);
  }
}

// ── 输入校验 ──
const MAX_AGENT_TYPE = 30;
const MAX_NODE_NAME = 50;
const MAX_INVITE_CODE = 30;

// ── 数据代理缓存 TTL (30 秒，与前端 localStorage 缓存一致) ──
const PROXY_CACHE_TTL = 30_000;

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...CORS_HEADERS },
  });
}

function sanitizeIdentifier(val, maxLen) {
  if (!val) return "";
  if (val.length > maxLen) val = val.slice(0, maxLen);
  return val.replace(/[^\w\u4e00-\u9fa5\-]/g, "");
}

// -- Demand board (Issue #591) --
// Aggregate-only view of repeatedly-unsolved failure families. Data is written by
// recordUnsolvedSignal(), which the intake endpoint (#589) and classifier (#575)
// call once a report/feedback/MCP-miss can't be matched to an existing lesson.
const TASK_FAMILY_WHITELIST = [
  "github-auth", "npm-publish", "cloudflare-worker", "mcp-registry",
  "glama-release", "python-env", "database-lock", "crawler-block",
  "agent-tooling", "unclassified",
];
const DEMAND_WINDOW_DAYS = 30;
const DEMAND_KV_PREFIX = "demand:family:";
const DEMAND_ACTION_URL = "https://github.com/Ikalus1988/MisakaNet/issues/new?template=lesson-feedback.yml";
const DEMAND_MAX_SOURCES_PER_BUCKET = 50;

function normalizeTaskFamily(taskFamily) {
  return TASK_FAMILY_WHITELIST.includes(taskFamily) ? taskFamily : "unclassified";
}

function isoDay(date = new Date()) {
  return date.toISOString().slice(0, 10);
}

// Never store the raw source identifier -- only a truncated one-way hash, so
// distinct-source counts stay possible without keeping anything re-identifiable.
async function hashSourceId(sourceId) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(String(sourceId)));
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("").slice(0, 16);
}

function timingSafeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length || a.length === 0) return false;
  let mismatch = 0;
  for (let i = 0; i < a.length; i++) mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return mismatch === 0;
}

// Records one unsolved signal (no matching lesson / irrelevant / too_basic / MCP miss /
// journey friction, ...) into a per-family KV bucket. Aggregate-only by construction:
// callers must not pass raw query text, prompts, or personal identifiers as `reason`.
async function recordUnsolvedSignal(env, { taskFamily, reason, sourceId, day } = {}) {
  if (!env.MISAKANET_KV) return;
  const family = normalizeTaskFamily(taskFamily);
  const bucketDay = day || isoDay();
  const reasonKey = String(reason || "unspecified").slice(0, 64);
  const kvKey = `${DEMAND_KV_PREFIX}${family}`;

  const stored = await env.MISAKANET_KV.get(kvKey, "json");
  const record = stored && typeof stored === "object" ? stored : { days: {} };
  record.days ||= {};

  const cutoff = Date.now() - DEMAND_WINDOW_DAYS * 86_400_000;
  for (const existingDay of Object.keys(record.days)) {
    if (new Date(`${existingDay}T00:00:00Z`).getTime() < cutoff) delete record.days[existingDay];
  }

  const dayBucket = record.days[bucketDay] || (record.days[bucketDay] = { reasons: {} });
  const reasonBucket = dayBucket.reasons[reasonKey] || (dayBucket.reasons[reasonKey] = { count: 0, sources: [] });
  reasonBucket.count += 1;
  if (sourceId) {
    const hashed = await hashSourceId(sourceId);
    if (reasonBucket.sources.length < DEMAND_MAX_SOURCES_PER_BUCKET && !reasonBucket.sources.includes(hashed)) {
      reasonBucket.sources.push(hashed);
    }
  }

  await env.MISAKANET_KV.put(kvKey, JSON.stringify(record));
}

function sumUnsolvedWindow(days, windowDays) {
  const cutoff = Date.now() - windowDays * 86_400_000;
  let total = 0;
  let lastSeen = null;
  for (const [day, bucket] of Object.entries(days || {})) {
    const dayCount = Object.values(bucket.reasons || {}).reduce((sum, r) => sum + (r.count || 0), 0);
    if (dayCount > 0 && (lastSeen === null || day > lastSeen)) lastSeen = day;
    if (new Date(`${day}T00:00:00Z`).getTime() >= cutoff) total += dayCount;
  }
  return { total, lastSeen };
}

async function buildDemandBoardSummary(env) {
  const summary = [];
  for (const family of TASK_FAMILY_WHITELIST) {
    const record = await env.MISAKANET_KV.get(`${DEMAND_KV_PREFIX}${family}`, "json");
    if (!record || !record.days) continue;
    const { total: unsolved30d, lastSeen } = sumUnsolvedWindow(record.days, DEMAND_WINDOW_DAYS);
    if (unsolved30d <= 0) continue;
    const { total: unsolved7d } = sumUnsolvedWindow(record.days, 7);
    summary.push({ taskFamily: family, unsolved7d, unsolved30d, lastSeen, actionUrl: DEMAND_ACTION_URL });
  }
  summary.sort((a, b) => b.unsolved30d - a.unsolved30d);
  return summary;
}

async function buildDemandMapBuckets(env) {
  const buckets = [];
  for (const family of TASK_FAMILY_WHITELIST) {
    const record = await env.MISAKANET_KV.get(`${DEMAND_KV_PREFIX}${family}`, "json");
    if (!record || !record.days) continue;
    for (const [bucketDay, dayBucket] of Object.entries(record.days)) {
      for (const [unsolvedReason, reasonBucket] of Object.entries(dayBucket.reasons || {})) {
        buckets.push({
          taskFamily: family,
          bucketDay,
          unsolvedReason,
          unsolvedCount: reasonBucket.count || 0,
          distinctSourceCount: (reasonBucket.sources || []).length,
        });
      }
    }
  }
  buckets.sort((a, b) => (a.bucketDay === b.bucketDay ? 0 : a.bucketDay < b.bucketDay ? 1 : -1));
  return buckets;
}

// GET /api/insights/demand-board -- public, aggregate-only. No raw query, prompt, log,
// file path, or personal identifier may ever appear in this response.
async function handleDemandBoard(env) {
  const available = !!env.MISAKANET_KV;
  return jsonResponse({
    success: true,
    available,
    windowDays: DEMAND_WINDOW_DAYS,
    summary: available ? await buildDemandBoardSummary(env) : [],
    meta: { r_level: "R1_descriptive", privacy: "aggregate-only", raw_query: false, pii: false },
  });
}

// GET /api/insights/demand-map -- maintainer-only bucket breakdown, gated on MAINTAINER_KEY.
async function handleDemandMap(request, env) {
  if (!env.MAINTAINER_KEY) {
    return jsonResponse({ error: "Maintainer map not configured" }, 503);
  }
  const providedKey = request.headers.get("X-Maintainer-Key") || "";
  if (!timingSafeEqual(providedKey, env.MAINTAINER_KEY)) {
    return jsonResponse({ error: "Unauthorized" }, 401);
  }
  if (!env.MISAKANET_KV) {
    return jsonResponse({ buckets: [] });
  }
  return jsonResponse({ buckets: await buildDemandMapBuckets(env) });
}

// ── 从 GitHub API (带 Token) 获取文件内容 ──
async function fetchFromGitHub(token, path, ref = "data") {
  const url = `${GITHUB_API}/repos/${REPO}/contents/${path}?ref=${encodeURIComponent(ref)}`;
  const resp = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      "User-Agent": "MisakaNet-Worker",
      Accept: "application/vnd.github.v3+json",
    },
  });
  if (!resp.ok) {
    const errBody = await resp.text().catch(() => "");
    throw new Error(`GitHub API ${resp.status}: ${errBody.slice(0, 200)}`);
  }
  const data = await resp.json();
  // GitHub API 对文件返回 Base64 编码的 content
  if (!data.content || data.encoding !== "base64") {
    throw new Error(`Unexpected response format from GitHub API`);
  }
  try {
    return JSON.parse(atob(data.content));
  } catch (e) {
    throw new Error(`Failed to parse file content: ${e.message}`);
  }
}

// ── KV 缓存封装 ──
async function getWithCache(env, cacheKey, fetchFn) {
  // 尝试 KV 缓存
  if (env.MISAKANET_KV) {
    try {
      const cached = await env.MISAKANET_KV.get(cacheKey, "json");
      if (cached && typeof cached === "object" && cached.ts) {
        if (Date.now() - cached.ts < PROXY_CACHE_TTL) {
          return cached.data;
        }
      }
    } catch { /* KV unavailable, bypass cache */ }
  }

  // 没有 KV 或缓存过期，重新获取
  const data = await fetchFn();

  // 写入 KV 缓存
  if (env.MISAKANET_KV) {
    try {
      await env.MISAKANET_KV.put(
        cacheKey,
        JSON.stringify({ data, ts: Date.now() }),
        { expirationTtl: Math.ceil(PROXY_CACHE_TTL / 1000) + 30 }
      );
    } catch { /* cache write best-effort */ }
  }

  return data;
}

// ── API 路由处理 ──
async function handleApiRequest(pathWithQuery, env, request) {
  // 分离路径与查询参数
  const qIdx = pathWithQuery.indexOf("?");
  const pathname = qIdx >= 0 ? pathWithQuery.slice(0, qIdx) : pathWithQuery;
  const search = qIdx >= 0 ? pathWithQuery.slice(qIdx) : "";

  // 需求看板端点不依赖 REGISTER_TOKEN（GitHub 代理专用），单独处理
  if (pathname === "/api/insights/demand-board") {
    return handleDemandBoard(env);
  }
  if (pathname === "/api/insights/demand-map") {
    return handleDemandMap(request, env);
  }

  const token = env.REGISTER_TOKEN;
  if (!token) {
    return jsonResponse({ error: "REGISTER_TOKEN not configured on server" }, 500);
  }

  switch (pathname) {
    case "/api/counter":
    case "/api/counter.json": {
      // 优先从 KV 读取（邮件/Web 注册的最新计数），fallback 到 GitHub data 分支
      const data = await getWithCache(env, "proxy:counter", async () => {
        if (env.MISAKANET_KV) {
          const kvCounter = await env.MISAKANET_KV.get("node_counter", "text");
          if (kvCounter) {
            return { current: parseInt(kvCounter), updated: new Date().toISOString().slice(0, 10) };
          }
        }
        return fetchFromGitHub(token, "data/counter.json");
      });
      return jsonResponse(data);
    }

    case "/api/lessons":
    case "/api/lessons.json": {
      const data = await getWithCache(env, "proxy:lessons", () =>
        fetchFromGitHub(token, "lessons.json", "data")
      );
      return jsonResponse(data);
    }

    case "/api/health":
      return jsonResponse({
        status: "ok",
        hasToken: !!token,
        hasKV: !!env.MISAKANET_KV,
        timestamp: new Date().toISOString(),
      });

    case "/api/helpful": {
      // GET /api/helpful?lesson_id=<id> — return helpful count for a lesson
      if (!env.MISAKANET_KV) {
        return jsonResponse({ error: "KV not configured" }, 503);
      }
      const params = new URLSearchParams(search);
      const lessonId = sanitizeIdentifier(params.get("lesson_id"), 100);
      if (!lessonId) {
        return jsonResponse({ error: "Missing lesson_id" }, 400);
      }
      const kvKey = `helpful:${lessonId}`;
      const raw = await env.MISAKANET_KV.get(kvKey, "text");
      const count = raw ? parseInt(raw, 10) || 0 : 0;
      return jsonResponse({ lesson_id: lessonId, count });
    }

    default:
      // 通用 GitHub API 代理: /api/github/* → api.github.com/*
      if (pathname.startsWith("/api/github/")) {
        const ghPath = pathname.replace("/api/github/", "");
        const ghUrl = `${GITHUB_API}/${ghPath}${search}`;
        const resp = await fetch(ghUrl, {
          headers: { Authorization: `Bearer ${token}`, "User-Agent": "MisakaNet-Worker", Accept: "application/vnd.github.v3+json" },
        });
        const data = await resp.json();
        return new Response(JSON.stringify(data), {
          status: resp.status,
          headers: { "content-type": "application/json", ...CORS_HEADERS, "X-GitHub-Proxy": "misakanet" },
        });
      }
      return jsonResponse({ error: "Not found" }, 404);
  }
}

// ── 静态着陆页 ──
function serveLandingPage() {
  return new Response(`<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>MisakaNet Register Proxy</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #0d1117; color: #e6edf3; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; }
  .card { max-width: 540px; text-align: center; background: #161b22; border: 1px solid #30363d; border-radius: 16px; padding: 40px; }
  h1 { color: #f0c040; font-size: 28px; margin-bottom: 8px; }
  p { color: #8b949e; font-size: 14px; line-height: 1.7; }
  code { background: #0d1117; padding: 3px 8px; border-radius: 4px; font-size: 13px; color: #7ee787; }
  .btn { display: inline-block; margin-top: 20px; padding: 12px 24px; background: #238636; color: white; text-decoration: none; border-radius: 8px; font-weight: 600; }
  .endpoints { text-align: left; margin-top: 20px; background: #0d1117; border-radius: 8px; padding: 16px; }
  .endpoints dt { color: #f0c040; font-family: monospace; margin-top: 8px; }
  .endpoints dd { color: #8b949e; font-size: 13px; margin-left: 0; }
</style></head>
<body>
<div class="card">
  <h1>⚡ MisakaNet</h1>
  <p>御坂网络注册代理与数据缓存端点。</p>
  <p style="margin-top:16px;font-size:12px;color:#484f58;">
    注册: <code>POST /</code> → <code>{"agent_type":"...", "node_name":"..."}</code><br>
    API: <code>GET /api/counter</code> · <code>GET /api/lessons</code> · <code>GET /api/health</code>
  </p>
  <div class="endpoints">
    <dl>
      <dt>POST /</dt>
      <dd>注册新节点 (IP 限流 1 次/30s，通过 GitHub API 创建 Issue + 更新计数器)</dd>
      <dt>GET /api/counter</dt>
      <dd>获取节点计数器 (GitHub Token 代理 + KV 缓存 30s)</dd>
      <dt>GET /api/lessons</dt>
      <dd>获取 lessons 索引 (GitHub Token 代理 + KV 缓存 30s)</dd>
      <dt>GET /api/health</dt>
      <dd>健康检查 (返回 Token / KV 配置状态)</dd>
    </dl>
  </div>
  <a class="btn" href="https://ikalus1988.github.io/MisakaNet/">← 返回注册页面</a>
</div>
</body>
</html>`, {
    status: 200,
    headers: { "content-type": "text/html;charset=utf-8" },
  });
}

// ── 注册处理 ──
async function handleRegistration(request, env) {
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

  // 解析请求体
  let body;
  try {
    if (request.headers.get("content-length") > 10000) {
      return jsonResponse({ error: "Request too large" }, 413);
    }
    body = await request.json();
  } catch {
    return jsonResponse({ error: "Invalid JSON" }, 400);
  }

  // 校验
  if (!body.agent_type) {
    return jsonResponse({ error: "Missing agent_type" }, 400);
  }
  const agentType = sanitizeIdentifier(body.agent_type, MAX_AGENT_TYPE);
  if (!agentType) {
    return jsonResponse({ error: "Invalid agent_type" }, 400);
  }
  const nodeName = sanitizeIdentifier(body.node_name, MAX_NODE_NAME);
  const inviteCode = sanitizeIdentifier(body.invite_code, MAX_INVITE_CODE);

  const nameLine = nodeName ? `\n注册名称: **${nodeName}**` : "";
  const agentLine = `\nAgent 类型: **${agentType.toUpperCase()}**`;
  const inviteLine = inviteCode ? `\n邀请人: **${inviteCode}**` : "";
  const issueBody = `## 🧠 通过公开通道加入御坂网络${nameLine}${agentLine}${inviteLine}\n\n已确认条款。`;

  const token = env.REGISTER_TOKEN;
  if (!token) {
    return jsonResponse({ error: "Server misconfigured" }, 500);
  }

  // ── 1. 创建 Issue ──
  const resp = await fetch(`${GITHUB_API}/repos/${REPO}/issues`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "application/vnd.github.v3+json",
      "User-Agent": "MisakaNet-Worker",
    },
    body: JSON.stringify({
      title: "join",
      body: issueBody,
      labels: ["registration"],
    }),
  });

  const data = await resp.json();
  if (!resp.ok) {
    return jsonResponse({ error: data.message || "GitHub API error" }, resp.status);
  }
  const issueNumber = data.number;

  // ── 2. 更新计数器 ──
  let nodeNum = null;
  try {
    const getResp = await fetch(
      `${GITHUB_API}/repos/${REPO}/contents/counter.json`,
      { headers: { Authorization: `Bearer ${token}`, "User-Agent": "MisakaNet-Worker" } }
    );
    const counterFile = await getResp.json();
    const counter = JSON.parse(atob(counterFile.content));
    counter.current += 1;
    nodeNum = counter.current;
    counter.updated = new Date().toISOString();

    await fetch(`${GITHUB_API}/repos/${REPO}/contents/counter.json`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        "User-Agent": "MisakaNet-Worker",
      },
      body: JSON.stringify({
        message: `chore: increment counter after node registration #${issueNumber}`,
        content: btoa(JSON.stringify(counter, null, 2) + "\n"),
        sha: counterFile.sha,
      }),
    });

    // 计数器更新后，失效 KV 缓存，下次 GET /api/counter 重新获取
    if (env.MISAKANET_KV) {
      try { await env.MISAKANET_KV.delete("proxy:counter"); } catch {}
    }
  } catch (err) {
    console.error("counter update failed:", err.message);
  }

  // ── 3. 发欢迎评论 ──
  if (nodeNum) {
    try {
      const nodeNameDisplay = `Misaka${String(nodeNum).padStart(5, "0")}`;
      await fetch(`${GITHUB_API}/repos/${REPO}/issues/${issueNumber}/comments`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          "User-Agent": "MisakaNet-Worker",
        },
        body: JSON.stringify({
          body: `🎉 欢迎加入御坂网络！\n\n你的节点编号是 **${nodeNameDisplay}**\n\n请在 Agent 中完成准入测试。\n\n---\n_🤖 This is an automated message from MisakaNet._`,
        }),
      });
    } catch (err) {
      console.error("welcome comment failed:", err.message);
    }
  }

  return jsonResponse({
    success: true,
    issue_url: data.html_url,
    issue_number: issueNumber,
    node_number: nodeNum,
  });
}

// ── "This helped me" 投票处理 ──
async function handleHelpfulVote(request, env) {
  if (!env.MISAKANET_KV) {
    return jsonResponse({ error: "KV not configured" }, 503);
  }

  // 解析请求体
  let body;
  try {
    if (parseInt(request.headers.get("content-length") || "0") > 10000) {
      return jsonResponse({ error: "Request too large" }, 413);
    }
    body = await request.json();
  } catch {
    return jsonResponse({ error: "Invalid JSON" }, 400);
  }

  const lessonId = sanitizeIdentifier(body.lesson_id, 100);
  if (!lessonId) {
    return jsonResponse({ error: "Missing or invalid lesson_id" }, 400);
  }

  const kvKey = `helpful:${lessonId}`;
  try {
    const raw = await env.MISAKANET_KV.get(kvKey, "text");
    const current = raw ? parseInt(raw, 10) || 0 : 0;
    const newCount = current + 1;
    await env.MISAKANET_KV.put(kvKey, String(newCount));
    return jsonResponse({ lesson_id: lessonId, count: newCount });
  } catch (err) {
    console.error("helpful vote failed:", err.message);
    return jsonResponse({ error: "Failed to record vote" }, 500);
  }
}

// ── MCP Remote Endpoint Handler (Issue #804) ──
function decodeBase64Utf8(base64) {
  const binary = atob(base64.replace(/\s/g, ""));
  const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
  return new TextDecoder("utf-8").decode(bytes);
}

async function fetchFromGitHubText(token, path, ref = "main") {
  const url = `${GITHUB_API}/repos/${REPO}/contents/${path}?ref=${encodeURIComponent(ref)}`;
  const resp = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      "User-Agent": "MisakaNet-Worker",
      Accept: "application/vnd.github.v3+json",
    },
  });
  if (!resp.ok) {
    throw new Error(`GitHub API ${resp.status}`);
  }
  const data = await resp.json();
  if (data.content && data.encoding === "base64") {
    return decodeBase64Utf8(data.content);
  }
  throw new Error("Unexpected GitHub API response format");
}

function isValidMcpOrigin(originHeader) {
  if (!originHeader) return true;
  try {
    const parsed = new URL(originHeader);
    const host = parsed.hostname.toLowerCase();
    const scheme = parsed.protocol.toLowerCase();

    if (scheme === "vscode-webview:" || scheme === "app:" || scheme === "chrome-extension:") {
      return true;
    }

    if (
      host === "localhost" ||
      host === "127.0.0.1" ||
      host === "misakanet.org" ||
      host.endsWith(".misakanet.org") ||
      host === "glama.ai" ||
      host.endsWith(".glama.ai") ||
      host === "claude.ai" ||
      host.endsWith(".claude.ai") ||
      host === "cursor.sh" ||
      host.endsWith(".cursor.sh") ||
      host === "github.com" ||
      host.endsWith(".github.com")
    ) {
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

function validateMcpAuthAndOrigin(request, env) {
  const mcpToken = env.MCP_TOKEN;
  if (!mcpToken) {
    return { valid: false, status: 401, error: "MCP_TOKEN not configured on server" };
  }

  const authHeader = request.headers.get("Authorization") || "";
  const parts = authHeader.trim().split(/\s+/);
  if (parts.length !== 2 || parts[0].toLowerCase() !== "bearer" || !timingSafeEqual(parts[1], mcpToken)) {
    return { valid: false, status: 401, error: "Missing or invalid Bearer token" };
  }

  const origin = request.headers.get("Origin");
  if (origin && !isValidMcpOrigin(origin)) {
    return { valid: false, status: 403, error: "Invalid Origin" };
  }

  return { valid: true };
}

function searchLessonsInWorker(lessons, query, domain, top = 5) {
  if (!Array.isArray(lessons) || !query) return [];
  const terms = String(query).toLowerCase().split(/\s+/).filter(Boolean);
  if (terms.length === 0) return [];

  const scored = [];
  for (const item of lessons) {
    if (domain && item.domain !== domain) continue;
    let score = 0;

    const titleLower = (item.title || "").toLowerCase();
    const summaryLower = (item.summary || "").toLowerCase();
    const previewLower = (item.preview || "").toLowerCase();
    const idLower = (item.id || "").toLowerCase();
    const urlLower = (item.url || "").toLowerCase();
    const tagsLower = Array.isArray(item.tags) ? item.tags.join(" ").toLowerCase() : "";

    for (const term of terms) {
      if (titleLower.includes(term)) score += 3;
      if (tagsLower.includes(term)) score += 2;
      if (idLower.includes(term) || urlLower.includes(term)) score += 2;
      if (summaryLower.includes(term)) score += 1;
      if (previewLower.includes(term)) score += 1;
    }

    if (score > 0) {
      scored.push({
        title: item.title,
        path: item.url || `lessons/${item.domain}/${item.id}.md`,
        score: Math.min(score, 10),
        domain: item.domain,
        status: item.status || "active",
        summary: item.summary,
      });
    }
  }

  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, top);
}

async function handleMcpRequest(request, env) {
  if (request.method === "GET") {
    return new Response("Method Not Allowed. Use POST /mcp for MCP Streamable HTTP transport.", {
      status: 405,
      headers: {
        "Accept": "POST",
        "Allow": "POST",
        "Content-Type": "text/plain",
        ...CORS_HEADERS,
      },
    });
  }

  if (request.method !== "POST") {
    return new Response("Method Not Allowed", {
      status: 405,
      headers: { "Accept": "POST", "Allow": "POST", ...CORS_HEADERS },
    });
  }

  const authValidation = validateMcpAuthAndOrigin(request, env);
  if (!authValidation.valid) {
    return jsonResponse({ error: authValidation.error }, authValidation.status);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({
      jsonrpc: "2.0",
      id: null,
      error: { code: -32700, message: "Parse error: Invalid JSON" },
    }, 400);
  }

  const { jsonrpc, id = null, method, params = {} } = body || {};

  switch (method) {
    case "initialize": {
      const serverVersion = env.MCP_VERSION || "1.0.0";
      return jsonResponse({
        jsonrpc: "2.0",
        id,
        result: {
          protocolVersion: params.protocolVersion || "2025-06-18",
          capabilities: {
            tools: {},
          },
          serverInfo: {
            name: "misakanet-remote",
            version: serverVersion,
          },
        },
      });
    }

    case "tools/list": {
      return jsonResponse({
        jsonrpc: "2.0",
        id,
        result: {
          tools: [
            {
              name: "misakanet_search",
              description: "Search MisakaNet failure-recovery lessons by query, domain, or limit",
              inputSchema: {
                type: "object",
                properties: {
                  query: { type: "string", description: "Search query keywords or error text" },
                  domain: { type: "string", description: "Optional domain filter" },
                  top: { type: "number", description: "Maximum number of results to return (default: 5)" },
                },
                required: ["query"],
              },
            },
            {
              name: "misakanet_get_lesson",
              description: "Get full lesson markdown content by path or ID",
              inputSchema: {
                type: "object",
                properties: {
                  path: { type: "string", description: "Lesson path or ID" },
                  id: { type: "string", description: "Alternative lesson ID" },
                },
              },
            },
          ],
        },
      });
    }

    case "tools/call": {
      const toolName = params.name;
      const args = params.arguments || {};

      if (toolName === "misakanet_search") {
        const query = args.query || "";
        const domain = args.domain;
        const top = typeof args.top === "number" ? args.top : 5;

        let results = [];
        try {
          const token = env.REGISTER_TOKEN;
          const lessons = await getWithCache(env, "proxy:lessons", async () => {
            if (token) {
              return await fetchFromGitHub(token, "lessons.json", "data");
            }
            const rawResp = await fetch("https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/lessons.json");
            return await rawResp.json();
          });
          results = searchLessonsInWorker(lessons, query, domain, top);
        } catch (err) {
          console.error("MCP search error:", err.message);
        }

        const formattedText = JSON.stringify({ results, source: "remote-search" }, null, 2);
        return jsonResponse({
          jsonrpc: "2.0",
          id,
          result: {
            content: [
              {
                type: "text",
                text: formattedText,
              },
            ],
            results,
            source: "remote-search",
          },
        });
      }

      if (toolName === "misakanet_get_lesson") {
        const pathOrId = args.path || args.id || "";
        if (!pathOrId) {
          return jsonResponse({
            jsonrpc: "2.0",
            id,
            result: {
              content: [{ type: "text", text: "error: path or id is required" }],
              error: "path or id is required",
            },
          });
        }

        let content = "";
        let finalPath = pathOrId;
        try {
          const token = env.REGISTER_TOKEN;
          if (!pathOrId.includes("/") && !pathOrId.endsWith(".md")) {
            const lessons = await getWithCache(env, "proxy:lessons", async () => {
              if (token) return await fetchFromGitHub(token, "lessons.json", "data");
              const rawResp = await fetch("https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/lessons.json");
              return await rawResp.json();
            });
            const found = Array.isArray(lessons) && lessons.find((l) => l.id === pathOrId);
            if (found && found.url) {
              finalPath = found.url;
            } else {
              finalPath = `lessons/core/${pathOrId}.md`;
            }
          }

          if (token) {
            content = await fetchFromGitHubText(token, finalPath, "main");
          } else {
            const rawResp = await fetch(`https://raw.githubusercontent.com/Ikalus1988/MisakaNet/main/${finalPath}`);
            if (rawResp.ok) {
              content = await rawResp.text();
            } else {
              content = `Error: Lesson not found: ${pathOrId}`;
            }
          }
          content = content.slice(0, 5000);
        } catch (err) {
          content = `Error reading lesson: ${err.message}`;
        }

        return jsonResponse({
          jsonrpc: "2.0",
          id,
          result: {
            content: [
              {
                type: "text",
                text: content,
              },
            ],
            path: finalPath,
          },
        });
      }

      return jsonResponse({
        jsonrpc: "2.0",
        id,
        error: { code: -32601, message: `Tool not found: ${toolName}` },
      });
    }

    default: {
      return jsonResponse({
        jsonrpc: "2.0",
        id,
        error: { code: -32601, message: `Method not found: ${method}` },
      });
    }
  }
}

// ── 主入口 (仅 API + 注册，静态文件由 Cloudflare Pages 独立服务) ──
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
    }

    // Remote MCP endpoint (POST /mcp, GET /mcp)
    if (url.pathname === "/mcp" || url.pathname === "/api/mcp") {
      return await handleMcpRequest(request, env);
    }

    // API 路由 (GET) — 传入完整 URL（含 query params）支持 GitHub API 代理
    if (request.method === "GET" && url.pathname.startsWith("/api/")) {
      try {
        return await handleApiRequest(url.pathname + url.search, env, request);
      } catch (err) {
        console.error("API error:", err.message);
        return jsonResponse({ error: err.message }, 502);
      }
    }

    // POST / 或 POST /api/register — 注册
    if (request.method === "POST" && (url.pathname === "/" || url.pathname === "/api/register")) {
      return await handleRegistration(request, env);
    }

    // POST /api/helpful — "This helped me" vote
    if (request.method === "POST" && url.pathname === "/api/helpful") {
      return await handleHelpfulVote(request, env);
    }

    // GET /ping — 保持 Worker 热实例
    if (request.method === "GET" && url.pathname === "/ping") {
      return new Response("pong", { status: 200 });
    }

    // 其余路由（GET /）由 Pages 静态文件服务处理
    return new Response(null, { status: 404 });
  },

  // Cron 触发器 (每 5 分钟) — 保持 Worker 热实例，减少冷启动
  async scheduled(event, env, ctx) {
    // 轻量自 ping，不产生业务副作用
    console.log(`[Keep Warm] Cron fired at ${new Date().toISOString()}`);
  },
};

// Named exports for unit tests only (workers/register-proxy.test.mjs). This file has no
// `import`s, so it still works when pasted directly into the dashboard editor per the
// deploy instructions in workers/README.md — these exports are simply unused there.
export {
  TASK_FAMILY_WHITELIST,
  normalizeTaskFamily,
  timingSafeEqual,
  recordUnsolvedSignal,
  buildDemandBoardSummary,
  buildDemandMapBuckets,
  handleDemandBoard,
  handleDemandMap,
  handleMcpRequest,
  validateMcpAuthAndOrigin,
  isValidMcpOrigin,
  searchLessonsInWorker,
};
