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

const { spawn, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { redact } = require('./src/lib/redact');
const { buildSpawnSpec } = require('./src/lib/spawn-command');

const HANDLER_TIMEOUT_MS = 5000;

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
    payload.message = redact(String(err.message || '')).slice(0, 500);
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
    let handlerArgs = [];
    if (process.env.FATAL_HANDLER_ARGS) {
      try {
        const parsed = JSON.parse(process.env.FATAL_HANDLER_ARGS);
        if (Array.isArray(parsed) && parsed.every((arg) => typeof arg === 'string')) {
          handlerArgs = parsed;
        }
      } catch (_) {}
    }
    const invocation = buildSpawnSpec(handler, [...handlerArgs, payload]);
    // Default to non-blocking detached/unref on POSIX so handlers can finish
    // after process.exit(). On Windows the parent kills the job object on
    // exit, so we must block until the handler finishes via spawnSync (matches
    // bin/fatal-guard.js). Without this, the handler dies with `process.exit()`
    // and never writes the tombstone (#1373 problem 4).
    if (process.platform === 'win32') {
      const payloadTmp = path.join(os.tmpdir(), `fatal-guard-${process.pid}.json`);
      try { fs.writeFileSync(payloadTmp, payload); } catch (_) {}
      // sanitizeCommand rejects shell metacharacters before any spawn, so the
      // env-derived FATAL_HANDLER can never smuggle a shell command. shell:
      // false is a literal at the call site (CodeQL sees a non-shell spawn).
      if (invocation.rejected) return;
      spawnSync(invocation.command, invocation.args, {
        timeout: HANDLER_TIMEOUT_MS,
        stdio: 'ignore',
        shell: false,
        env: {
          ...process.env,
          // Avoid UnicodeEncodeError on Windows cp1252 when the handler is a
          // Python script that prints the tombstone. PYTHONIOENCODING=utf-8
          // forces UTF-8 stdio regardless of the active code page (#1373
          // problem 3).
          PYTHONIOENCODING: 'utf-8',
          FATAL_PAYLOAD_FILE: payloadTmp,
          FATAL_PAYLOAD: payload,
        },
        ...invocation.options,
      });
    } else {
      // sanitizeCommand rejects shell metacharacters before any spawn; shell:
      // false is a literal here so CodeQL does not treat this as a shell sink.
      if (invocation.rejected) return;
      const child = spawn(invocation.command, invocation.args, {
        stdio: 'ignore',
        detached: true,
        shell: false,
        env: {
          ...process.env,
          PYTHONIOENCODING: 'utf-8',
        },
        ...invocation.options,
      });
      child.on('error', () => {});
      child.unref();
    }
  } catch (_) {}
}

module.exports = { buildPayload, runHandler };
