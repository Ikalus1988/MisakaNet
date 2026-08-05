'use strict';

/**
 * Secret redaction module for fatal-guard.
 * Independently testable (Step 4 / T16).
 */

const PATTERNS = [
  { name: 'jwt',      re: /eyJ[\w-]+\.[\w-]+\.[\w-]+/g },
  { name: 'dsn',      re: /(?:postgres|postgresql|mysql|mongodb|redis|amqp):\/\/[^\s"']+/gi },
  { name: 'aws_key',  re: /AKIA[0-9A-Z]{16}/g },
  { name: 'gcp_key',  re: /AIza[0-9A-Za-z_\-]{35}/g },
  { name: 'openai',   re: /sk-[A-Za-z0-9]{20,}/g },
  { name: 'gh_token', re: /gh[pousr]_[A-Za-z0-9]{36,}/g },
  { name: 'authz',    re: /(?:authorization|x-api-key|cookie|set-cookie)\s*[:=]\s*[^\s'"]+/gi },
  { name: 'long_tok', re: /\b[A-Za-z0-9_\-]{40,}\b/g },
];

function redact(s) {
  if (typeof s !== 'string' || !s) return s;
  let out = s;
  for (const p of PATTERNS) out = out.replace(p.re, `[REDACTED:${p.name}]`);
  return out;
}

module.exports = { redact, PATTERNS };
