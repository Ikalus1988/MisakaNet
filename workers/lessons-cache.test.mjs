// `/api/lessons` is cacheable at the edge — and cacheable *safely*, which is the part that decides
// its shape (2026-10-02).
//
// The budget this protects is D1's, not Workers'. Workers Free allows 100,000 requests/day; D1 Free
// allows **5 million rows read/day**, and a search costs rows read, not requests. Divided out, the
// two budgets meet at **50 rows per request**: a request that reads more than that exhausts D1
// before it exhausts requests — and D1's limit errors *inside* the Worker, where a route's fail
// mode cannot help. `?q=` runs an FTS5 MATCH and, when it finds nothing, a second relaxed `OR`, so
// it is the most expensive read on the endpoint and the one worth not repeating per caller.
//
// What this file pins:
//   * the answer carries a minutes-scale TTL and is no longer `no-store` (the API's default);
//   * a second identical request inside the TTL is served from the cache — the D1 stub sees no
//     second query, which is the saving, not the header;
//   * the response is identical with and without an `Authorization` header, the property that makes
//     a shared TTL safe on a worker whose other API routes are `no-store` precisely because their
//     bodies vary by caller;
//   * a refusal is not cached, so a transient D1 problem cannot be pinned for the TTL.
//
// Run: node --test workers/lessons-cache.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, { LESSONS_CACHE_CONTROL, LESSONS_TTL_SECONDS } from './register-proxy-sw.js';

const ROWS = [
  { id: 'pip-install-proxy-timeout', title: 'pip install ReadTimeoutError behind a corporate proxy',
    domain: 'python', status: 'published', tags: '["pip","proxy"]',
    path: 'lessons/python/pip-install-proxy-timeout.md', summary: 'Set the index and the trusted host.',
    updated: '2026-01-02', created: '2026-01-01', rank: 1 },
];

/**
 * A D1 stub that counts the queries it was asked to run. The count is the assertion: a cache hit
 * that still queried D1 would satisfy a header check and save nothing.
 */
function createCountingD1(rows = ROWS) {
  const state = { queries: 0 };
  return {
    state,
    prepare() {
      const stmt = {
        bind() { return stmt; },
        async all() { state.queries += 1; return { results: rows }; },
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
  };
}

function request(path, headers = {}) {
  return new Request(`https://misakanet.org${path}`, { headers });
}

/**
 * `caches.default` does not exist under `node --test`, and the route degrades to a recompute without
 * it — so the cache half of this file has to install one. Two methods, deliberately: `match`/`put`
 * are the whole surface the route uses, and a richer fake would let a real misuse pass.
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

// ── the TTL ──────────────────────────────────────────────────────────────────────────────────────

test('the answer carries a minutes-scale TTL instead of the API default no-store', async () => {
  const response = await worker.fetch(request('/api/lessons?q=proxy'), createEnv(createCountingD1()), asyncCtx);
  assert.equal(response.status, 200);
  const header = response.headers.get('Cache-Control') || '';
  assert.equal(header, LESSONS_CACHE_CONTROL, header);
  assert.ok(!/no-store/i.test(header), `a shared TTL and no-store cannot both be the point: ${header}`);
  const maxAge = Number((/max-age=(\d+)/.exec(header) || [])[1]);
  assert.ok(Number.isFinite(maxAge), header);
  assert.ok(maxAge >= 30 && maxAge <= 300,
    `this number is how long a merged lesson can stay invisible; ${maxAge}s is not "minutes"`);
  assert.equal(maxAge, LESSONS_TTL_SECONDS, 'the header drifted from the constant the test asserts');
});

test('the list form is cacheable too — it reads D1 as well', async () => {
  const response = await worker.fetch(request('/api/lessons?limit=5'), createEnv(createCountingD1()), asyncCtx);
  assert.equal(response.headers.get('Cache-Control'), LESSONS_CACHE_CONTROL);
});

// ── the saving ───────────────────────────────────────────────────────────────────────────────────

test('a second request inside the TTL is served from the edge cache, not recomputed', async () => {
  await withFakeCache(async () => {
    const d1 = createCountingD1();
    const env = createEnv(d1);
    const first = await worker.fetch(request('/api/lessons?q=proxy'), env, asyncCtx);
    assert.equal(first.status, 200);
    const afterFirst = d1.state.queries;
    assert.ok(afterFirst > 0, 'the first request has to reach D1, or this test proves nothing');

    const second = await worker.fetch(request('/api/lessons?q=proxy'), env, asyncCtx);
    assert.equal(second.status, 200);
    assert.equal(d1.state.queries, afterFirst,
      'the second request queried D1 anyway — the TTL is a header, not a saving');
    assert.deepEqual(await second.json(), await first.json());
  });
});

test('different queries do not share an entry', async () => {
  await withFakeCache(async () => {
    const d1 = createCountingD1();
    const env = createEnv(d1);
    await worker.fetch(request('/api/lessons?q=proxy'), env, asyncCtx);
    const afterFirst = d1.state.queries;
    await worker.fetch(request('/api/lessons?q=totally-different'), env, asyncCtx);
    assert.ok(d1.state.queries > afterFirst,
      'a different ?q= was answered from another query\'s cache entry — the key is not the URL');
  });
});

// ── the property that makes a shared TTL safe ────────────────────────────────────────────────────

test('the body does not vary with the caller, so a shared entry leaks nothing', async () => {
  const anonymous = await worker.fetch(request('/api/lessons?q=proxy'), createEnv(createCountingD1()), asyncCtx);
  const maintainer = await worker.fetch(
    request('/api/lessons?q=proxy', { Authorization: 'Bearer maintainer-token' }),
    createEnv(createCountingD1()), asyncCtx);
  assert.deepEqual(await maintainer.json(), await anonymous.json(),
    'the body differs by caller — then it must not carry a shared TTL, whatever the route does now');
  assert.equal(maintainer.headers.get('Cache-Control'), LESSONS_CACHE_CONTROL);
});

// ── what must not be cached ──────────────────────────────────────────────────────────────────────

test('a refusal is not cached, so a transient D1 problem is not pinned for the TTL', async () => {
  await withFakeCache(async () => {
    // Filtered queries need D1; without the binding the route refuses rather than silently returning
    // the whole list.
    const env = { MISAKANET_KV: { async get() { return null; }, async put() { return undefined; }, async delete() { return undefined; } } };
    const response = await worker.fetch(request('/api/lessons?domain=python'), env, asyncCtx);
    const header = response.headers.get('Cache-Control') || '';
    assert.ok(/no-store/.test(header),
      `a refusal answered with a shared TTL would outlive the condition it reports: ${header}`);
    // And nothing was written, so a later request with D1 bound is not answered from it.
    const d1 = createCountingD1();
    const second = await worker.fetch(request('/api/lessons?domain=python'), createEnv(d1), asyncCtx);
    assert.equal(second.status, 200);
    assert.ok(d1.state.queries > 0, 'the refusal was served from the cache after the condition changed');
  });
});
