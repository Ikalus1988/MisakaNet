#!/usr/bin/env node
/**
 * @misaka-net/fatal-guard
 *
 * Zero-dependency non-invasive fatal error guard.
 *
 * This module exports:
 *   - buildPayload(reason)  — Build a 4-field JSON payload
 *   - runHandler(reason)    — Fire the external handler (if FATAL_HANDLER is set)
 *   - FatalPayload          — Type signature (JSDoc)
 *
 * For automatic hook registration, use:
 *   node -r @misaka-net/fatal-guard/register ./app.js
 *
 * Or import and attach manually:
 *   const { runHandler } = require('@misaka-net/fatal-guard');
 *   process.on('uncaughtException', (err) => runHandler('uncaught_exception'));
 */

const { spawn } = require('node:child_process');
const { redact } = require('./src/lib/redact');

/**
 * @typedef {Object} FatalPayload
 * @property {number} schemaVersion — Payload format version (always 1)
 * @property {string} reason — "uncaught_exception" | "unhandled_rejection" | "exit_code"
 * @property {string} timestamp — ISO 8601 timestamp
 * @property {number} pid — Process ID
 * @property {string} [errorName] — Error constructor name (v0.3+)
 * @property {string} [message] — Redacted error message (v0.3+)
 * @property {string} [stackSnippet] — Redacted stack trace snippet (v0.3+)
 */

/**
 * Build a JSON payload string with diagnostic fields.
 * @param {string} reason
 * @param {Error|string} [error] — optional error object or message
 * @returns {string}
 */
function buildPayload(reason, error) {
  const payload = {
    schemaVersion: 1,
    reason,
    timestamp: new Date().toISOString(),
    pid: process.pid,
  };

  if (error) {
    const err = typeof error === 'string' ? { message: error } : error;
    payload.errorName = err.name || 'Error';
    payload.message = redact(String(err.message || '')).slice(0, 300);
    if (err.stack) {
      payload.stackSnippet = redact(String(err.stack)).slice(0, 1000);
    }
  }

  return JSON.stringify(payload);
}

/**
 * Fire-and-forget external handler invocation.
 * Reads FATAL_HANDLER env var (or fallback chain), spawns with JSON payload as argv[1].
 * Never throws. Never blocks shutdown.
 *
 * @param {string} reason
 * @param {Error|string} [error] — optional error object for diagnostic payload
 * @param {string} [customPayload] — optional pre-built JSON payload (wrapper mode passes extra fields)
 */
function runHandler(reason, error, customPayload) {
  const handler = (
    process.env.FATAL_HANDLER ||
    process.env.MISAKANET_ERROR_HANDLER ||
    process.env.VITE_ERROR_HANDLER ||
    process.env.E2B_ERROR_HANDLER ||
    process.env.OPENCLAW_ERROR_HANDLER ||
    ''
  ).trim();
  if (!handler) return;

  try {
    const payload = customPayload || buildPayload(reason, error);
    const child = spawn(handler, [payload], {
      stdio: 'ignore',
      detached: true,
      shell: false,
    });
    child.on('error', () => {});
    child.unref();
  } catch (_) {}
}

module.exports = { buildPayload, runHandler };
