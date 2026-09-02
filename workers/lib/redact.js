/**
 * Shared redaction module — single source of truth for secret patterns.
 *
 * Both the /api/intake route and the MCP misakanet_submit_intake tool
 * use this module. Patterns live in redact-patterns.json.
 */
const patterns = require("./redact-patterns.json");

const compiled = patterns.map((p) => ({
  id: p.id,
  regex: new RegExp(p.pattern, p.flags),
  replacement: p.replacement,
}));

/**
 * Redact secrets from text. Truncates to maxLen characters.
 * @param {string} text
 * @param {number} [maxLen=2000]
 * @returns {string}
 */
function redactText(text, maxLen = 2000) {
  if (!text) return "";
  let result = String(text).slice(0, maxLen);
  for (const { regex, replacement } of compiled) {
    result = result.replace(regex, replacement);
  }
  return result;
}

/**
 * Return the list of pattern IDs for diagnostics.
 * @returns {string[]}
 */
function patternIds() {
  return compiled.map((p) => p.id);
}

module.exports = { redactText, patternIds, patterns };
