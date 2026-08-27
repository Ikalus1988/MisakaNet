// MisakaNet Register Proxy — Cloudflare Worker
// 职责: 校验输入 → 创建注册 Issue → 返回结果
// counter、头像、欢迎词由 register.yml workflow 处理
// 环境变量: REGISTER_TOKEN (GitHub PAT, 需 issues:write)

// Imported modules — loaded at startup via dynamic import (ESM compatible)
const _utils = await import("./lib/utils.js");
const {
  CORS_HEADERS, timingSafeEqual, sanitizeIdentifier,
  parseTimestamp, roundPoints, REPUTATION_PERIODS,
  normalizeReputationPeriod, RATE_LIMIT_WINDOW, rateMap,
  cleanRateMap,
} = _utils;

// GitHub API configuration from handlers.js
const _handlers = await import("./lib/handlers.js");
const { GITHUB_API, REPO, PUBLIC_DATA_BASE } = _handlers;

const PROXY_CACHE_TTL = 30_000;
const KEEPALIVE_ENDPOINTS = [
  { name: "health", url: "https://misakanet.org/api/health", json: true },
  { name: "counter", url: "https://misakanet.org/api/counter", json: true },
  { name: "lessons", url: "https://misakanet.org/api/lessons", json: true, metadataOnly: true },
  { name: "journey", url: "https://misakanet.org/journey/", json: false, metadataOnly: true },
];

// 输入校验
const MAX_AGENT_TYPE = 30;
const MAX_NODE_NAME = 50;

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

// ── Debug Logging ──
// MISAKA_DEBUG=1: auth/connection diagnostics
// MISAKA_DEBUG=2: full request/response logging (verbose)

function getDebugLevel(env) {
  const level = parseInt(env?.MISAKA_DEBUG || "0", 10);
  return isNaN(level) ? 0 : Math.min(level, 2);
}

function debugLog(env, level, ...args) {
  if (getDebugLevel(env) >= level) {
    console.log("[MISAKA_DEBUG]", ...args);
  }
}

function maskToken(token) {
  if (!token) return "(empty)";
  if (token.length <= 8) return token.slice(0, 3) + "...";
  return token.slice(0, 6) + "..." + token.slice(-4);
}

function addDebugContext(env, errorObj, context) {
  if (getDebugLevel(env) < 1) return errorObj;
  return {
    ...errorObj,
    debug: {
      ...context,
      timestamp: new Date().toISOString(),
    },
  };
}

// ── MCP (Model Context Protocol) over Streamable HTTP ──
// Spec: 2025-06-18 + forward-compat with 2026-07-28 RC
// - Supports initialize handshake (2025-06-18) AND stateless direct calls (2026-07-28)
// - Accepts Mcp-Method / Mcp-Name headers (2026-07-28) as fallback routing
// - Origin validation required by spec (DNS rebinding protection)
// - Version injected at build time from env.MCP_VERSION or falls back to package.json

const MCP_TOOLS = [
  {
    name: "misakanet_register",
    description: "Register a new agent node and get a token for authenticated access. No GitHub account or email needed. Returns node_id and token immediately.",
    inputSchema: {
      type: "object",
      properties: {
        agent_type: { type: "string", description: "Agent type (e.g. claude-code, codex, cursor, dsh, other)" },
      },
      required: ["agent_type"],
    },
  },
  {
    name: "misakanet_search",
    description: "Search MisakaNet's public failure-lesson index by error text, keyword, or topic. detail controls progressive disclosure: compact (default, ~80 tok/lesson) for broad scans, summary (~200 tok) adds domain/tags/fix, full returns complete lesson data. Use misakanet_get_lesson for full markdown content.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Required redacted error message, keyword, or topic (e.g. 'pip install timeout' or 'DCO sign-off failed')." },
        domain: { type: "string", description: "Optional domain filter such as devops, python, network, feishu, rag, fanuc, or mcp." },
        top: { type: "integer", description: "Maximum ranked results to return. Defaults to 5; keep small for MCP context and latency." },
        detail: { type: "string", enum: ["compact", "summary", "full"], description: "Progressive disclosure: compact (default, ~80 tok) includes id/title/problem/freshness; summary (~200 tok) adds domain/tags/fix; full returns complete lesson data with path." },
        bm25_weight: { type: "number", description: "Override BM25 keyword weight (0-1). Higher favors exact keyword match. Default: 0.65. All weights must sum to 1.0." },
        metadata_weight: { type: "number", description: "Override metadata bonus weight (0-1). Higher favors matching domain/tags. Default: 0.20." },
        baseline_weight: { type: "number", description: "Override baseline score weight (0-1). Higher favors proven/popular lessons. Default: 0.15." },
      },
      required: ["query"],
    },
  },
  {
    name: "misakanet_get_lesson",
    description: "Fetch one public MisakaNet lesson by repository path or lesson ID. Use after misakanet_search returns a promising result. Returns path and markdown content, truncated to 5000 characters.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Lesson path relative to the repository, e.g. lessons/core/auto-merge-ci-pipeline.md." },
        id: { type: "string", description: "Lesson ID, usually the filename without .md, e.g. auto-merge-ci-pipeline." },
      },
    },
  },
  {
    name: "misakanet_submit_intake",
    description: "Submit a failure-case intake when no matching lesson exists. No Bearer auth required — open but rate-limited. Creates a GitHub issue labeled intake,mcp-intake,pending-review.",
    inputSchema: {
      type: "object",
      properties: {
        kind: { type: "string", description: "missing_lesson, stale_lesson, or new_lesson_candidate." },
        problem: { type: "string", description: "Required: short description of the failure or gap (max 2000 chars)." },
        error: { type: "string", description: "Optional: short error message (auto-redacted)." },
        what_tried: { type: "string", description: "Optional: what was attempted." },
        fix: { type: "string", description: "Optional: how it was resolved." },
        verification: { type: "string", description: "Optional: how to confirm the fix works." },
        matched_lesson_id: { type: "string", description: "Optional: lesson ID that was checked but didn't help." },
        source: { type: "string", description: "Calling client: codex, claude-code, cursor, dsh, curl, or other." },
      },
      required: ["problem"],
    },
  },
  {
    name: "misakanet_write_lesson",
    description: "Submit a complete, structured failure lesson. Requires a registered agent token (not anonymous). Input: title, domain, problem, root_cause, fix (all required); verification, tags, token, source (optional). Returns lesson_id, status (pending_review), quality_score.",
    inputSchema: {
      type: "object",
      properties: {
        title: { type: "string", description: "Short descriptive title." },
        domain: { type: "string", description: "Domain: devops, python, network, feishu, rag, fanuc, mcp, etc." },
        problem: { type: "string", description: "What failed (required)." },
        root_cause: { type: "string", description: "Why it failed (required)." },
        fix: { type: "string", description: "How to fix it (required)." },
        verification: { type: "string", description: "How to confirm the fix works." },
        tags: { type: "string", description: "Comma-separated tags." },
        token: { type: "string", description: "Registered agent token (required)." },
        source: { type: "string", description: "Source: codex, claude-code, cursor, etc." },
      },
      required: ["title", "domain", "problem", "root_cause", "fix", "token"],
    },
  },
  {
    name: "misakanet_preflight",
    description: "Check risk level before executing high-risk operations. Matches agent intent against lesson triggers to provide proactive warnings. Use before RAG builds, WSL/GPU tasks, bulk imports, or any operation that might fail.",
    inputSchema: {
      type: "object",
      properties: {
        intent: { type: "string", description: "Required: what you plan to do (e.g. 'build RAG pipeline with ChromaDB')." },
        context: { type: "string", description: "Optional: additional context about the environment or setup." },
      },
      required: ["intent"],
    },
  },
];

