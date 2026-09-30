// Public errors must not carry internals (CodeQL js/stack-trace-exposure, #258).
//
// CodeQL flagged this worker's shared `jsonResponse` sink on 2026-09-12: exception
// messages were reaching callers. Six paths did it — five `jsonResponse({ error:
// e.message }, 5xx)` handlers (`/api/counter`, `/api/lessons`, `/api/analytics`,
// `/api/analytics/traffic`, plus a 400 body-parse) and a diagnostic I had added to the
// registration failure while chasing a KV outage.
//
// A database or parser error names tables, columns, URLs, file paths and sometimes
// credentials, and this worker answers anonymous callers. What a caller needs is that it
// failed and whether retrying helps; the detail belongs in Workers Logs.
//
// These tests assert the contract from the outside: a dependency that throws a
// recognisable internal string must not put it in any response body, while the generic
// message and a stable `code` still appear.
//
// Run: node --test workers/error-exposure.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('error-exposure');

// Everything here is something an operator would need and a caller must never see. The
// marker is neutral on purpose: a realistic provider-shaped token in this file would be
// reported by the plugin-scanner's secret patterns (see
// tests/test_scanner_secret_patterns.py) — the third time today that writing a
// credential-shaped string, even to test for its absence, was itself the problem.
const SECRET_MARKER = 'INTERNAL-SECRET-MARKER-7f3a9c';
const INTERNAL = 'D1_ERROR: no such table: lessons at prepare (/home/runner/work/x.js:42) '
  + `api_key=${SECRET_MARKER}`;

function throwingD1() {
  return {
    prepare() {
      return {
        bind() { return this; },
        async all() { throw new Error(INTERNAL); },
        async run() { throw new Error(INTERNAL); },
      };
    },
  };
}

function createEnv({ d1, kvFails = false, kv = true } = {}) {
  const store = new Map();
  return {
    MCP_TOKEN: TOKEN,
    REGISTER_TOKEN: TOKEN,
    ...(d1 ? { MISAKANET_D1: d1 } : {}),
    // `kv: false` models a deployment with no KV binding at all — the shape `/api/counter` has to
    // answer for now that its file fallback is gone (see the counter_unavailable test below).
    ...(kv ? { MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put() {
        if (kvFails) throw new Error(INTERNAL);
        return undefined;
      },
      async delete(key) { store.delete(key); },
    } } : {}),
  };
}

function assertNoInternals(text, label) {
  assert.ok(!text.includes('D1_ERROR'), `${label} echoed a database error: ${text.slice(0, 200)}`);
  assert.ok(!text.includes(SECRET_MARKER), `${label} echoed credential-looking text: ${text.slice(0, 200)}`);
  assert.ok(!text.includes('/home/runner'), `${label} echoed a path/stack frame: ${text.slice(0, 200)}`);
  assert.ok(!/at Object\.|<anonymous>/.test(text), `${label} echoed a stack: ${text.slice(0, 200)}`);
}

// Every 5xx the worker can answer with, and the code it must carry so a caller can quote something
// machine-readable instead of a sentence. An enumerated set rather than a regex: the point of this
// assertion is that a *new* 5xx shape cannot appear without someone deciding its code here.
//
// `counter_unavailable` joined the list on 2026-09-28, when `/api/counter` lost its GitHub file
// fallback: with D1 throwing and no KV binding the handler now says which stores it asked, instead of
// answering with a number from a mirror that could be months old (issue #1820). That is still a 5xx —
// a degradation scripts/site_health_check.py should see — so it belongs in this table rather than
// outside the rule.
// `/api/activity` joined the list on 2026-09-29 with the homepage's cacheable activity route: it
// reads the same counter stores through the same readers, so it can raise the same D1/parse failures,
// and a body naming a table or a file path would be one every visitor's browser caches and re-serves.
const DOCUMENTED_5XX_CODES = new Set(['internal_error', 'counter_unavailable']);

