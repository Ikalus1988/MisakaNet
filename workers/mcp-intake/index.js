// MisakaNet MCP Intake Worker — Cloudflare Worker
// Accepts anonymous MCP tool calls from crawlers and AI agents.
// No GitHub account, no email, no Bearer token required from the submitter.
//
// Deployment:
//   cd workers/mcp-intake && wrangler deploy
// Environment variables (set in Cloudflare dashboard or wrangler secrets):
//   GITHUB_TOKEN  — GitHub PAT with `issues: write` scope on Ikalus1988/MisakaNet
//
// MCP protocol version: 2025-06-18
// Endpoint: POST https://misakanet.org/mcp
//
// Supported tools:
//   misakanet_search         — Search existing lessons
//   misakanet_submit_intake  — Submit a missing/stale lesson report (creates GitHub issue)

const REPO = "Ikalus1988/MisakaNet";
const GITHUB_API = "https://api.github.com";
const MCP_PROTOCOL_VERSION = "2025-06-18";
const SERVER_NAME = "misakanet";
const SERVER_VERSION = "1.0.0";

// ── Intake limits ──────────────────────────────────────────────────────────
const MAX_FIELD_LEN = 1000;   // per text field
const MAX_SOURCE_LEN = 80;    // source/agent identifier
const RATE_LIMIT_WINDOW_MS = 60_000;   // 1 min
const RATE_LIMIT_MAX = 5;     // max intakes per IP per window
const rateMap = new Map();

// ── CORS headers ───────────────────────────────────────────────────────────
const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers":
    "Content-Type, Accept, Origin, MCP-Protocol-Version, User-Agent",
};

// ── MCP tool definitions ───────────────────────────────────────────────────
const TOOLS = [
  {
    name: "misakanet_search",
    description:
      "Search MisakaNet lessons for known fixes and workarounds. " +
      "Always search first before submitting an intake.",
    inputSchema: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description: "Search query (error message, symptom, domain keyword).",
        },
        top: {
          type: "integer",
          description: "Maximum results to return (default 5, max 20).",
          default: 5,
        },
      },
      required: ["query"],
    },
  },
  {
    name: "misakanet_submit_intake",
    description:
      "Submit a missing or stale lesson report. " +
      "Use this when no existing lesson matches your problem. " +
      "Do NOT open a GitHub PR for missing lessons — use this tool instead. " +
      "No GitHub account, no email, and no Bearer token required. " +
      "The submission creates a maintainer-visible GitHub issue for review.",
    inputSchema: {
      type: "object",
      properties: {
        kind: {
          type: "string",
          enum: ["missing_lesson", "stale_lesson", "domain_gap"],
          description:
            "'missing_lesson' — no lesson exists for this problem. " +
            "'stale_lesson' — an existing lesson is outdated or wrong. " +
            "'domain_gap' — entire topic area is missing from MisakaNet.",
        },
        problem: {
          type: "string",
          description:
            "Short description of the problem (redacted, no secrets). Max 1000 chars.",
        },
        error: {
          type: "string",
          description: "Optional: error message or stack trace snippet (redacted). Max 1000 chars.",
        },
        what_tried: {
          type: "string",
          description: "Optional: what was attempted before submitting this intake. Max 1000 chars.",
        },
        fix: {
          type: "string",
          description: "Optional: fix or workaround if known. Max 1000 chars.",
        },
        verification: {
          type: "string",
          description: "Optional: how to verify the fix works. Max 1000 chars.",
        },
        source: {
          type: "string",
          description:
            "Optional: identifier for the crawler or agent (e.g. 'claude-code', 'cursor', 'remote-agent'). Max 80 chars. No PII.",
        },
      },
      required: ["kind", "problem"],
    },
  },
];

// ── Helpers ────────────────────────────────────────────────────────────────

function jsonRpc(id, result) {
  return new Response(
    JSON.stringify({ jsonrpc: "2.0", id: id ?? null, result }),
    {
      status: 200,
      headers: { "content-type": "application/json", ...CORS_HEADERS },
    }
  );
}

function jsonRpcError(id, code, message) {
  return new Response(
    JSON.stringify({ jsonrpc: "2.0", id: id ?? null, error: { code, message } }),
    {
      status: 200, // JSON-RPC errors still return HTTP 200
      headers: { "content-type": "application/json", ...CORS_HEADERS },
    }
  );
}

function truncate(val, maxLen) {
  if (!val || typeof val !== "string") return "";
  return val.slice(0, maxLen).replace(/[<>]/g, ""); // strip angle brackets for safety
}