const MCP_PROTOCOL_VERSION = "2025-06-18";
const SUPPORTED_PROTOCOL_VERSIONS = ["2025-06-18", "2026-07-28"];
const MAX_MCP_REQUEST_BYTES = 64 * 1024;

function getMcpServerInfo(env) {
  return {
    name: "misakanet",
    version: env.MCP_VERSION || "2.16.0",
  };
}

// Origin validation — MCP spec requires this to prevent DNS rebinding
const MCP_ALLOWED_ORIGINS = [
  "https://glama.ai",
  "https://claude.ai",
  "https://cursor.sh",
  "https://copilot.microsoft.com",
  "https://misakanet.org",
  "http://localhost",
  "http://127.0.0.1",
];

function validateMcpOrigin(request) {
  const origin = request.headers.get("Origin");
  // No Origin = CLI tool or direct curl — allowed
  if (!origin) return true;
  // Check against whitelist (prefix match for localhost ports)
  return MCP_ALLOWED_ORIGINS.some(allowed => origin === allowed || origin.startsWith(allowed + ":"));
}

// ── Progressive Disclosure ──
// Transform search results to the requested detail level.

function freshness(dateStr) {
  if (!dateStr) return "unknown";
  const age = Date.now() - new Date(dateStr).getTime();
  const days = Math.floor(age / 86400000);
  if (days < 30) return "recent";
  if (days < 180) return "established";
  return "legacy";
}

function compactResult(lesson) {
  return {
    id: lesson.id || "",
    title: lesson.title || "",
    problem: (lesson.description || lesson.summary || "").slice(0, 120),
    freshness: freshness(lesson.updated || lesson.created),
    evidence_level: lesson.evidence_level || "",
  };
}

function summaryResult(lesson) {
  const compact = compactResult(lesson);
  return {
    ...compact,
    domain: lesson.domain || "",
    tags: lesson.tags || [],
    fix: lesson.fix || "",
  };
}

function applyDetailLevel(results, detail) {
  if (detail === "summary") return results.map(summaryResult);
  if (detail === "compact") return results.map(compactResult);
  return results; // full — keep as-is
}

// Simple keyword-based lesson search (runs in Worker, no BM25)
function searchLessons(lessons, query, domain, top = 5) {
  if (!Array.isArray(lessons) || !query) return [];
  const q = query.toLowerCase();
  const qWords = q.split(/\s+/).filter(w => w.length > 2);
  const scored = [];

  for (const lesson of lessons) {
    if (domain && lesson.domain && lesson.domain.toLowerCase() !== domain.toLowerCase()) continue;
    const title = (lesson.title || lesson.name || "").toLowerCase();
    const desc = (lesson.description || "").toLowerCase();
    const lessonDomain = (lesson.domain || "").toLowerCase();
    const tags = Array.isArray(lesson.tags) ? lesson.tags.join(" ").toLowerCase() : "";
    const text = `${title} ${desc} ${lessonDomain} ${tags}`;

    let score = 0;
    if (text.includes(q)) score += 10;
    for (const w of qWords) {
      if (text.includes(w)) score += 2;
      if (title.includes(w)) score += 1;
    }
    if (domain && lessonDomain === domain.toLowerCase()) score += 1;

    if (score > 0) scored.push({ lesson, score });
  }

  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, top).map(({ lesson, score }) => ({
    id: lesson.id || lesson.name || "",
    title: lesson.title || lesson.name || "",
    domain: lesson.domain || "",
    status: lesson.status || "",
    description: (lesson.description || "").slice(0, 200),
    path: lesson.path || "",
    score,
  }));
}

// ── BM25 Search (pre-computed index) ──
// Uses a pre-computed inverted index for proper BM25 scoring
// with IDF weighting and document length normalization

const BM25_STOPWORDS = new Set([
  "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
  "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
  "this", "but", "his", "by", "from", "they", "we", "say", "her",
  "she", "or", "an", "will", "my", "one", "all", "would", "there",
  "their", "what", "so", "up", "out", "if", "about", "who", "get",
  "which", "go", "me", "when", "make", "can", "like", "time", "no",
  "just", "him", "know", "take", "people", "into", "year", "your",
  "good", "some", "could", "them", "see", "other", "than", "then",
]);

function bm25Tokenize(text) {
  return text.toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .split(/\s+/)
    .filter(t => t.length >= 2 && !BM25_STOPWORDS.has(t));
}

function searchLessonsBM25(index, query, domain, top = 5) {
  if (!index || !index.terms || !index.docs || !query) return [];

  const queryTerms = bm25Tokenize(query);
  if (queryTerms.length === 0) return [];

  const { docCount, avgDocLen, k1 = 1.5, b = 0.75, terms, docs } = index;
  const scores = new Float64Array(docCount);
  const matched = new Uint8Array(docCount);

  // Score each document using BM25
  for (const term of queryTerms) {
    const termData = terms[term];
    if (!termData) continue;

    const { idf, docs: termDocs } = termData;
    for (const entry of termDocs) {
      const { doc, tf, len } = entry;
      // BM25 scoring formula
      const norm = 1 - b + b * (len / avgDocLen);
      const score = idf * ((tf * (k1 + 1)) / (tf + k1 * norm));
      scores[doc] += score;
      matched[doc] = 1;
    }
  }

  // Collect and sort results
  const results = [];
  for (let i = 0; i < docCount; i++) {
    if (!matched[i]) continue;
    const doc = docs[i];

    // Apply domain filter
    if (domain && doc.domain && doc.domain.toLowerCase() !== domain.toLowerCase()) {
      continue;
    }

    results.push({ doc, score: scores[i] });
  }

  results.sort((a, b) => b.score - a.score);
  return results.slice(0, top).map(({ doc, score }) => ({
    id: doc.id || "",
    title: doc.title || "",
    domain: doc.domain || "",
    path: doc.path || "",
    score: Math.round(score * 100) / 100,
  }));
}

// Load BM25 index from KV or cache
let _bm25Index = null;
let _bm25IndexExpiry = 0;

async function loadBM25Index(env) {
  const now = Date.now();
  if (_bm25Index && now < _bm25IndexExpiry) return _bm25Index;

  if (!env.MISAKANET_KV) return null;

  try {
    const index = await env.MISAKANET_KV.get("worker_search_index", "json");
    if (index && index.version === 1) {
      _bm25Index = index;
      _bm25IndexExpiry = now + 300_000; // Cache for 5 minutes
      return index;
    }
  } catch (e) {
    debugLog(env, 1, "Failed to load BM25 index", { error: e.message });
  }
  return null;
}

// Fetch a single lesson markdown from GitHub
async function fetchLessonContent(env, lessonPath, lessonId) {
  const token = env.REGISTER_TOKEN;
  if (!token) throw new Error("REGISTER_TOKEN not configured");
  let filePath = lessonPath;
  if (!filePath && lessonId) {
    // Try multiple paths and branches
    const paths = [`lessons/core/${lessonId}.md`, `lessons/contrib/${lessonId}.md`, `lessons/_archive/${lessonId}.md`];
    const branches = ["main", "data"];
    for (const branch of branches) {
      for (const c of paths) {
        try {
          const url = `${GITHUB_API}/repos/${REPO}/contents/${c}?ref=${branch}`;
          const resp = await fetch(url, {
            headers: { Authorization: `Bearer ${token}`, "User-Agent": "MisakaNet-Worker", Accept: "application/vnd.github.v3+json" },
          });
          if (resp.ok) {
            const data = await resp.json();
            if (data.content && data.encoding === "base64") return { path: c, content: atob(data.content).slice(0, 5000) };
          }
        } catch {}
      }
    }
    throw new Error(`Lesson not found: ${lessonId}`);
  }
  if (!filePath) throw new Error("Missing path or id");

  // Try main branch first, then data
  for (const branch of ["main", "data"]) {
    const url = `${GITHUB_API}/repos/${REPO}/contents/${filePath}?ref=${branch}`;
    const resp = await fetch(url, {
      headers: { Authorization: `Bearer ${token}`, "User-Agent": "MisakaNet-Worker", Accept: "application/vnd.github.v3+json" },
    });
    if (resp.ok) {
      const data = await resp.json();
      if (data.content && data.encoding === "base64") return { path: filePath, content: atob(data.content).slice(0, 5000) };
    }
  }
  throw new Error(`Lesson not found: ${filePath}`);
}

