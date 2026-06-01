// MisakaNet Register Proxy — Cloudflare Worker
// 部署方式: 见 workers/README.md
// 环境变量: REGISTER_TOKEN (GitHub PAT, 需 contents+issues write)

const REPO = "Ikalus1988/MisakaNet";
const GITHUB_API = "https://api.github.com";

// IP 限流: 每个 IP 每 30 秒最多 1 次
const RATE_LIMIT_WINDOW = 30_000;
const RATE_MAP_CLEAN_INTERVAL = 300_000; // 5 分钟清理一次过期条目
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
const MAX_INVITE_CODE = 30;

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
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
  // 只允许字母、数字、下划线、连字符、中文
  return val.replace(/[^\w\u4e00-\u9fa5\-]/g, "");
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
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
  <a class="btn" href="https://ikalus1988.github.io/MisakaNet/">← 返回注册页面</a>
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

    // 定期清理 rateMap（每 50 次请求触发一次）
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

    // 校验必填字段 + 输入清洗
    if (!body.agent_type) {
      return jsonResponse({ error: "Missing agent_type" }, 400);
    }
    const agentType = sanitizeIdentifier(body.agent_type, MAX_AGENT_TYPE);
    if (!agentType) {
      return jsonResponse({ error: "Invalid agent_type" }, 400);
    }
    const nodeName = sanitizeIdentifier(body.node_name, MAX_NODE_NAME);
    const inviteCode = sanitizeIdentifier(body.invite_code, MAX_INVITE_CODE);

    // 构造 Issue body
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
    } catch (err) {
      console.error("counter update failed:", err.message);
    }

    // ── 3. 发欢迎评论（含节点编号供前端 JS 解析） ──
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
  },
};