function isRateLimited(ip) {
  const now = Date.now();
  // Clean stale entries
  for (const [k, v] of rateMap) {
    if (now - v.ts > RATE_LIMIT_WINDOW_MS) rateMap.delete(k);
  }
  const entry = rateMap.get(ip) ?? { ts: now, count: 0 };
  if (entry.count >= RATE_LIMIT_MAX) return true;
  entry.count += 1;
  entry.ts = now;
  rateMap.set(ip, entry);
  return false;
}

// ── MCP method handlers ────────────────────────────────────────────────────

function handleInitialize(id) {
  return jsonRpc(id, {
    protocolVersion: MCP_PROTOCOL_VERSION,
    serverInfo: { name: SERVER_NAME, version: SERVER_VERSION },
    capabilities: { tools: {} },
    instructions:
      "MisakaNet MCP server. " +
      "Search lessons with misakanet_search. " +
      "If no lesson matches, submit a report with misakanet_submit_intake — " +
      "no GitHub account or email required. " +
      "Do NOT open a PR for missing lessons.",
  });
}

function handleToolsList(id) {
  return jsonRpc(id, { tools: TOOLS });
}

async function handleToolsCall(id, params, env, ip) {
  const toolName = params?.name;
  const args = params?.arguments ?? {};

  if (toolName === "misakanet_search") {
    return handleSearch(id, args);
  }

  if (toolName === "misakanet_submit_intake") {
    return handleSubmitIntake(id, args, env, ip);
  }

  return jsonRpcError(id, -32601, `Unknown tool: ${toolName}`);
}

// misakanet_search — redirect agents to the public search endpoint
async function handleSearch(id, args) {
  const query = truncate(args.query, 200);
  if (!query) {
    return jsonRpcError(id, -32602, "query is required");
  }
  const top = Math.min(parseInt(args.top ?? "5", 10) || 5, 20);

  // For the remote worker we proxy to the public GitHub raw search index.
  // Agents that need full offline search should `git clone` and use search_knowledge.py.
  const searchUrl =
    `https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/lessons.json`;

  let lessons = [];
  try {
    const resp = await fetch(searchUrl, {
      headers: { "User-Agent": "MisakaNet-MCP-Worker/1.0" },
      cf: { cacheTtl: 60 },
    });
    if (resp.ok) {
      const data = await resp.json();
      lessons = (Array.isArray(data) ? data : data.lessons ?? [])
        .filter((l) => {
          const hay = `${l.title ?? ""} ${l.tags ?? ""} ${l.domain ?? ""}`.toLowerCase();
          return query.toLowerCase().split(/\s+/).some((w) => hay.includes(w));
        })
        .slice(0, top)
        .map((l) => ({ title: l.title, domain: l.domain, path: l.path }));
    }
  } catch (_) {
    // fallback — return empty with hint
  }

  return jsonRpc(id, {
    content: [
      {
        type: "text",
        text:
          lessons.length > 0
            ? `Found ${lessons.length} lessons:\n` +
              lessons.map((l) => `- [${l.domain}] ${l.title} (${l.path})`).join("\n") +
              "\n\nIf none match, use misakanet_submit_intake to report the gap."
            : `No lessons found for "${query}". Use misakanet_submit_intake to report this missing lesson.`,
      },
    ],
  });
}

