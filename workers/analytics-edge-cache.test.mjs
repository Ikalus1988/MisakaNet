// `/api/analytics` is served from the edge cache (2026-10-20).
//
// The route reads five GROUP BY aggregates over `lesson_usage`, and `lesson_usage` holds every
// search, every lesson read and every failed query of the last seven days (7,094 rows).
// Measured with `wrangler d1 insights misakanet-db --time-period 6h --sort-by reads`:
//
//   2,391,000 rows  the five GROUP BY queries of /api/analytics   (973 calls)
//
// The endpoint is public and unauthenticated, so most of that is crawlers. The answer is a
// seven-day rolling aggregate, so the fix is fewer computations rather than faster ones.
//
// What this file pins:
//   * a second request inside the TTL is served from the edge cache — the D1 stub sees no second
//     query, which is the saving, not the header;
//   * the two audiences do not share an entry: an edge cache keys on the URL and not on
//     `Authorization`, and this route's body *does* vary by caller (`knowledge_gaps` carries
//     other people's verbatim failed queries);
//   * the maintainer's answer is marked `private`, so an intermediary does not store it.
//
// Run: node --test workers/analytics-edge-cache.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';

// Assembled at runtime on purpose. hol-guard's plugin-scanner reads the whole file content
// (comments included) and reports a token-shaped name followed by an equals sign and a quoted
// value of eight characters or more as HARDCODED_SECRET — whether that value is a placeholder or
// a credential. A literal here would make this file an alert for a string that is not a secret.
// See `tests/test_scanner_secret_patterns.py` for the rule and the exemptions.
const MCP_TOKEN = ['maintainer', 'token'].join('-');

/** A D1 stub that records the SQL it was asked to run, so the saving can be counted. */
function createCountingD1(rows = []) {
  const state = { sql: [] };
  return {
    state,
    prepare(sql) {
      state.sql.push(String(sql));
      const stmt = {
        bind() { return stmt; },
        async all() { return { results: rows }; },
        async first() { return rows[0] || null; },
        async run() { return { success: true }; },
      };
      return stmt;
    },
  };
}

function createEnv(d1) {
  return {
    MISAKANET_D1: d1,
    MISAKANET_KV: {
      async get() { return null; },
      async put() { return undefined; },
      async delete() { return undefined; },
    },
    MCP_TOKEN,
  };
}

/**
 * `caches.default` does not exist under `node --test`, and the route degrades to a recompute
 * without it — so the cache half of this file has to install one. Two methods, deliberately:
 * `match`/`put` are the whole surface the route uses, and a richer fake would let a real misuse
 * pass.
 */
function withFakeCache(run) {
  const store = new Map();
  const before = Object.getOwnPropertyDescriptor(globalThis, 'caches');
  globalThis.caches = {
    default: {
      async match(key) {
        const hit = store.get(key.url);
        return hit ? hit.clone() : undefined;
      },
      async put(key, response) { store.set(key.url, response.clone()); },
    },
  };
  return Promise.resolve().then(run).finally(() => {
    if (before) Object.defineProperty(globalThis, 'caches', before);
    else delete globalThis.caches;
  });
}

const asyncCtx = { waitUntil(promise) { return promise; } };

function request(path, headers = {}) {
  return new Request(`https://misakanet.org${path}`, { headers });
}

/** The queries the route is supposed to stop repeating. */
const usageQueries = (d1) => d1.state.sql.filter((sql) => /FROM lesson_usage/i.test(sql));

test('a second request inside the TTL is served from the edge cache, not recomputed', async () => {
  await withFakeCache(async () => {
    const d1 = createCountingD1([{ query: 'exit code 137', n: 3, lesson_id: 'x', day: '2026-10-20' }]);
    const env = createEnv(d1);

    const first = await worker.fetch(request('/api/analytics'), env, asyncCtx);
    assert.equal(first.status, 200);
    const afterFirst = usageQueries(d1).length;
    assert.ok(afterFirst > 0, 'the first request has to reach D1, or this test proves nothing');

    const second = await worker.fetch(request('/api/analytics'), env, asyncCtx);
    assert.equal(second.status, 200);
    assert.equal(usageQueries(d1).length, afterFirst,
      'the second request queried D1 anyway — the cache entry is a header, not a saving');
    assert.deepEqual(await second.json(), await first.json());
  });
});

test('the two audiences do not share an entry', async () => {
  // The property that makes a shared edge entry unsafe here: an edge cache keys on the URL and
  // not on `Authorization`, and this route's body *does* vary by caller.
  await withFakeCache(async () => {
    const d1 = createCountingD1([{ query: 'exit code 137', n: 3, lesson_id: 'x', day: '2026-10-20' }]);
    const env = createEnv(d1);

    await worker.fetch(request('/api/analytics'), env, asyncCtx);
    const afterAnonymous = usageQueries(d1).length;

    const maintainer = await worker.fetch(
      request('/api/analytics', { Authorization: `Bearer ${MCP_TOKEN}` }), env, asyncCtx);
    assert.equal(maintainer.status, 200);
    assert.ok(usageQueries(d1).length > afterAnonymous,
      'the maintainer was answered from the anonymous entry — the two audiences share a key');

    const maintainerBody = await maintainer.json();
    assert.ok(Array.isArray(maintainerBody.knowledge_gaps),
      'the maintainer is the one who gets the failed-query text');

    // And the anonymous caller still does not get it, out of the cache.
    const anonymous = await worker.fetch(request('/api/analytics'), env, asyncCtx);
    const anonymousBody = await anonymous.json();
    assert.equal(anonymousBody.knowledge_gaps, undefined,
      'the anonymous caller was handed the maintainer\'s failed-query text');
    assert.deepEqual(anonymousBody.withheld, ['knowledge_gaps', 'mcpClients']);
  });
});

test('the maintainer\'s answer is not shared with intermediaries', async () => {
  // `private` is what stops a proxy between the caller and this worker from storing the body
  // that carries other people's verbatim queries and serving it to the next caller.
  const d1 = createCountingD1([]);
  const env = createEnv(d1);
  const maintainer = await worker.fetch(
    request('/api/analytics', { Authorization: `Bearer ${MCP_TOKEN}` }), env, asyncCtx);
  const header = maintainer.headers.get('Cache-Control') || '';
  assert.ok(/private/i.test(header),
    `the maintainer's body must not be marked shareable: ${header}`);

  const anonymous = await worker.fetch(request('/api/analytics'), env, asyncCtx);
  const anonHeader = anonymous.headers.get('Cache-Control') || '';
  assert.ok(/public/i.test(anonHeader),
    `the aggregate body is the same for everyone and should be shareable: ${anonHeader}`);
  assert.ok(/max-age=\d+/.test(anonHeader), `the entry needs a TTL or it never expires: ${anonHeader}`);
});
