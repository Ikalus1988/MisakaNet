// MisakaNet Register + Data Proxy — Cloudflare Worker
// 部署方式: https://dash.cloudflare.com/ → Workers & Pages
// 环境变量: REGISTER_TOKEN (GitHub PAT, 需 contents+issues write)
// KV Namespace: MISAKANET_KV (可选，用于缓存数据代理响应)

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
async function handleApiRequest(pathWithQuery, env) {
  const token = env.REGISTER_TOKEN;
  if (!token) {
    return jsonResponse({ error: "REGISTER_TOKEN not configured on server" }, 500);
  }

  // 分离路径与查询参数
  const qIdx = pathWithQuery.indexOf("?");
  const pathname = qIdx >= 0 ? pathWithQuery.slice(0, qIdx) : pathWithQuery;
  const search = qIdx >= 0 ? pathWithQuery.slice(qIdx) : "";

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

// ── 主入口 (仅 API + 注册，静态文件由 Cloudflare Pages 独立服务) ──
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
    }

    // API 路由 (GET) — 传入完整 URL（含 query params）支持 GitHub API 代理
    if (request.method === "GET" && url.pathname.startsWith("/api/")) {
      try {
        return await handleApiRequest(url.pathname + url.search, env);
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