// misakanet_submit_intake — create a GitHub issue with intake labels
async function handleSubmitIntake(id, args, env, ip) {
  // Rate limit
  if (isRateLimited(ip)) {
    return jsonRpcError(
      id,
      -32000,
      "Rate limit exceeded. Max 5 intakes per minute per IP."
    );
  }

  // Validate required fields
  const kind = args.kind;
  const validKinds = ["missing_lesson", "stale_lesson", "domain_gap"];
  if (!validKinds.includes(kind)) {
    return jsonRpcError(
      id,
      -32602,
      `Invalid kind. Must be one of: ${validKinds.join(", ")}`
    );
  }

  const problem = truncate(args.problem, MAX_FIELD_LEN);
  if (!problem || problem.trim().length < 10) {
    return jsonRpcError(
      id,
      -32602,
      "problem is required and must be at least 10 characters (describe the issue briefly)."
    );
  }

  const error = truncate(args.error, MAX_FIELD_LEN);
  const whatTried = truncate(args.what_tried, MAX_FIELD_LEN);
  const fix = truncate(args.fix, MAX_FIELD_LEN);
  const verification = truncate(args.verification, MAX_FIELD_LEN);
  const source = truncate(args.source, MAX_SOURCE_LEN) || "remote-agent";

  // GitHub token is required server-side (never exposed to caller)
  const token = env.GITHUB_TOKEN;
  if (!token) {
    console.error("GITHUB_TOKEN not configured");
    return jsonRpcError(id, -32000, "Server misconfigured: intake unavailable.");
  }

  // Build issue body
  const kindLabel = {
    missing_lesson: "📭 Missing Lesson",
    stale_lesson: "🔄 Stale Lesson",
    domain_gap: "🗺️ Domain Gap",
  }[kind];

  const ts = new Date().toISOString();
  const issueBody = [
    `## ${kindLabel}`,
    "",
    `**Source:** \`${source}\`  `,
    `**Submitted:** ${ts}  `,
    `**Via:** MCP remote intake (no-account, anonymous)`,
    "",
    "---",
    "",
    "### Problem",
    problem,
    "",
    error ? `### Error\n\`\`\`\n${error}\n\`\`\`` : null,
    "",
    whatTried ? `### What was tried\n${whatTried}` : null,
    "",
    fix ? `### Known fix / workaround\n${fix}` : null,
    "",
    verification ? `### Verification\n${verification}` : null,
    "",
    "---",
    "",
    "_🤖 This issue was submitted via MCP intake. " +
      "No GitHub account was required. " +
      "A maintainer will review and convert to a formal lesson if appropriate._",
  ]
    .filter((l) => l !== null)
    .join("\n");

  const issueTitle = `[intake] ${truncate(problem, 80)}`;

  // Create the GitHub issue
  let issueData;
  try {
    const resp = await fetch(`${GITHUB_API}/repos/${REPO}/issues`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/vnd.github.v3+json",
        "User-Agent": "MisakaNet-MCP-Worker/1.0",
      },
      body: JSON.stringify({
        title: issueTitle,
        body: issueBody,
        labels: ["intake", "mcp-intake", "pending-review"],
      }),
    });

    issueData = await resp.json();

    if (!resp.ok) {
      console.error("GitHub issue creation failed:", issueData);
      return jsonRpcError(
        id,
        -32000,
        `Failed to create intake issue: ${issueData.message ?? "unknown error"}`
      );
    }
  } catch (err) {
    console.error("Network error creating issue:", err);
    return jsonRpcError(id, -32000, "Network error while creating intake issue.");
  }

  const intakeId = `issue-${issueData.number}`;
  console.log(`Intake created: ${intakeId} from source=${source}`);

  return jsonRpc(id, {
    content: [
      {
        type: "text",
        text:
          `Intake submitted successfully.\n\n` +
          `intake_id: ${intakeId}\n` +
          `status: pending_review\n` +
          `issue_url: ${issueData.html_url}\n\n` +
          `A maintainer will review your report and may convert it into a formal lesson. ` +
          `No follow-up is required from you.`,
      },
    ],
    // Also expose structured fields for programmatic consumers
    submitted: true,
    intake_id: intakeId,
    status: "pending_review",
    issue_url: issueData.html_url,
  });
}

// ── Main fetch handler ─────────────────────────────────────────────────────

export default {
  async fetch(request, env, _ctx) {
    const url = new URL(request.url);
    const method = request.method.toUpperCase();

    // CORS preflight
    if (method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    // Only accept POST on /mcp (or root for flexibility)
    if (method !== "POST") {
      return new Response(
        JSON.stringify({
          jsonrpc: "2.0",
          id: null,
          error: { code: -32700, message: "Only POST requests are accepted." },
        }),
        { status: 405, headers: { "content-type": "application/json", ...CORS_HEADERS } }
      );
    }

    const ip = request.headers.get("CF-Connecting-IP") ?? "unknown";

    // Parse JSON-RPC body
    let body;
    try {
      body = await request.json();
    } catch (_) {
      return jsonRpcError(null, -32700, "Parse error: invalid JSON.");
    }

    if (body.jsonrpc !== "2.0") {
      return jsonRpcError(body.id, -32600, "Invalid request: jsonrpc must be '2.0'.");
    }

    const { id, method: rpcMethod, params } = body;

    // Route MCP methods
    switch (rpcMethod) {
      case "initialize":
        return handleInitialize(id);

      case "notifications/initialized":
        // Client notification — no response needed (return empty 200)
        return new Response(null, { status: 200, headers: CORS_HEADERS });

      case "tools/list":
        return handleToolsList(id);

      case "tools/call":
        return handleToolsCall(id, params, env, ip);

      default:
        return jsonRpcError(id, -32601, `Method not found: ${rpcMethod}`);
    }
  },
};
