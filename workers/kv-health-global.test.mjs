// KV write health, made global (2026-09-20, #1822 + #1890).
//
// What went wrong in production that day: every KV write failed (`error code: 10048`, the account over
// the free tier's 1,000-distinct-keys-per-day budget) while `/api/health` answered `ok` to four of ten
// consecutive requests. The counters were per-isolate module state, so an isolate that had not attempted
// a write yet answered `attempts: 0` → `ok`. A monitor sampling once had a 40% chance of being told
// everything was fine, and the reason string (`kv writes failing: 12/12`) named no cause at all — the
// same words would have described a deleted namespace.
//
// These tests pin the two fixes from the outside:
//
//   * the last outcome is persisted in D1, so every isolate tells the same story, and a stale failure
//     does not haunt the endpoint forever;
//   * the reason names the *kind* (quota / binding / throttle), because those want three different
//     responses and used to read identically.
//
// Run: node --test workers/kv-health-global.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, { healthStatus, kvErrorKind } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('kv-health');
const LESSONS = [
  { id: 'pip-timeout-mirror', title: 'pip install timeout', domain: 'python', tags: ['pip'],
    path: 'lessons/core/pip-timeout-mirror.md', summary: 'pip install times out' },
];

/** Minimal D1 stand-in implementing the one-row health table. */
function createHealthD1({ fail = false } = {}) {
  const rows = new Map();
  return {
    rows,
    prepare(sql) {
      const stmt = {
        _bound: [],
        bind(...args) { stmt._bound = args; return stmt; },
        async all() {
          if (fail) throw new Error('D1_ERROR: no such table');
          if (/SELECT last_error/i.test(sql)) {
            const row = rows.get('health');
            return { results: row ? [row] : [] };
          }
          return { results: [] };
        },
        async run() {
          if (fail) throw new Error('D1_ERROR: no such table');
          if (/INSERT INTO kv_write_health/i.test(sql) && /last_error/i.test(sql)) {
            const [error, at] = stmt._bound;
            rows.set('health', { ...(rows.get('health') || {}), last_error: error, last_error_at: at });
          } else if (/INSERT INTO kv_write_health/i.test(sql)) {
            const [at] = stmt._bound;
            rows.set('health', { ...(rows.get('health') || {}), last_ok_at: at });
          }
          return { success: true };
        },
      };
      return stmt;
    },
  };
}

function createEnv({ d1 = null, failWrites = true } = {}) {
  const store = new Map([['proxy:lessons', JSON.stringify({ ts: Date.now(), data: LESSONS })]]);
  const env = {
    MCP_TOKEN: TOKEN,
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) {
        if (failWrites) throw new Error('KV PUT failed: 429: your account has reached the free usage limit for this operation for today [code: 10048]');
        store.set(key, value);
      },
      async delete(key) { store.delete(key); },
    },
  };
  if (d1) env.MISAKANET_D1 = d1;
  return env;
}

const health = (env) => worker.fetch(new Request('https://misakanet.org/api/health'), env);

// ── the classifier ───────────────────────────────────────────────────────────────────────────────────

test('the three kinds of KV write failure are told apart', () => {
  assert.deepEqual(kvErrorKind('KV PUT failed: 429 [code: 10048]'), { code: '10048', kind: 'quota' });
  assert.deepEqual(kvErrorKind('KV PUT failed: [code: 10009]'), { code: '10009', kind: 'binding' });
  assert.deepEqual(kvErrorKind('KV GET failed: 404 Not Found'), { code: '404', kind: 'binding' });
  assert.deepEqual(kvErrorKind('KV PUT failed: 429 Too Many Requests'), { code: '429', kind: 'throttle' });
  assert.deepEqual(kvErrorKind('something else entirely'), { code: '', kind: 'unknown' });
});

// ── the local counters keep their old contract ───────────────────────────────────────────────────────

test('a local outage still reads the way it always did', () => {
  const health = healthStatus({ hasKV: true, attempts: 5, failures: 5 });
  assert.equal(health.status, 'degraded');
  assert.match(health.reason, /^kv writes failing: 5\/5 attempts, no successful write$/);
  assert.equal(health.kv_error_kind, 'unknown');
});

test('a stale global failure is history, not state', () => {
  const twoDaysAgo = new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString();
  assert.deepEqual(
    healthStatus({ hasKV: true, global: { error: '[code: 10048]', lastErrorAt: twoDaysAgo, lastOkAt: '' } }),
    { status: 'ok' });
});

test('a success after the failure clears it', () => {
  const failed = new Date(Date.now() - 60_000).toISOString();
  const okAfter = new Date().toISOString();
  assert.deepEqual(
    healthStatus({ hasKV: true, global: { error: '[code: 10048]', lastErrorAt: failed, lastOkAt: okAfter } }),
    { status: 'ok' });
});

test('a global failure alone is enough to degrade, even from a fresh isolate', () => {
  // This is the production symptom: local counters are empty because this isolate never wrote.
  const health = healthStatus({ hasKV: true, attempts: 0, failures: 0,
    global: { error: 'KV PUT failed [code: 10048]', lastErrorAt: new Date().toISOString(), lastOkAt: '' } });
  assert.equal(health.status, 'degraded', 'the coin flip was the whole bug');
  assert.match(health.reason, /quota 10048/);
  assert.equal(health.kv_error_kind, 'quota');
});

test('no KV binding stays a configuration, not a failure', () => {
  assert.deepEqual(healthStatus({ hasKV: false, attempts: 9, failures: 9 }), { status: 'ok' });
});

// ── end to end: a failed write is recorded, and /api/health reports it from any isolate ──────────────

test('a failed KV write is persisted, and health names the cause from a cold isolate', async () => {
  const d1 = createHealthD1();
  const env = createEnv({ d1 });
  // Force a write through the public surface: a search that misses writes a gap record.
  await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'MCP-Protocol-Version': '2025-06-18',
               Origin: 'https://misakanet.org' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query: 'zzqqxx gibberish 9911' } } }),
  }), env);

  const row = d1.rows.get('health');
  assert.ok(row && row.last_error_at, 'the failing write must leave a D1 record of itself');
  assert.match(row.last_error, /10048/, row.last_error);

  const response = await health(env);
  const body = await response.json();
  assert.equal(body.status, 'degraded');
  assert.match(body.degraded_reason, /quota 10048/, body.degraded_reason);
  assert.equal(body.kv_writes.global_error_kind, 'quota');
  assert.equal(body.kv_writes.global_backend, 'd1');
});

test('without a D1 binding the endpoint still answers, on isolate state alone', async () => {
  const env = createEnv({ d1: null });
  const response = await health(env);
  const body = await response.json();
  assert.equal(response.status, 200, 'a health probe must not 500 because a table is missing');
  assert.equal(body.kv_writes.global_backend, 'isolate');
});

test('a broken health table never breaks the endpoint', async () => {
  const env = createEnv({ d1: createHealthD1({ fail: true }) });
  const response = await health(env);
  const body = await response.json();
  assert.equal(response.status, 200, 'a health probe must not 500 because a table is missing');
  assert.equal(body.kv_writes.global_backend, 'isolate', 'the answer falls back to isolate state');
  assert.equal(body.kv_writes.global_last_failure_at, '', 'no global row means no global claim');
  // Note what this test can *not* assert: that the status is `ok`. The worker module is a singleton in
  // this process, so `kvWriteStats` carries the failures recorded by earlier tests in the file — which
  // is precisely the per-isolate behaviour the global row exists to work around. A fresh-isolate
  // assertion belongs to the pure function above (`global` with `attempts: 0`), not here.
  assert.equal(typeof body.status, 'string');
});
