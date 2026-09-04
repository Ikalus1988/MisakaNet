/**
 * Pure utility functions — no side effects, no env/request dependency.
 * Extracted from register-proxy-sw.js for maintainability.
 */

import intakeHints from "./intake-hints.json" with { type: "json" };

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

// ── Intake kind inference (question vs failure) ──
// Used by misakanet_submit_intake and the search no-match suggestion so that
// how-to / knowledge-gap submissions are routed as `question` instead of being
// treated as malformed failure lessons (see #1396: a PT-BR how-to arrived as
// kind=missing_lesson, got scored 16.9/100 by the lesson auto-review and was
// auto-rejected to badcase). Conservative on purpose: only clear question
// phrasing with NO failure evidence flips the kind.

const INTAKE_KINDS = intakeHints.intake_kinds;
const QUESTION_HINTS = intakeHints.question_hints.map((pattern) => new RegExp(pattern, "i"));
const FAILURE_HINTS = intakeHints.failure_hints.map((pattern) => new RegExp(pattern, "i"));

function looksLikeQuestion(text) {
  return QUESTION_HINTS.some((re) => re.test(String(text || "")));
}

function hasFailureEvidence(text) {
  return FAILURE_HINTS.some((re) => re.test(String(text || "")));
}

/**
 * Resolve the intake kind for a submission.
 *
 * - An explicit, valid kind (stale_lesson / new_lesson_candidate / question /
 *   missing_lesson) is honored as-is, EXCEPT kind="missing_lesson": callers
 *   are still guided toward it by older copy, so a clear question with zero
 *   failure evidence is re-routed to "question".
 * - An absent kind defaults to "missing_lesson", upgraded to "question" under
 *   the same rule.
 *
 * Returns { kind, autoDetected }.
 */
function inferIntakeKind({ kind, problem, error, what_tried, fix, verification } = {}) {
  const explicit = String(kind || "").trim();
  if (explicit && !INTAKE_KINDS.includes(explicit)) {
    return { kind: "missing_lesson", autoDetected: false, invalid: explicit };
  }
  const problemText = `${problem || ""} ${what_tried || ""}`;
  const structuredFailure = Boolean(error || fix || verification);
  const isQuestion = looksLikeQuestion(problemText) && !structuredFailure && !hasFailureEvidence(problemText);
  if (explicit === "missing_lesson" || !explicit) {
    if (isQuestion) return { kind: "question", autoDetected: true };
    return { kind: "missing_lesson", autoDetected: false };
  }
  return { kind: explicit, autoDetected: false };
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
  INTAKE_KINDS,
  QUESTION_HINTS,
  FAILURE_HINTS,
  looksLikeQuestion,
  hasFailureEvidence,
  inferIntakeKind,
};
