// A failing KV write must degrade, not kill the endpoint (2026-09-12).
//
// Found by an adversarial review of that day's changes, and confirmed live: every
// KV *write* in production started failing — `misakanet_register`, `/mcp/connect`,
// `/api/search-signal`, `/api/helpful` all answered CF `error code: 1101` / HTTP 500.
// The cause was environmental, but the *reason it took the endpoints down* was ours:
// 28 of 33 writes were bare `await env.MISAKANET_KV.put(...)`, so the exception
// escaped `worker.fetch`. Two consequences mattered:
//
//   * an agent whose IP had used its 5 free reads was told to register, and
//     registration 500'd — the documented escape hatch was gone exactly when needed;
//   * anonymous search died on its own rate-limit counter, so a fresh IP could not
//     search either.
//
// These tests pin the degradation contract: storage trouble may cost us counters and
// caching, it may not cost us the search path, and it may never hand out a token
// that was not stored.
//
// Run: node --test workers/kv-write-failure.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, { refreshSearchIndex, BM25_INDEX_KEY } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

// Synthetic token for the fixtures below (workers/_test-token.mjs explains why these
// are never written as literals: the plugin-scanner flags that shape).
const TOKEN = testToken('kv-failure');

const LESSONS = [
  { id: 'pip-timeout-mirror', title: 'pip install timeout', domain: 'python', tags: ['pip'],
    path: 'lessons/core/pip-timeout-mirror.md', summary: 'pip install times out on slow networks',
    preview: 'Set index-url to a mirror and raise the timeout behind a corporate proxy.' },
];

function createEnv({ failWrites = true, seed = {} } = {}) {
  const store = new Map(Object.entries(seed));
  return {
    MCP_TOKEN: TOKEN,
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put() {
        if (failWrites) {
          // Shaped like the real failure: Cloudflare KV refuses the write and the
          // rejection surfaces as an uncaught exception unless it is guarded.
          throw new Error('KV PUT failed: 429 Too Many Requests');
        }
        return undefined;
      },
      async delete(key) { store.delete(key); },
    },
    _store: store,
  };
}

function mcpCall(name, args = {}) {
  return new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'Origin': 'https://misakanet.org',
      'CF-Connecting-IP': '203.0.113.' + (Math.floor(Math.random() * 200) + 1),
    },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name, arguments: args } }),
  });
}

async function toolResult(env, name, args) {
  const response = await worker.fetch(mcpCall(name, args), env);
  assert.equal(response.status, 200, `HTTP ${response.status} instead of a tool result`);
  const body = await response.json();
  return JSON.parse(body.result.content[0].text);
}

test('a failing KV write does not take search down for an anonymous caller', async () => {
  // `proxy:lessons` is seeded so no network is involved: the only thing that can
  // throw here is the rate-limit counter write.
  const env = createEnv({
    seed: { 'proxy:lessons': JSON.stringify({ ts: Date.now(), data: LESSONS }) },
  });
  const result = await toolResult(env, 'misakanet_search', { query: 'pip install timeout', top: 3 });
  assert.equal(result.error, undefined, `search failed instead of degrading: ${JSON.stringify(result)}`);
  assert.ok(Array.isArray(result.results), JSON.stringify(result));
});

test('register refuses to hand out a token it could not store', async () => {
  const env = createEnv();
  const result = await toolResult(env, 'misakanet_register', { agent_type: 'kv-failure-test' });
  assert.equal(result.token, undefined,
    'a token that was never persisted would fail on the next authenticated call with no explanation');
  assert.match(String(result.error || ''), /storage|temporarily/i, JSON.stringify(result));
  assert.match(String(result.hint || ''), /anonymous|search/i,
    'the caller needs to be told what still works');
});

test('register still works when storage is healthy', async () => {
  const env = createEnv({ failWrites: false });
  const result = await toolResult(env, 'misakanet_register', { agent_type: 'kv-ok-test' });
  assert.ok(String(result.token || '').startsWith('mcp_'), JSON.stringify(result));
  assert.ok(result.node_id, JSON.stringify(result));
});

test('health reports KV write failures instead of answering a bare ok', async () => {
  const env = createEnv();
  await toolResult(env, 'misakanet_search', { query: 'anything' });
  const response = await worker.fetch(new Request('https://misakanet.org/api/health'), env);
  const body = await response.json();
  assert.equal(body.status, 'ok');
  assert.ok(body.kv_writes.failures >= 1,
    `health must surface the failing writes it just observed: ${JSON.stringify(body.kv_writes)}`);
  assert.ok(body.kv_writes.last_failure_at, 'and when they started failing');
  // ...but not the storage layer own message: /api/health is anonymous. The detail goes
  // to Workers Logs; a diagnostic I had put in the response is what CodeQL flagged.
  assert.equal(body.kv_writes.last_error, undefined,
    'an anonymous endpoint must not echo internal error text');
  assert.doesNotMatch(JSON.stringify(body), /429|KV PUT failed/);
});

test('search-index reports a stale index rather than serving it as fresh', async () => {
  const env = createEnv({ failWrites: false });
  // A rebuild that cannot be written leaves the previous index in place. `builtAt`
  // is then the only evidence, and it must be reported.
  const staleIndex = { version: 1, built_at: new Date(Date.now() - 30 * 3600 * 1000).toISOString(),
                       docCount: LESSONS.length, avgDocLen: 5, k1: 1.5, b: 0.75,
                       textMode: 'rich', terms: {}, docs: [] };
  env._store.set(BM25_INDEX_KEY, JSON.stringify(staleIndex));
  const response = await worker.fetch(new Request('https://misakanet.org/api/search-index'), env);
  const body = await response.json();
  assert.equal(body.available, true);
  assert.equal(body.stale, true, `a 30h-old index must be reported as stale: ${JSON.stringify(body)}`);
});

test('an un-writable index is reported by the refresh, not swallowed', async () => {
  const env = createEnv({
    seed: { 'proxy:lessons': JSON.stringify({ ts: Date.now(), data: LESSONS }) },
  });
  const result = await refreshSearchIndex(env);
  assert.equal(env._store.has(BM25_INDEX_KEY), false, 'the write really did fail');
  assert.equal(result.refreshed, false,
    `a build that could not be stored must not be reported as refreshed: ${JSON.stringify(result)}`);
  assert.match(String(result.reason), /kv write/i, JSON.stringify(result));
});
