/**
 * Pure utility functions — no side effects, no env/request dependency.
 * Extracted from register-proxy-sw.js for maintainability.
 */

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, MCP-Protocol-Version, Accept, Origin",
  "Access-Control-Max-Age": "86400",
};

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...CORS_HEADERS },
  });
}

function mcpJsonResponse(body, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "MCP-Protocol-Version": "2025-06-18",
      ...CORS_HEADERS,
      ...extraHeaders,
    },
  });
}

function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return result === 0;
}

function sanitizeIdentifier(val, maxLen = 50) {
  if (!val) return "";
  if (val.length > maxLen) val = val.slice(0, maxLen);
  return val.replace(/[^\w一-龥\-]/g, "");
}

function parseTimestamp(value) {
  const timestamp = Date.parse(String(value || ""));
  return Number.isFinite(timestamp) ? timestamp : null;
}

function roundPoints(value) {
  return Math.round(value * 100) / 100;
}

const REPUTATION_PERIODS = Object.freeze(Object.create(null, {
  "all-time": { value: null, enumerable: true },
  monthly: { value: 30, enumerable: true },
  weekly: { value: 7, enumerable: true },
}));

function normalizeReputationPeriod(value) {
  const period = String(value || "all-time").toLowerCase();
  if (period === "all_time" || period === "alltime") return "all-time";
  if (period === "month") return "monthly";
  if (period === "week") return "weekly";
  return period in REPUTATION_PERIODS ? period : null;
}

const RATE_LIMIT_WINDOW = 30_000;
const rateMap = new Map();

function cleanRateMap() {
  const now = Date.now();
  for (const [key, timestamp] of rateMap) {
    if (now - timestamp > RATE_LIMIT_WINDOW) rateMap.delete(key);
  }
}

function validateMcpOrigin(request) {
  const origin = request.headers.get("Origin") || "";
  const MCP_ALLOWED_ORIGINS = [
    "https://claude.ai",
    "https://cursor.sh",
    "https://cursor.com",
    "https://openai.com",
    "https://chat.openai.com",
    "https://chatgpt.com",
    "",
  ];
  return MCP_ALLOWED_ORIGINS.includes(origin);
}

export {
  CORS_HEADERS,
  jsonResponse,
  mcpJsonResponse,
  timingSafeEqual,
  sanitizeIdentifier,
  parseTimestamp,
  roundPoints,
  REPUTATION_PERIODS,
  normalizeReputationPeriod,
  RATE_LIMIT_WINDOW,
  rateMap,
  cleanRateMap,
  validateMcpOrigin,
};