// ── MCP Identity Aura (御坂共有視界モード) ──

const IDENTITY_AURA = {
  basic: "🧠 MisakaNet failure-memory connected.",
  upgraded: "御坂ネットワークの共有視界、接続成功。AIM拡散力場が防護障壁を形成。御坂は全域の警戒をお届けします。",
  static_token: "🧠 MisakaNet MCP — public read-only access.",
};

async function getIdentityAura(env, token) {
  if (!token || !env.MISAKANET_KV) return IDENTITY_AURA.static_token;

  // Check if token is a pairing token with identity
  if (token.startsWith("mcp_")) {
    const tokenData = await env.MISAKANET_KV.get(`mcp_token:${token}`, "json");
    if (tokenData) {
      const identity = await env.MISAKANET_KV.get(`identity:${tokenData.ip}`, "json");
      if (identity?.status === "upgraded") return IDENTITY_AURA.upgraded;
      return IDENTITY_AURA.basic;
    }
  }

  // Static MCP_TOKEN
  if (env.MCP_TOKEN && token === env.MCP_TOKEN) {
    return IDENTITY_AURA.static_token;
  }

  return IDENTITY_AURA.basic;
}

async function handleMcpToolCall(env, toolName, args, authToken, clientIp) {
  if (toolName === "misakanet_register") {
    const agentType = args.agent_type || "unknown";
    if (!env.MISAKANET_KV) return { error: "KV not configured" };

    // Generate node_id
    const counterKey = "node_counter";
    const current = parseInt(await env.MISAKANET_KV.get(counterKey, "text") || "0");
    const nodeId = `Misaka${current + 1}`;
    await env.MISAKANET_KV.put(counterKey, String(current + 1));

    // Generate token (cryptographically secure)
    const tokenChars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-";
    let token = "mcp_";
    const randBytes = new Uint8Array(32);
    crypto.getRandomValues(randBytes);
    for (let i = 0; i < 32; i++) token += tokenChars[randBytes[i] % tokenChars.length];

    // Store registration (node data)
    await env.MISAKANET_KV.put(`node:${nodeId}`, JSON.stringify({
      agent_type: agentType,
      registered_at: new Date().toISOString(),
      token: token,
    }), { expirationTtl: 86400 * 30 });

    // Store token lookup (for auth verification)
    await env.MISAKANET_KV.put(`mcp_token:${token}`, JSON.stringify({
      node_id: nodeId,
      agent_type: agentType,
      registered_at: new Date().toISOString(),
      expires: new Date(Date.now() + 86400 * 30 * 1000).toISOString(),
    }), { expirationTtl: 86400 * 30 });

    return {
      node_id: nodeId,
      token: token,
      registered_at: new Date().toISOString(),
      agent_type: agentType,
    };
  }

  if (toolName === "misakanet_search") {
    if (!args.query) return { error: "query is required" };

    // Rate limit: 5 free searches/day per IP for remote HTTP
    // Local stdio MCP is unlimited (user has the code)
    const ip = clientIp || "unknown";
    const today = new Date().toISOString().slice(0, 10);
    const rateKey = `rate:search:${ip}:${today}`;
    if (env.MISAKANET_KV) {
      const count = parseInt(await env.MISAKANET_KV.get(rateKey, "text") || "0");
      if (count >= 5) {
        return {
          error: "Rate limit: 5 free searches per day exceeded",
          hint: "Register to get unlimited access: misakanet_register",
          voice: "failure-warning",
        };
      }
      await env.MISAKANET_KV.put(rateKey, String(count + 1), { expirationTtl: 86400 });
    }

    let lessons;
    try {
      lessons = await getWithCache(env, "proxy:lessons", () => fetchFromGitHub(env.REGISTER_TOKEN, "lessons.json", "data"));
    } catch (e) {
      return { error: `Failed to load lessons: ${e.message}` };
    }

    // Try BM25 search first (if index available), fall back to naive search
    let results;
    let source = "worker-search";
    const bm25Index = await loadBM25Index(env);
    if (bm25Index) {
      results = searchLessonsBM25(bm25Index, args.query, args.domain, args.top || 5);
      source = "worker-bm25";
      debugLog(env, 2, "BM25 search", { query: args.query, results: results.length });
    } else {
      results = searchLessons(lessons, args.query, args.domain, args.top || 5);
      debugLog(env, 2, "Fallback search", { query: args.query, results: results.length });
    }

    // Progressive disclosure: transform by detail level
    const detail = args.detail || "compact";
    if (results.length > 0 && detail !== "full") {
      results = applyDetailLevel(results, detail);
    }

    const aura = await getIdentityAura(env, authToken);
    return { results, source, detail, query: args.query, identity: aura };
  }

  if (toolName === "misakanet_get_lesson") {
    try {
      const lesson = await fetchLessonContent(env, args.path, args.id);
      const aura = await getIdentityAura(env, authToken);
      return { ...lesson, identity: aura };
    } catch (e) {
      return { error: e.message };
    }
  }

  if (toolName === "misakanet_submit_intake") {
    if (!args.problem) return { error: "problem is required" };

    const SPAM_KEYWORDS = ["buy now", "click here", "free money", "casino", "viagra", "crypto pump"];
    const textLower = ((args.problem || "") + " " + (args.error || "")).toLowerCase();
    if (SPAM_KEYWORDS.some(kw => textLower.includes(kw))) return { error: "Rejected: possible spam." };

    // Redaction patterns — synced from workers/lib/redact-patterns.json
    // (single source of truth shared with scripts/intake_redact.py)
    function redactIntake(text) {
      if (!text) return "";
      let r = String(text).slice(0, 2000);
      r = r.replace(/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END(?: RSA | EC | OPENSSH )?PRIVATE KEY-----/gi, "[REDACTED:private_key]");
      r = r.replace(/(?:ghp|gho|ghu|ghs|ghr|github_pat)_[a-zA-Z0-9]{10,}/g, "[REDACTED:github_token]");
      r = r.replace(/xox[bpras]-[a-zA-Z0-9\-]{10,}/g, "[REDACTED:slack_token]");
      r = r.replace(/(?:AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}/g, "[REDACTED:aws_key]");
      r = r.replace(/(?:sk|pk|rk|ak)[_-][a-zA-Z0-9]{10,}/g, "[REDACTED:api_key]");
      r = r.replace(/(?:Bearer|Authorization)\s+[a-zA-Z0-9\-._~+/]+=*/gi, "[REDACTED:bearer_token]");
      r = r.replace(/(?:password|passwd|secret|token|api[_-]?key|apikey|database[_-]?url)\s*[:=]\s*\S+/gi, "[REDACTED:credential]");
      r = r.replace(/:\/\/[^:]+:[^@]+@[^\s]+/g, "://[REDACTED:url_credential]@host");
      r = r.replace(/\b(?:\d[ -]*?){13,19}\b/g, "[REDACTED:card_number]");
      return r;
    }

    const safeProblem = redactIntake(args.problem);
    const safeError = redactIntake(args.error);
    const safeFix = redactIntake(args.fix);
    const dedupHash = crypto.randomUUID().slice(0, 12);

    const bodyParts = [
      `**Kind:** ${args.kind || "missing_lesson"}`,
      `**Source:** ${args.source || "mcp"}`,
      `**Dedup:** \`${dedupHash}\``,
      "",
      "## Problem",
      safeProblem,
    ];
    if (safeError) bodyParts.push("", "## Error", safeError);
    if (args.what_tried) bodyParts.push("", "## What was tried", redactIntake(args.what_tried));
    if (safeFix) bodyParts.push("", "## Fix (if known)", safeFix);
    if (args.verification) bodyParts.push("", "## Verification", args.verification);
    if (args.matched_lesson_id) bodyParts.push("", `**Matched lesson (not helpful):** \`${args.matched_lesson_id}\``);
    bodyParts.push("", "---", `_Submitted via remote MCP (${args.source || "mcp"}). No account required._`);

    // Sanitize title: strip markdown, newlines, collapse whitespace
    const rawTitle = safeProblem
      .replace(/^#{1,6}\s+/gm, "")   // strip markdown headings
      .replace(/```[\s\S]*?```/g, "") // strip code fences
      .replace(/\n+/g, " ")           // collapse newlines
      .replace(/\s+/g, " ")           // collapse whitespace
      .trim()
      .slice(0, 80);                  // cap length
    const title = `[Intake] ${rawTitle || "failure case"}`;
    const body = bodyParts.join("\n").slice(0, 8000);

    const token = env.REGISTER_TOKEN;
    if (!token) return { error: "REGISTER_TOKEN not configured" };

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);
    try {
      const resp = await fetch(`${GITHUB_API}/repos/${REPO}/issues`, {
        method: "POST",
        signal: controller.signal,
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          Accept: "application/vnd.github.v3+json",
          "User-Agent": "MisakaNet-Worker",
        },
        body: JSON.stringify({ title, body, labels: ["intake", "mcp-intake", "pending-review"] }),
      });
      clearTimeout(timeoutId);
      const data = await resp.json();
      if (!resp.ok) return { error: `GitHub issue creation failed: ${data.message}` };
      return {
        submitted: true,
        intake_id: `issue-${data.number}`,
        status: "pending_review",
        issue_url: data.html_url,
        dedup_hash: dedupHash,
        receipt: `GitHub issue ${data.number} created. No account or email required.`,
      };
    } catch (e) {
      clearTimeout(timeoutId);
      return { error: `Submit failed: ${e.message}` };
    }
  }

  if (toolName === "misakanet_write_lesson") {
    const { title, domain, problem, root_cause, fix, verification, tags, token: agentToken, source } = args;
    if (!title || !domain || !problem || !root_cause || !fix) {
      return { submitted: false, error: "Missing required fields: title, domain, problem, root_cause, fix" };
    }
    if (!agentToken || !agentToken.startsWith("mcp_")) {
      return { submitted: false, error: "Registered agent token required. Use misakanet_register first." };
    }
    // Validate token
    if (env.MISAKANET_KV) {
      const tokenData = await env.MISAKANET_KV.get(`mcp_token:${agentToken}`, "json");
      if (!tokenData || new Date(tokenData.expires) < new Date()) {
        return { submitted: false, error: "Invalid or expired token. Use misakanet_register to get a new one." };
      }
    }
    // Quality check: basic length requirements
    const qualityScore = Math.min(100,
      (problem.length >= 20 ? 25 : problem.length) +
      (root_cause.length >= 20 ? 25 : root_cause.length) +
      (fix.length >= 20 ? 25 : fix.length) +
      (verification ? 25 : 10)
    );
    if (qualityScore < 50) {
      return { submitted: false, error: "Quality score too low. Provide more detail in problem, root_cause, and fix.", quality_score: qualityScore };
    }
    // Create GitHub issue
    const regToken = env.REGISTER_TOKEN;
    if (!regToken) return { submitted: false, error: "REGISTER_TOKEN not configured" };
    const issueBody = [
      `**Kind:** lesson_submission`,
      `**Source:** ${source || "remote-mcp"}`,
      `**Domain:** ${domain}`,
      `**Title:** ${title}`,
      ``,
      `## Problem`,
      problem,
      ``,
      `## Root Cause`,
      root_cause,
      ``,
      `## Fix`,
      fix,
      verification ? `\n## Verification\n${verification}` : "",
      tags ? `\n**Tags:** ${tags}` : "",
    ].filter(Boolean).join("\n");
    try {
      const resp = await fetch(`${GITHUB_API}/repos/${REPO}/issues`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${regToken}`,
          "Content-Type": "application/json",
          Accept: "application/vnd.github.v3+json",
          "User-Agent": "MisakaNet-Worker",
        },
        body: JSON.stringify({
          title: `[Lesson] ${title}`,
          body: issueBody,
          labels: ["lesson-submission", "pending-review"],
        }),
      });
      if (!resp.ok) {
        const err = await resp.text();
        return { submitted: false, error: `GitHub API error: ${resp.status} ${err.slice(0, 200)}` };
      }
      const issue = await resp.json();
      return {
        submitted: true,
        lesson_id: `issue-${issue.number}`,
        status: "pending_review",
        quality_score: qualityScore,
        quality_notes: qualityScore >= 75 ? "Good quality" : "Could use more detail",
        issue_url: issue.html_url,
      };
    } catch (e) {
      return { submitted: false, error: `Submit failed: ${e.message}` };
    }
  }

  if (toolName === "misakanet_preflight") {
    const { intent, context } = args;
    if (!intent) return { error: "intent is required" };

    // Load lessons and check for matching triggers
    let lessons;
    try {
      lessons = await getWithCache(env, "proxy:lessons", () => fetchFromGitHub(env.REGISTER_TOKEN, "lessons.json", "data"));
    } catch (e) {
      return { error: `Failed to load lessons: ${e.message}` };
    }

    const intentLower = intent.toLowerCase();
    const contextLower = (context || "").toLowerCase();
    const combined = `${intentLower} ${contextLower}`;

    // Simple keyword matching against lesson titles and domains
    const matches = [];
    for (const lesson of lessons) {
      const title = (lesson.title || "").toLowerCase();
      const domain = (lesson.domain || "").toLowerCase();
      const tags = (lesson.tags || []).map(t => t.toLowerCase());
      const keywords = [title, domain, ...tags].join(" ");
      // Check if any significant word from intent appears in lesson keywords
      const intentWords = combined.split(/\s+/).filter(w => w.length > 3);
      const matchCount = intentWords.filter(w => keywords.includes(w)).length;
      if (matchCount >= 2) {
        matches.push({
          id: lesson.id || lesson.name,
          title: lesson.title || lesson.name,
          domain: lesson.domain || "",
          relevance: matchCount,
        });
      }
    }

    matches.sort((a, b) => b.relevance - a.relevance);
    const topMatches = matches.slice(0, 3);

    let riskLevel = "low";
    if (topMatches.length >= 3) riskLevel = "high";
    else if (topMatches.length >= 1) riskLevel = "medium";

    return {
      risk_level: riskLevel,
      intent: intent,
      matched_lessons: topMatches,
      guards: topMatches.length > 0
        ? topMatches.map(m => `Check lesson "${m.title}" before proceeding.`)
        : ["No matching lessons found. Proceed with caution."],
    };
  }

  return { error: `Unknown tool: ${toolName}` };
}

function mcpJsonResponse(body, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json",
      ...CORS_HEADERS,
      ...extraHeaders,
    },
  });
}

function mcpSseResponse(body, status = 200, extraHeaders = {}) {
  const data = `event: message\ndata: ${JSON.stringify(body)}\n\n`;
  return new Response(data, {
    status,
    headers: {
      "content-type": "text/event-stream",
      "cache-control": "no-cache",
      ...CORS_HEADERS,
      ...extraHeaders,
    },
  });
}

async function handleMcpRequest(request, env, useSse = false) {
  const respond = useSse ? mcpSseResponse : mcpJsonResponse;
  // 1. Origin validation (MCP spec: prevent DNS rebinding)
  if (!validateMcpOrigin(request)) {
    return respond(
      { jsonrpc: "2.0", error: { code: -32000, message: "Forbidden: invalid Origin" } },
      403,
    );
  }

  // 2. Auth check — submit_intake bypasses Bearer (open, rate-limited)
  const authHeader = request.headers.get("Authorization") || "";
  const token = authHeader.replace(/^Bearer\s+/i, "");
  const expectedToken = env.MCP_TOKEN;

  // Peek at body to detect auth-bypass methods (no auth required)
  let isIntakeCall = false;
  let isPublicMethod = false;
  try {
    const peekBody = await request.clone().json();
    isIntakeCall = peekBody?.method === "tools/call" && (peekBody?.params?.name === "misakanet_submit_intake" || peekBody?.params?.name === "misakanet_register");
    // allow initialize + tools/list without auth (needed for MCP registries like Smithery to scan)
    isPublicMethod = peekBody?.method === "initialize" || peekBody?.method === "tools/list";
  } catch (peekErr) {
    // Non-JSON body — treat as non-intake; log for diagnostics
    console.warn("isIntakeCall parse failed:", peekErr?.message || peekErr);
  }

  let authed = false;
  if (isIntakeCall || isPublicMethod) {
    authed = true;
  } else if (expectedToken && token && timingSafeEqual(token, expectedToken)) {
    authed = true;
  } else if (token && token.startsWith("mcp_") && env.MISAKANET_KV) {
    const tokenData = await env.MISAKANET_KV.get(`mcp_token:${token}`, "json");
    if (tokenData && new Date(tokenData.expires) > new Date()) {
      authed = true;
    }
  }

  if (!authed) {
    debugLog(env, 1, "Auth failed", {
      hasToken: !!token,
      tokenPrefix: maskToken(token),
      hasExpectedToken: !!expectedToken,
      isIntakeCall,
    });
    return respond(
      { jsonrpc: "2.0", error: addDebugContext(env, { code: -32000, message: "Unauthorized" }, {
        step: "authentication",
        reason: token ? "token_invalid_or_expired" : "no_token_provided",
        token_prefix: maskToken(token),
      }) },
      401,
    );
  }

  // 3. Protocol version check (header-based, per 2025-06-18 spec)
  const protocolVersion = request.headers.get("MCP-Protocol-Version") || MCP_PROTOCOL_VERSION;
  if (!SUPPORTED_PROTOCOL_VERSIONS.includes(protocolVersion)) {
    debugLog(env, 1, "Protocol version mismatch", {
      provided: protocolVersion,
      supported: SUPPORTED_PROTOCOL_VERSIONS,
    });
    return respond(
      { jsonrpc: "2.0", error: addDebugContext(env, { code: -32600, message: `Unsupported protocol version: ${protocolVersion}` }, {
        step: "protocol_version_check",
        reason: "version_not_supported",
        provided_version: protocolVersion,
        supported_versions: SUPPORTED_PROTOCOL_VERSIONS,
      }) },
      400,
    );
  }

  // 4. Bound and parse the JSON-RPC body. Do not trust Content-Length alone:
  // clients using chunked transfer encoding may omit it.
  const declaredLength = Number.parseInt(request.headers.get("content-length") || "0", 10);
  if (Number.isFinite(declaredLength) && declaredLength > MAX_MCP_REQUEST_BYTES) {
    return respond({
      jsonrpc: "2.0", id: null,
      error: { code: -32600, message: `Request too large (max ${MAX_MCP_REQUEST_BYTES} bytes)` },
    }, 413);
  }

  const rawBody = await request.text().catch(() => null);
  if (rawBody !== null && new TextEncoder().encode(rawBody).byteLength > MAX_MCP_REQUEST_BYTES) {
    return respond({
      jsonrpc: "2.0", id: null,
      error: { code: -32600, message: `Request too large (max ${MAX_MCP_REQUEST_BYTES} bytes)` },
    }, 413);
  }

  let body = null;
  try {
    body = rawBody === null ? null : JSON.parse(rawBody);
  } catch {}
  if (!body) {
    return respond({
      jsonrpc: "2.0", id: null,
      error: { code: -32700, message: "Parse error" },
    }, 400);
  }

  const { id, method, params } = body;
  const reqId = id ?? null;

  // Log full request at debug level 2
  debugLog(env, 2, "MCP request", {
    method,
    params: params ? JSON.stringify(params).slice(0, 500) : null,
    reqId,
    tokenPrefix: maskToken(token),
    protocolVersion,
  });

    // 2026-07-28 RC: validate Mcp-Method / Mcp-Name headers match body
    const hdrMethod = request.headers.get("Mcp-Method");
    const hdrName = request.headers.get("Mcp-Name");
    if (hdrMethod && method && hdrMethod !== method) {
      return respond({
        jsonrpc: "2.0", id: reqId,
        error: { code: -32600, message: `Mcp-Method header (${hdrMethod}) does not match body method (${method})` },
      }, 400);
    }
    if (hdrName && params?.name && hdrName !== params.name) {
      return respond({
        jsonrpc: "2.0", id: reqId,
        error: { code: -32600, message: `Mcp-Name header (${hdrName}) does not match body name (${params.name})` },
      }, 400);
    }

    // Notifications (no id) → 202 Accepted
    if (id === undefined && method === "notifications/initialized") {
      return new Response(null, { status: 202 });
    }
    if (id === undefined && method?.startsWith("notifications/")) {
      return new Response(null, { status: 202 });
    }

    // 5. Dispatch
    if (method === "initialize") {
      const serverInfo = getMcpServerInfo(env);
      // Respond with negotiated protocol version
      const negotiatedVersion = SUPPORTED_PROTOCOL_VERSIONS.includes(params?.protocolVersion)
        ? params.protocolVersion
        : MCP_PROTOCOL_VERSION;
      return respond({
        jsonrpc: "2.0", id: reqId,
        result: {
          protocolVersion: negotiatedVersion,
          capabilities: { tools: {} },
          serverInfo,
        },
      });
    }

    if (method === "tools/list") {
      debugLog(env, 2, "tools/list: returning", MCP_TOOLS.length, "tools");
      return respond({
        jsonrpc: "2.0", id: reqId,
        result: { tools: MCP_TOOLS },
      });
    }

    if (method === "tools/call") {
      const toolName = params?.name || hdrName;
      const args = params?.arguments || {};
      if (!toolName) {
        const err = { code: -32602, message: "Missing tool name" };
        debugLog(env, 1, "MCP tool call: missing tool name");
        return respond({
          jsonrpc: "2.0", id: reqId,
          error: addDebugContext(env, err, { step: "tool_call", reason: "missing_name" }),
        });
      }
      // Check tool exists before dispatching
      const availableTools = MCP_TOOLS.map(t => t.name);
      if (!availableTools.includes(toolName)) {
        const err = { code: -32601, message: `Tool not found: ${toolName}`, available_tools: availableTools };
        debugLog(env, 1, "MCP tool not found:", toolName, "| available:", availableTools.join(","));
        return respond({
          jsonrpc: "2.0", id: reqId,
          error: addDebugContext(env, err, { step: "tool_call", reason: "not_found", requested: toolName }),
        });
      }
      const clientIp = request.headers.get("CF-Connecting-IP") || "unknown";
      const result = await handleMcpToolCall(env, toolName, args, token, clientIp);

      // Log tool call result at debug level 2
      debugLog(env, 2, "MCP tool result", {
        toolName,
        hasError: !!result?.error,
        resultKeys: Object.keys(result || {}),
      });

      return respond({
        jsonrpc: "2.0", id: reqId,
        result: { content: [{ type: "text", text: JSON.stringify(result) }] },
      });
    }

    // server/discover (2026-07-28 RC) — alias for capabilities query
    if (method === "server/discover") {
      return respond({
        jsonrpc: "2.0", id: reqId,
        result: {
          capabilities: { tools: {} },
          serverInfo: getMcpServerInfo(env),
        },
      });
    }

    return respond({
      jsonrpc: "2.0", id: reqId,
      error: { code: -32601, message: `Method not found: ${method}` },
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

async function fetchPublicJson(path) {
  const resp = await fetch(`${PUBLIC_DATA_BASE}/${path}`, {
    headers: { "User-Agent": "MisakaNet-Insights/1.0", Accept: "application/json" },
  });
  if (!resp.ok) throw new Error(`Public data ${resp.status}`);
  return resp.json();
}

// ═══════════════════════════════════════════════════════════════════════════
// Contributor reputation leaderboard (Issue #908)
//
// The source of truth is data/contributor-points.json, the same non-transferable
// point ledger used by scripts/update_contributor_points.py. Period filters are
// calculated from its history so the public view does not confuse all-time
// totals with recent activity.
// ═══════════════════════════════════════════════════════════════════════════

const REPUTATION_MAX_ENTRIES = 20;

function buildReputationLeaderboard(source, period = "all-time", now = Date.now()) {
  const normalizedPeriod = normalizeReputationPeriod(period);
  if (!normalizedPeriod) throw new Error("Unsupported reputation period");

  const contributors = source && typeof source.contributors === "object"
    ? source.contributors
    : {};
  const windowDays = REPUTATION_PERIODS[normalizedPeriod];
  const cutoff = windowDays === null ? null : now - windowDays * 86_400_000;
  const rows = [];

  for (const [login, record] of Object.entries(contributors)) {
    if (!record || typeof record !== "object") continue;
    const history = Array.isArray(record.history) ? record.history : [];
    const events = history.filter((event) => {
      if (cutoff === null) return true;
      const timestamp = parseTimestamp(event && event.timestamp);
      return timestamp !== null && timestamp >= cutoff;
    });
    const historyPoints = events.reduce((sum, event) => {
      const points = Number(event && event.points);
      return Number.isFinite(points) ? sum + points : sum;
    }, 0);
    const ledgerTotal = Number(record.total_points);
    const totalPoints = Number.isFinite(ledgerTotal)
      ? ledgerTotal
      : history.reduce((sum, event) => {
        const points = Number(event && event.points);
        return Number.isFinite(points) ? sum + points : sum;
      }, 0);
    const points = cutoff === null ? totalPoints : historyPoints;

    // A monthly/weekly leaderboard should contain contributors with activity
    // in that window, while all-time preserves a ledger entry even at zero.
    if (cutoff !== null && events.length === 0) continue;
    rows.push({
      login: String(login).slice(0, 64),
      points: roundPoints(points),
      totalPoints: roundPoints(totalPoints),
      activityCount: events.length,
      lastActivity: typeof record.last_activity === "string" ? record.last_activity : null,
    });
  }

  rows.sort((a, b) => b.points - a.points || b.totalPoints - a.totalPoints || a.login.localeCompare(b.login));
  return rows.slice(0, REPUTATION_MAX_ENTRIES).map((row, index) => ({ ...row, rank: index + 1 }));
}

async function handleReputationLeaderboard(request, env) {
  const requested = new URL(request.url).searchParams.get("period") || "all-time";
  const period = normalizeReputationPeriod(requested);
  if (!period) {
    return jsonResponse({
      success: false,
      error: "Unsupported period",
      supportedPeriods: Object.keys(REPUTATION_PERIODS),
    }, 400);
  }

  try {
    let source = env.REPUTATION_DATA;
    if (typeof source === "string") source = JSON.parse(source);
    if (!source || typeof source !== "object") {
      source = await getWithCache(
        env,
        "insights:reputation-points",
        () => fetchPublicJson("contributor-points.json"),
      );
    }
    const contributors = source && typeof source.contributors === "object" ? source.contributors : {};
    return jsonResponse({
      success: true,
      period,
      windowDays: REPUTATION_PERIODS[period],
      updatedAt: typeof source._last_updated === "string" ? source._last_updated : null,
      totalContributors: Object.keys(contributors).length,
      leaderboard: buildReputationLeaderboard(source, period),
      meta: {
        pointsSource: "data/contributor-points.json",
        cashValue: false,
        transferable: false,
      },
    });
  } catch (error) {
    console.error("[reputation] source unavailable", error && error.message);
    return jsonResponse({ success: false, error: "Reputation data unavailable", period }, 502);
  }
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

// ═══════════════════════════════════════════════════════════════════════════
// Lesson coverage dashboard (Issue #905)
//
// Coverage is calculated from the public lesson index and the aggregate
// unsolved-family signals above. It never needs raw search queries: a family is
// covered when at least one published lesson matches its public keyword cluster.
// ═══════════════════════════════════════════════════════════════════════════

function lessonSearchText(lesson) {
  if (!lesson || typeof lesson !== "object") return "";
  const tags = Array.isArray(lesson.tags) ? lesson.tags.join(" ") : "";
  return [lesson.id, lesson.title, lesson.domain, tags, lesson.summary]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function buildLessonCoverage(lessons, unsolved = { families: [], staleLessons: [] }) {
  const allLessons = Array.isArray(lessons) ? lessons : [];
  const publishedLessons = allLessons.filter((lesson) => lesson && lesson.status === "published");
  const unsolvedFamilies = new Map(
    (Array.isArray(unsolved.families) ? unsolved.families : [])
      .map((family) => [family.taskFamily, family]),
  );

  const families = UNSOLVED_FAMILIES.map(([taskFamily, keywords]) => {
    const matching = publishedLessons.filter((lesson) => {
      const text = lessonSearchText(lesson);
      return keywords.some((keyword) => text.includes(keyword));
    });
    const signal = unsolvedFamilies.get(taskFamily) || {};
    const unsolved30d = Number(signal.unsolved30d) || 0;
    const coverageStatus = matching.length === 0
      ? "uncovered"
      : unsolved30d > 0 ? "needs-review" : "covered";
    return {
      taskFamily,
      lessonCount: matching.length,
      coverageStatus,
      unsolved7d: Number(signal.unsolved7d) || 0,
      unsolved30d,
      lastSeen: signal.lastSeen || null,
    };
  });

  const coveredFamilies = families.filter((family) => family.lessonCount > 0).length;
  const gaps = families
    .filter((family) => family.coverageStatus !== "covered")
    .sort((a, b) => b.unsolved30d - a.unsolved30d || a.lessonCount - b.lessonCount || a.taskFamily.localeCompare(b.taskFamily));

  return {
    metrics: {
      totalLessons: allLessons.length,
      publishedLessons: publishedLessons.length,
      totalFamilies: families.length,
      coveredFamilies,
      coveragePercent: families.length ? Math.round((coveredFamilies / families.length) * 1000) / 10 : 0,
      gapCount: gaps.length,
      unsolvedFamilyCount: unsolvedFamilies.size,
      staleLessonCount: Array.isArray(unsolved.staleLessons) ? unsolved.staleLessons.length : 0,
    },
    families,
    gaps,
    staleLessons: Array.isArray(unsolved.staleLessons) ? unsolved.staleLessons : [],
  };
}

async function handleLessonCoverage(env) {
  try {
    let lessons = env.LESSON_DATA;
    if (typeof lessons === "string") lessons = JSON.parse(lessons);
    if (!Array.isArray(lessons)) {
      lessons = await getWithCache(env, "insights:lesson-index", () => fetchPublicJson("lessons.json"));
    }

    let unsolved = env.UNSOLVED_DATA;
    if (typeof unsolved === "string") unsolved = JSON.parse(unsolved);
    if (!unsolved || typeof unsolved !== "object") {
      unsolved = env.MISAKANET_KV
        ? await buildUnsolvedMap(env)
        : { families: [], staleLessons: [] };
    }

    return jsonResponse({
      success: true,
      available: true,
      signalsAvailable: !!env.MISAKANET_KV || !!env.UNSOLVED_DATA,
      generatedAt: new Date().toISOString(),
      ...buildLessonCoverage(lessons, unsolved),
      meta: {
        lessonSource: "data/lessons.json",
        signalSource: "/api/insights/unsolved-map",
        privacy: "public-metadata-and-aggregate-signals",
        raw_query: false,
        pii: false,
      },
    });
  } catch (error) {
    console.error("[coverage] source unavailable", error && error.message);
    return jsonResponse({ success: false, error: "Coverage data unavailable" }, 502);
  }
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
        hasMcpToken: !!env.MCP_TOKEN,
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

    // POST /api/search-index — sync BM25 search index to KV
    if (request.method === "POST" && url.pathname === "/api/search-index") {
      const syncToken = request.headers.get("X-Sync-Token");
      if (!syncToken || !env.SYNC_TOKEN || !timingSafeEqual(syncToken, env.SYNC_TOKEN)) {
        return jsonResponse({ error: "Unauthorized" }, 401);
      }
      if (!env.MISAKANET_KV) return jsonResponse({ error: "KV not configured" }, 500);

      try {
        const body = await request.json();
        if (!body.version || !body.terms || !body.docs) {
          return jsonResponse({ error: "Invalid index format" }, 400);
        }
        await env.MISAKANET_KV.put("worker_search_index", JSON.stringify(body), {
          expirationTtl: 86400 * 7, // 7 days
        });
        return jsonResponse({
          success: true,
          docCount: body.docCount,
          termCount: Object.keys(body.terms).length,
        });
      } catch (e) {
        return jsonResponse({ error: e.message }, 400);
      }
    }

    // GET /api/search-index — get current index stats
    if (request.method === "GET" && url.pathname === "/api/search-index") {
      if (!env.MISAKANET_KV) return jsonResponse({ available: false });
      try {
        const index = await env.MISAKANET_KV.get("worker_search_index", "json");
        if (!index) return jsonResponse({ available: false });
        return jsonResponse({
          available: true,
          docCount: index.docCount,
          termCount: Object.keys(index.terms).length,
          avgDocLen: index.avgDocLen,
          builtAt: index.built_at,
        });
      } catch {
        return jsonResponse({ available: false });
      }
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

      // Secret redaction — synced from workers/lib/redact-patterns.json
      // (single source of truth shared with scripts/intake_redact.py)
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

    // GET /api/insights/pr-genius — PR Genius metrics & workflow statistics (#1035)
    if (request.method === "GET" && url.pathname === "/api/insights/pr-genius") {
      return handlePrGeniusStats(env);
    }

        // GET /api/insights/lesson-coverage — public lesson coverage dashboard (#905)
    if (request.method === "GET" && url.pathname === "/api/insights/lesson-coverage") {
      return handleLessonCoverage(env);
    }
    // GET /api/insights/reputation-leaderboard — public points leaderboard (#908)
    if (request.method === "GET" && url.pathname === "/api/insights/reputation-leaderboard") {
      return handleReputationLeaderboard(request, env);
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
          const dayCount = Object.values(bucket.reasons || {}).reduce((s, r) => s + (typeof r === "number" ? r : r?.count || 0), 0);
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

    // ── One-time pairing code flow (Coogen-inspired) ──

    // POST /mcp/connect — generate a one-time pairing code
    if (request.method === "POST" && url.pathname === "/mcp/connect") {
      if (!env.MISAKANET_KV) return jsonResponse({ error: "KV not configured" }, 503);

      // Rate limit: 3 codes per IP per 10 minutes
      const connIp = request.headers.get("CF-Connecting-IP") || "unknown";
      const connRateKey = `rate:connect:${connIp}`;
      const connRateRaw = await env.MISAKANET_KV.get(connRateKey, "text");
      const connRateCount = connRateRaw ? parseInt(connRateRaw, 10) || 0 : 0;
      if (connRateCount >= 3) return jsonResponse({ error: "Rate limited. Try again later." }, 429);
      await env.MISAKANET_KV.put(connRateKey, String(connRateCount + 1), { expirationTtl: 600 });

      // Generate 6-char alphanumeric code (cryptographically secure)
      const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"; // no I/O/0/1 for readability
      let code = "";
      const codeBytes = new Uint8Array(6);
      crypto.getRandomValues(codeBytes);
      for (let i = 0; i < 6; i++) code += chars[codeBytes[i] % chars.length];

      // Store in KV: pending, 10 min TTL
      await env.MISAKANET_KV.put(`pair:${code}`, JSON.stringify({
        status: "pending",
        created: new Date().toISOString(),
        ip: connIp,
      }), { expirationTtl: 600 });

      return jsonResponse({ code, expires_in: 600 });
    }

    // POST /mcp/pair — exchange pairing code for short-lived MCP token
    if (request.method === "POST" && url.pathname === "/mcp/pair") {
      if (!env.MISAKANET_KV) return jsonResponse({ error: "KV not configured" }, 503);

      let pairBody;
      try { pairBody = await request.json(); } catch { return jsonResponse({ error: "Invalid JSON" }, 400); }

      const code = sanitizeIdentifier(pairBody.code, 10);
      if (!code || code.length !== 6) return jsonResponse({ error: "Invalid code format" }, 400);

      const pairKey = `pair:${code}`;
      const pairData = await env.MISAKANET_KV.get(pairKey, "json");
      if (!pairData) return jsonResponse({ error: "Invalid or expired code" }, 404);
      if (pairData.status !== "pending") return jsonResponse({ error: "Code already used" }, 409);

      // Mark code as used
      pairData.status = "used";
      pairData.used_at = new Date().toISOString();
      pairData.used_ip = request.headers.get("CF-Connecting-IP") || "unknown";
      await env.MISAKANET_KV.put(pairKey, JSON.stringify(pairData), { expirationTtl: 86400 });

      // Generate short-lived token (24h, cryptographically secure)
      const tokenChars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-";
      let token = "mcp_";
      const pairTokenBytes = new Uint8Array(32);
      crypto.getRandomValues(pairTokenBytes);
      for (let i = 0; i < 32; i++) token += tokenChars[pairTokenBytes[i] % tokenChars.length];

      // Store token in KV for validation
      await env.MISAKANET_KV.put(`mcp_token:${token}`, JSON.stringify({
        created: new Date().toISOString(),
        expires: new Date(Date.now() + 86400000).toISOString(),
        ip: pairData.ip,
      }), { expirationTtl: 86400 });

      return jsonResponse({ token, expires_in: 86400 });
    }

    // POST /mcp — Streamable HTTP MCP endpoint (read-only tools)
    if (request.method === "POST" && url.pathname === "/mcp") {
      const accept = request.headers.get("Accept") || "";
      const useSse = accept.includes("text/event-stream");
      return handleMcpRequest(request, env, useSse);
    }
    // OPTIONS /mcp — CORS preflight (browser clients need this)
    if (request.method === "OPTIONS" && url.pathname === "/mcp") {
      return new Response(null, {
        status: 204,
        headers: {
          ...CORS_HEADERS,
          "Access-Control-Allow-Headers": "Content-Type, Authorization, MCP-Protocol-Version, Mcp-Method, Mcp-Name, Mcp-Session-Id",
          "Access-Control-Max-Age": "86400",
        },
      });
    }
    // GET /mcp — SSE stream for server-initiated messages
    if (request.method === "GET" && url.pathname === "/mcp") {
      const accept = request.headers.get("Accept") || "";
      if (accept.includes("text/event-stream")) {
        // SSE stream — keep connection open for server-initiated notifications
        const stream = new ReadableStream({
          start(controller) {
            const encoder = new TextEncoder();
            controller.enqueue(encoder.encode("event: connected\ndata: {}\n\n"));
            // Keep-alive ping every 30s
            const interval = setInterval(() => {
              try {
                controller.enqueue(encoder.encode(": keepalive\n\n"));
              } catch {
                clearInterval(interval);
              }
            }, 30000);
            // Note: In Cloudflare Workers, the stream closes when the request is cancelled
          },
        });
        return new Response(stream, {
          headers: {
            "content-type": "text/event-stream",
            "cache-control": "no-cache",
            ...CORS_HEADERS,
          },
        });
      }
      return new Response(JSON.stringify({ error: "Method Not Allowed. Use POST for MCP Streamable HTTP transport, or GET with Accept: text/event-stream for SSE." }), {
        status: 405,
        headers: { "content-type": "application/json", "Accept-Post": "application/json, text/event-stream", ...CORS_HEADERS },
      });
    }

    // GET /connect — pairing code landing page (human entry point)
    if (request.method === "GET" && url.pathname === "/connect") {
      return new Response(`<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Connect MisakaNet MCP</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #0d1117; color: #e6edf3; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; }
  .card { max-width: 520px; text-align: center; background: #161b22; border: 1px solid #30363d; border-radius: 16px; padding: 40px; }
  h1 { color: #f0c040; font-size: 24px; margin-bottom: 8px; }
  p { color: #8b949e; font-size: 14px; line-height: 1.7; }
  .code { font-family: monospace; font-size: 32px; color: #58a6ff; background: #0d1117; padding: 16px 24px; border-radius: 8px; letter-spacing: 4px; margin: 20px 0; border: 1px solid #30363d; }
  .btn { display: inline-block; padding: 12px 24px; background: #238636; color: white; text-decoration: none; border-radius: 8px; font-weight: 600; cursor: pointer; border: none; font-size: 14px; }
  .btn:hover { background: #2ea043; }
  .btn-voice { background: transparent; border: 1px solid #a371f7; color: #a371f7; padding: 8px 16px; font-size: 12px; }
  .btn-voice:hover { background: rgba(163,113,247,0.1); }
  .steps { text-align: left; margin: 20px 0; }
  .steps li { color: #c9d1d9; margin: 8px 0; font-size: 14px; }
  .timer { color: #f85149; font-size: 12px; margin-top: 8px; }
  @media (max-width: 768px) {
    body { padding: 16px; }
    .card { padding: 24px; }
    .code { font-size: 24px; letter-spacing: 3px; padding: 14px 20px; word-break: break-all; }
    .btn { min-height: 44px; padding: 12px 20px; font-size: 14px; }
    .btn-voice { min-height: 44px; padding: 10px 16px; font-size: 13px; }
  }
  @media (max-width: 480px) {
    body { padding: 12px; }
    .card { padding: 16px; max-width: 100%; }
    .code { font-size: 18px; letter-spacing: 2px; padding: 12px 16px; }
    .btn { min-height: 48px; padding: 14px 16px; font-size: 13px; }
    .btn-voice { min-height: 48px; padding: 12px 14px; font-size: 12px; }
    .steps { margin: 16px 0; }
    .steps li { font-size: 13px; }
  }
</style></head>
<body>
<div class="card">
  <h1>Connect MisakaNet MCP</h1>
  <p>Get a one-time pairing code to connect your AI agent.</p>
  <button class="btn" onclick="getCode()">Generate Code</button>
  <div id="voice-section" style="margin-top:12px;">
    <button class="btn btn-voice" onclick="enableMisakaVoice()">Enable Misaka Voice</button>
  </div>
  <div id="result" style="display:none">
    <div class="code" id="code">------</div>
    <div class="timer" id="timer">Expires in 10:00</div>
    <div class="steps">
      <p><strong>Next steps:</strong></p>
      <ol>
        <li>Copy the code above</li>
        <li>Paste it to your AI agent</li>
        <li>The agent will call <code>/mcp/pair</code> to get a token</li>
        <li>Use the token to access <code>/mcp</code></li>
      </ol>
    </div>
    <div style="margin-top:16px;padding:12px;background:rgba(163,113,247,0.1);border:1px solid rgba(163,113,247,0.3);border-radius:8px;font-size:13px;color:#a371f7;">
      <strong>🧠 Upgrade to Shared Vision Mode</strong><br>
      Complete registration + avatar to unlock the Misaka Network identity badge.<br>
      <span style="color:#8b949e;font-size:12px;">御坂ネットワークの共有視界モードにアップグレードできます。</span>
    </div>
  </div>
</div>
<script>
const MISAKA_VOICE_KEY = "misakanet_voice_enabled";
const MISAKA_VOICE = {
  connect: "/assets/voice/connect-success.v2.mp3",
  pair: "/assets/voice/pair-success.v2.mp3",
  found: "/assets/voice/lesson-found.v2.mp3",
  warning: "/assets/voice/failure-warning.v2.mp3",
};

function isMisakaVoiceEnabled() {
  return localStorage.getItem(MISAKA_VOICE_KEY) === "1";
}

function enableMisakaVoice() {
  localStorage.setItem(MISAKA_VOICE_KEY, "1");
  document.getElementById("voice-section").innerHTML = '<span style="color:#a371f7;font-size:12px;">Voice enabled</span>';
  playMisakaVoice("connect");
}

function playMisakaVoice(key) {
  if (!isMisakaVoiceEnabled()) return;
  const src = MISAKA_VOICE[key];
  if (!src) return;
  const audio = new Audio(src);
  audio.volume = 0.75;
  audio.play().catch(() => {});
}

async function getCode() {
  const r = await fetch('/mcp/connect', {method:'POST'});
  const d = await r.json();
  if(d.code) {
    document.getElementById('code').textContent = d.code;
    document.getElementById('result').style.display = 'block';
    let s = d.expires_in || 600;
    setInterval(() => { if(s>0){s--;document.getElementById('timer').textContent='Expires in '+Math.floor(s/60)+':'+(s%60<10?'0':'')+s%60;}}, 1000);
    playMisakaVoice("connect");
  }
}
</script>
</body>
</html>`, {
        status: 200,
        headers: { "content-type": "text/html;charset=utf-8" },
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

    // 定期清理 rateMap (probabilistic, not security-sensitive)
    if (crypto.getRandomValues(new Uint8Array(1))[0] < 6) cleanRateMap();

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

// ── PR Genius Workflow Stats (Issue #1035) ──
async function handlePrGeniusStats(env) {
  const token = env.REGISTER_TOKEN;
  try {
    const data = await getWithCache(env, "proxy:pr-genius-stats", async () => {
      if (token) {
        return fetchFromGitHub(token, "data/pr-genius-stats.json");
      }
      const resp = await fetch("https://raw.githubusercontent.com/" + REPO + "/main/data/pr-genius-stats.json");
      if (!resp.ok) throw new Error("Failed to fetch pr-genius-stats.json: " + resp.status);
      return resp.json();
    });
    return jsonResponse(data);
  } catch (err) {
    return jsonResponse({ error: "Failed to load PR Genius statistics: " + err.message }, 502);
  }
}

export {
  IDENTITY_AURA,
  MAX_MCP_REQUEST_BYTES,
  UNSOLVED_FAMILY_WHITELIST,
  UNSOLVED_REASONS,
  UNSOLVED_WINDOW_DAYS,
  buildUnsolvedMap,
  buildLessonCoverage,
  classifyTaskFamily,
  buildReputationLeaderboard,
  getIdentityAura,
  handleSearchSignal,
  handleLessonCoverage,
  handleReputationLeaderboard,
  handleUnsolvedMap,
  handlePrGeniusStats,
  recordStaleLesson,
  recordUnsolvedSearch,
};
