// MisakaNet Register Proxy — Cloudflare Worker
// 职责: 校验输入 → 创建注册 Issue → 返回结果
// counter、头像、欢迎词由 register.yml workflow 处理
// 环境变量: REGISTER_TOKEN (GitHub PAT, 需 issues:write)

const REPO = "Ikalus1988/MisakaNet";
const GITHUB_API = "https://api.github.com";
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

function sanitizeIdentifier(val, maxLen) {
  if (!val) return "";
  if (val.length > maxLen) val = val.slice(0, maxLen);
  // 只允许字母、数字、下划线、连字符、中文
  return val.replace(/[^\w\u4e00-\u9fa5\-]/g, "");
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
        timestamp: new Date().toISOString(),
      });
    }

    if (request.method === "GET" && url.pathname === "/ping") {
      return new Response("pong", {
        status: 200,
        headers: { "content-type": "text/plain;charset=utf-8", ...CORS_HEADERS },
      });
    }

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

    if (request.method !== "POST") {
      return jsonResponse({ error: "Method not allowed" }, 405);
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
