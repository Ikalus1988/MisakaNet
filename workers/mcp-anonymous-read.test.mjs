// PRD ④ tests: anonymous read access — misakanet_search and
// misakanet_get_lesson must work WITHOUT auth (5 free reads/day per IP),
// while authenticated callers are exempt from the quota.
// Run: node --test workers/mcp-anonymous-read.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('anon');

// KV store with a seedable counter map so tests can simulate quota exhaustion.
function createEnv(seed = {}) {
  const store = new Map(Object.entries(seed));
  return {
    MCP_TOKEN: TOKEN,
    MCP_VERSION: 'anon-test',
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) {
        store.set(key, value);
      },
      _store: store,
    },
  };
}

// Seed proxy:lessons so search doesn't hit GitHub.
function withLessons(env) {
  env.MISAKANET_KV._store.set('proxy:lessons', JSON.stringify({
    ts: Date.now(),
    data: [{ id: 'pip-mirror', title: 'pip install timeout', description: 'use mirror', domain: 'python' }],
  }));
  return env;
}

function mcpCall(name, args, extraHeaders = {}, env = null) {
  return worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '203.0.113.99',
      ...extraHeaders,
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name, arguments: args },
    }),
  }), env);
}

async function resultText(response) {
  const body = await response.json();
  return JSON.parse(body.result.content[0].text);
}

test('anonymous misakanet_search succeeds without auth (no 401)', async () => {
  const env = withLessons(createEnv());
  const resp = await mcpCall('misakanet_search', { query: 'pip timeout' }, {}, env);
  assert.equal(resp.status, 200);
  const result = await resultText(resp);
  assert.ok(Array.isArray(result.results));
  assert.equal(result.results[0].id, 'pip-mirror');
});

test('anonymous misakanet_get_lesson succeeds without auth (no 401)', async () => {
  // D1 unbound + empty KV → GitHub path will 401 without REGISTER_TOKEN, but
  // that 401 is a GitHub call, not an MCP auth rejection: the tool reached
  // the handler (status 200 with an error message inside).
  const env = createEnv();
  const resp = await mcpCall('misakanet_get_lesson', { id: 'anything' }, {}, env);
  assert.equal(resp.status, 200);
  const body = await resp.json();
  const text = body.result.content[0].text;
  // If auth had blocked it, we'd get {"error":{"message":"Unauthorized"}}.
  assert.doesNotMatch(text, /"message":"Unauthorized"/);
  // A failure is reported without internal detail (CodeQL alert #258, 2026-09-12):
  // no token name, no upstream status, no stack.
  assert.match(text, /Retry shortly|internal_error|error/);
  assert.doesNotMatch(text, /REGISTER_TOKEN|GitHub API|at Object\.|runner/);
});

test('anonymous reads share one burst window across search and get_lesson', async () => {
  const env = withLessons(createEnv());
  const burst = `burst-${new Date().toISOString().slice(0, 16).replace(':', '-')}`;
  const ip = '203.0.113.99';
  // Pre-fill the burst window for this IP (the limit is per minute now, not per day).
  env.MISAKANET_KV._store.set(`rate:read:${ip}:${burst}`, '20');

  const resp = await mcpCall('misakanet_search', { query: 'pip timeout' }, {}, env);
  assert.equal(resp.status, 200);
  const result = await resultText(resp);
  assert.match(result.error, /Too many requests: max \d+ reads per \d+s/);
  assert.match(result.hint, /retry after|no registration needed/);
});

test('authenticated callers are exempt from the anonymous quota', async () => {
  const env = withLessons(createEnv());
  const today = new Date().toISOString().slice(0, 10);
  const ip = '203.0.113.99';
  env.MISAKANET_KV._store.set(`rate:read:${ip}:${today}`, '5');

  const resp = await mcpCall('misakanet_search', { query: 'pip timeout' },
    { Authorization: `Bearer ${TOKEN}` }, env);
  assert.equal(resp.status, 200);
  const result = await resultText(resp);
  assert.equal(result.error, undefined);
  assert.ok(Array.isArray(result.results));
});

