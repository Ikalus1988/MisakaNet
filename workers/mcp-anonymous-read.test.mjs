// PRD ④ tests: anonymous read access — misakanet_search and
// misakanet_get_lesson must work WITHOUT auth (5 free reads/day per IP),
// while authenticated callers are exempt from the quota.
// Run: node --test workers/mcp-anonymous-read.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';

const TOKEN = 'anon-test-token';

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
  assert.match(text, /REGISTER_TOKEN|not found|GitHub API/);
});

test('anonymous reads share a 5/day/IP quota across search and get_lesson', async () => {
  const env = withLessons(createEnv());
  const today = new Date().toISOString().slice(0, 10);
  const ip = '203.0.113.99';
  // Pre-fill quota at 5/5 for this IP.
  env.MISAKANET_KV._store.set(`rate:read:${ip}:${today}`, '5');

  const resp = await mcpCall('misakanet_search', { query: 'pip timeout' }, {}, env);
  assert.equal(resp.status, 200);
  const result = await resultText(resp);
  assert.match(result.error, /Rate limit: 5 free searches per day exceeded/);
  assert.match(result.hint, /misakanet_register/);
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
