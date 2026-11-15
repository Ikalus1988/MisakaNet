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
import worker, { refreshSearchIndex, BM25_INDEX_KEY, storeGet, readStoredIndex
} from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';
import { withKvStore } from './_test-kv-store.mjs';

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

// Does this body echo the storage layer's own message, or the upstream status?
//
// The rule is about the *values the endpoint chose to include*, not about the bytes of the serialized
// body. The first version asserted `doesNotMatch(JSON.stringify(body), /429|KV PUT failed/)`, which
// also matches the milliseconds of an ISO timestamp: `/api/health` answered correctly with
// `…T13:52:03.429Z` and the assertion failed on the clock (measured 2026-11-15, audit run 43720010324
// for PR #5038). Three timestamp fields per body made that a ~1-in-330 chance per run, on every PR.
const ISO_TIMESTAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/;

function storageDetailLeaked(body) {
  const found = [];
  (function visit(node) {
    if (Array.isArray(node) || (node && typeof node === 'object')) {
      for (const value of Object.values(node)) visit(value);
      return;
    }
    if (typeof node === 'number') {
      if (node === 429) found.push('429');
      return;
    }
    if (typeof node !== 'string') return;
    if (ISO_TIMESTAMP.test(node)) return; // a clock reading is not a leak
    if (/429/.test(node) || node.includes('KV PUT failed')) found.push(node);
  })(body);
  return found;
}

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
  assert.deepEqual(storageDetailLeaked(body), [],
    'an anonymous endpoint must not echo the storage layer message or the upstream status');
});

test('the leak check does not read a timestamp millisecond as a 429', () => {
  // The body that actually went red: every value is clean, and `.429` is a clock reading.
  const clean = {
    status: 'ok',
    kv_writes: {
      attempts: 9, failures: 5,
      last_failure_at: '2026-11-15T13:52:03.358Z', last_ok_at: '2026-11-15T13:52:03.356Z',
    },
    timestamp: '2026-11-15T13:52:03.429Z',
  };
  assert.deepEqual(storageDetailLeaked(clean), [], 'a correct health body must not fail this');
  // …and what the rule exists for is still caught, in a message and as a bare number.
  assert.deepEqual(storageDetailLeaked({ last_error: 'KV PUT failed: 429 Too Many Requests' }),
    ['KV PUT failed: 429 Too Many Requests']);
  assert.deepEqual(storageDetailLeaked({ upstream: 429 }), ['429']);
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
  // The reason is no longer KV-specific: the index goes through `storePut`, which tries D1 first and
  // only then KV (#2116), so "the build could not be stored" is the condition — and that is what the
  // assertion is about. The one above it is the part that matters: a build nobody stored must never
  // be reported as refreshed.
  assert.match(String(result.reason), /storage write/i, JSON.stringify(result));
});

// The point of #2116, as a test: a spent KV budget is no longer enough to freeze the index.
//
// This is the state production was in on 2026-09-23 — `/api/health` said `kv writes failing (quota
// 10048)`, the rebuild ran, the write was refused, and search kept serving a previous build whose
// lessons had no `evidence_level`. With the index in the durable store the same outage costs nothing.
test('with D1 bound, a KV write outage no longer freezes the index (#2116)', async () => {
  const env = createEnv({ failWrites: true,
    seed: { 'proxy:lessons': JSON.stringify({ ts: Date.now(), data: LESSONS }) } });
  // The corpus comes from D1 too once it is bound (`loadLessonsFresh`), so the stub answers both:
  // kv_store rows through the shared helper, lesson rows through this.
  const lessonsD1 = {
    prepare() {
      const stmt = { bind() { return stmt; },
        async all() { return { results: LESSONS.map(l => ({ ...l, tags: JSON.stringify(l.tags || []) })) }; },
        async run() { return { success: true }; } };
      return stmt;
    },
  };
  env.MISAKANET_D1 = withKvStore(lessonsD1);

  const result = await refreshSearchIndex(env);
  assert.equal(result.refreshed, true,
    `the rebuild must publish while KV refuses writes: ${JSON.stringify(result)}`);

  const stored = await readStoredIndex(env);
  assert.equal(stored.docCount, LESSONS.length, 'the index is readable from where it was written');
  assert.equal(env._store.has(BM25_INDEX_KEY), false,
    'and it did not go to KV — the storage it could not use');
});