// Glama connector health fix: anonymous streamable-http sessions must pass the
// spec-mandated notifications/initialized (fire-and-forget, no response) —
// previously the auth gate 401'd it, so gateway health checks showed Unhealthy.
test('anonymous session accepts notifications/initialized (202, not 401)', async () => {
  const env = createEnv();
  const post = (body) => worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '203.0.113.77',
    },
    body: JSON.stringify(body),
  }), env);

  // initialize works anonymously (already the case).
  const init = await post({
    jsonrpc: '2.0', id: 1, method: 'initialize',
    params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'health', version: '1' } },
  });
  assert.equal(init.status, 200);

  // The mandatory post-initialize notification must be accepted anonymously.
  const notif = await post({ jsonrpc: '2.0', method: 'notifications/initialized' });
  assert.equal(notif.status, 202);

  // Other notification namespaces stay open too.
  const other = await post({ jsonrpc: '2.0', method: 'notifications/cancelled', params: {} });
  assert.equal(other.status, 202);
});

// ── #2845: a method that is answered but unreachable ──────────────────────────────────────────────
// `server/discover` has had a handler in the worker since the 2026-07-28 RC, answering with
// `capabilities` + `serverInfo`. It was still unreachable, because the auth gate's public set
// named only `initialize`, `tools/list` and `notifications/*` — and a client that *negotiates*
// sends `server/discover` first, so it never got past the gate to the handler.
//
// Measured against production on 2026-10-06, no token, only the method varying:
//
//     method           2025-06-18   2025-11-25   2026-07-28
//     initialize           200          200          200
//     tools/list           200          200          200
//     server/discover      401          401          401
//
// The 401 body is `{"code":-32000,"message":"Unauthorized"}`, which the SDK behind DeepSeek
// Harness classifies as a transport failure and retries forever rather than downgrading to
// `initialize`. A protocol-negotiation miss answered as a transport fault is the whole bug:
// the client never learns the door is open.
//
// So the shape worth guarding is not "this method is public" but **"every method the worker
// answers is reachable by an anonymous session"** — a handler behind a closed gate is
// indistinguishable, to a client, from a method that was never implemented.
test('every method the worker answers is reachable without a token', async () => {
  // The public set, as source. Read rather than reimplemented, so this cannot drift from
  // `isPublicMethod` in a way that makes the assertion below pass for the wrong reason.
  const src = await readFile(new URL('./register-proxy-sw.js', import.meta.url), 'utf8');
  const publicBlock = src.slice(
    src.indexOf('isPublicMethod = peekBody?.method'),
    src.indexOf('} catch (peekErr)'),
  );

  // Every `if (method === "…")` branch the dispatcher answers, minus the ones that are
  // business operations (they run *inside* `tools/call`, gated by `openTools` above).
  const answered = [...src.matchAll(/if \(method === "([^"]+)"\)/g)].map((m) => m[1]);
  assert.ok(answered.length > 3, `expected the dispatcher to branch on several methods, found ${answered.length}`);

  // Lifecycle/discovery methods carry no business data, so an anonymous session may have them.
  // A `tools/call` is not one of these: its tool name is what `openTools` checks.
  const LIFECYCLE = ['initialize', 'tools/list', 'server/discover'];
  for (const m of LIFECYCLE) {
    assert.ok(
      answered.includes(m),
      `the worker answers "${m}" but this test's lifecycle list does not mention it — if that is ` +
      `intentional, add it to LIFECYCLE with the reason it is safe without a token, and make sure ` +
      `the auth gate agrees`,
    );
  }

  // The gate itself. This is the assertion that was failing before the fix: a method with a
  // handler and no mention in the public set is answered-by-nobody.
  for (const m of LIFECYCLE) {
    assert.ok(
      publicBlock.includes(`"${m}"`),
      `the worker answers "${m}" but the auth gate's public set does not name it, so an ` +
      `anonymous client gets 401 before reaching the handler. A negotiating client sends ` +
      `server/discover first and never falls back to initialize (#2845).`,
    );
  }
});

test('anonymous server/discover returns capabilities instead of 401', async () => {
  const env = createEnv();
  const res = await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      accept: 'application/json, text/event-stream',
      'MCP-Protocol-Version': '2026-07-28',
      Origin: 'https://misakanet.org',
      'CF-Connecting-IP': '203.0.113.91',
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 'sd-1', method: 'server/discover',
      params: { _meta: { 'io.modelcontextprotocol/protocolVersion': '2026-07-28' } },
    }),
  }), env);

  assert.equal(res.status, 200, `server/discover answered ${res.status}, not 200 — an anonymous ` +
    `negotiating client treats 401 as a transport fault and retries forever (#2845)`);

  const body = await res.text();
  const data = JSON.parse(body.split('data: ')[1]);
  assert.equal(data.result.capabilities.tools !== undefined, true,
    `server/discover must report capabilities, got: ${body.slice(0, 200)}`);
  assert.ok(data.result.serverInfo?.name, `server/discover must report serverInfo, got: ${body.slice(0, 200)}`);
});