for (const path of ['/api/counter', '/api/lessons', '/api/analytics', '/api/analytics/traffic', '/api/activity']) {
  test(`${path} reports a failure without internals`, async () => {
    const response = await worker.fetch(new Request(`https://misakanet.org${path}`), createEnv({ d1: throwingD1() }));
    const body = await response.text();
    assertNoInternals(body, path);
    if (response.status >= 500) {
      const parsed = JSON.parse(body);
      assert.ok(parsed.error, `${path} must still say that it failed`);
      assert.ok(DOCUMENTED_5XX_CODES.has(parsed.code),
        `${path} gave an undocumented code (${parsed.code}) — add it to DOCUMENTED_5XX_CODES with a reason`);
    }
  });
}

test('/api/counter says which stores it asked when they are both down', async () => {
  // The specific shape behind `counter_unavailable`: no D1 binding, no KV binding, and — since the
  // 2026-09-28 change — no outbound request either. `workers/register-storage-d1.test.mjs` asserts the
  // no-network half; this one pins the body a caller actually reads.
  const env = createEnv({ d1: null, kv: false });
  const response = await worker.fetch(new Request('https://misakanet.org/api/counter'), env);
  assert.equal(response.status, 503);
  const body = await response.json();
  assert.equal(body.code, 'counter_unavailable');
  assert.equal(body.current, null, 'never a number it could not verify');
  assert.match(String(body.hint || ''), /D1 service nor the KV fallback|no file fallback/);
  assertNoInternals(JSON.stringify(body), '/api/counter (unavailable)');
});

test('registration does not echo the storage error', async () => {
  const env = createEnv({ kvFails: true });
  const response = await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18', 'Origin': 'https://misakanet.org',
      'CF-Connecting-IP': '198.51.100.42',
    },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_register', arguments: { agent_type: 'exposure-test' } } }),
  }), env);
  const body = await response.text();
  assertNoInternals(body, 'register');
  const payload = JSON.parse(JSON.parse(body).result.content[0].text);
  assert.equal(payload.code, 'storage_unavailable');
  assert.equal(payload.storage_error, undefined,
    'the storage message was moved to the logs; it must not come back as a field');
});

test('health reports counters without the message', async () => {
  const env = createEnv({ kvFails: true });
  // Provoke one failing write so the counters are non-zero.
  await worker.fetch(new Request('https://misakanet.org/api/helpful', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lesson_id: 'x' }),
  }), env);
  const response = await worker.fetch(new Request('https://misakanet.org/api/health'), env);
  const body = await response.text();
  assertNoInternals(body, '/api/health');
  const parsed = JSON.parse(body);
  assert.ok(parsed.kv_writes, 'health must still report KV write health');
  assert.equal(parsed.kv_writes.last_error, undefined);
});

test('a malformed body is a 400 without a parser message', async () => {
  const response = await worker.fetch(new Request('https://misakanet.org/api/search-index', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Sync-Token': 'x' },
    body: '{not json',
  }), createEnv());
  const body = await response.text();
  assertNoInternals(body, '/api/search-index');
});

test('/connect does not echo an upstream body or exception', async () => {
  // The upstream (GitHub) message can name the credential or the account — "Bad
  // credentials" and scope lists are exactly the kind of detail a caller must not get.
  const env = createEnv();
  const response = await worker.fetch(new Request('https://misakanet.org/connect?code=abc&state=xyz'), env);
  const body = await response.text();
  assertNoInternals(body, '/connect');
  assert.doesNotMatch(body, /Bad credentials|scope|Bearer /);
});

test('the PR Genius endpoint does not echo an exception', async () => {
  const env = createEnv();
  const response = await worker.fetch(new Request('https://misakanet.org/api/pr-genius-stats'), env);
  const body = await response.text();
  assertNoInternals(body, '/api/pr-genius-stats');
});
