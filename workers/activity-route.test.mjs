// The homepage activity feed: a number that says how old it is, behind a TTL that is real
// (2026-09-29).
//
// The panel read `docs/data/activity.json`, rewritten every three hours. Measured 2026-09-29 the file
// (generated_at 16:21Z) said `total 5974` while the same endpoint answered 6645 for the same day —
// ~10% low, with a ~2x case reported by a reviewer. The *date* was identical in both, so nothing on
// the page could show the staleness. That is why `/api/activity` carries `generated_at` and why the
// panel renders the age rather than only the day.
//
// The 17.4s cold path that justified the snapshot is gone: six consecutive requests that day
// answered in 1.08–1.28s. What remains worth avoiding is paying a recompute per visitor, so the
// route is cacheable — and cacheable *safely*, which is the part that decides its shape:
// `/api/analytics/traffic` serves `mcpClients` to the maintainer token only (2026-09-29), so its
// body varies by caller and an edge cache (which keys on the URL, not on `Authorization`) must never
// hold it. Hence a route of its own that cannot read the caller at all.
//
// What this file pins:
//   * the TTL is present in the response *and* honoured (a second request inside the window is
//     served from the cache rather than recomputed);
//   * the payload is the snapshot's five keys, so the panel renders one shape from two sources;
//   * the response is identical with and without the maintainer token — the property that makes a
//     shared TTL safe — and no `mcpClients` / `knowledge_gaps` can appear;
//   * both routes read the same counters, so they cannot disagree about today.
//
// Run: node --test workers/activity-route.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, {
  ACTIVITY_CACHE_CONTROL, ACTIVITY_SOURCE, ACTIVITY_TTL_SECONDS, readTrafficBreakdown,
} from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const DAY = new Date().toISOString().slice(0, 10);
const TOKEN = testToken('activity-route');

// The published shape. Pinned on the Python side too — `SNAPSHOT_KEYS` in
// `scripts/sync_site_activity.py`, asserted by `tests/test_sync_site_activity.py` — because the panel
// reads the live route and the committed file with one renderer, so a key that moves in one producer
// would break the other silently.
const SNAPSHOT_KEYS = ['generated_at', 'source', 'date', 'total', 'calls'];

/** Minimal D1 stand-in answering exactly the counters SELECT (cf. workers/traffic-aggregation.test.mjs). */
function createCountersD1(seed = {}) {
  const rows = new Map(Object.entries(seed)); // `${scope}|${bucket}|${period}` -> count
  return {
    rows,
    prepare(sql) {
      const stmt = {
        _bound: [],
        bind(...args) { stmt._bound = args; return stmt; },
        async all() {
          if (/SELECT count FROM counters/i.test(sql)) {
            const [scope, bucket, period] = stmt._bound;
            const value = rows.get(`${scope}|${bucket}|${period}`);
            return value === undefined ? { results: [] } : { results: [{ count: value }] };
          }
          return { results: [] };
        },
        async run() { return { success: true }; },
      };
      return stmt;
    },
  };
}

const SEED = {
  [`traffic|mcp|${DAY}`]: 6499,
  [`traffic|agent|${DAY}`]: 84,
  [`traffic|crawler|${DAY}`]: 18,
  [`traffic|pageview|${DAY}`]: 44,
};

function createEnv(options = {}) {
  return {
    MCP_TOKEN: TOKEN,
    ...(options.d1 === null ? {} : { MISAKANET_D1: options.d1 || createCountersD1(SEED) }),
    ...(options.kv === false ? {} : {
      MISAKANET_KV: {
        async get() { return null; },
        async put() { return undefined; },
        async delete() { return undefined; },
      },
    }),
  };
}

function request(path, headers = {}) {
  return new Request(`https://misakanet.org${path}`, { headers });
}

/**
 * `caches.default` does not exist in `node --test` (Node 22 exposes no `caches` global), and the
 * route degrades to a recompute without it — so the cache half of this file has to install one. It
 * is a two-method stub, deliberately: `match`/`put` are the entire surface the route uses, and a
 * richer fake would let a real misuse pass.
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

// ── the shape the panel renders ──────────────────────────────────────────────────────────────────

test('the route answers in the snapshot shape, so one renderer reads both sources', async () => {
  const response = await worker.fetch(request('/api/activity'), createEnv());
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.deepEqual(Object.keys(body).sort(), [...SNAPSHOT_KEYS].sort(), JSON.stringify(body));
  assert.equal(body.source, ACTIVITY_SOURCE);
  assert.equal(body.date, DAY);
  assert.equal(body.total, 6645);
  assert.deepEqual(body.calls, { mcp: 6499, agent: 84, crawler: 18, pageview: 44 });
});

test('total is the sum of its classes, and the classes are the four the page labels', async () => {
  const body = await (await worker.fetch(request('/api/activity'), createEnv())).json();
  assert.equal(body.total, Object.values(body.calls).reduce((a, b) => a + b, 0),
    'a total that disagrees with its parts is what a truncated read looks like');
  assert.deepEqual(Object.keys(body.calls).sort(), ['agent', 'crawler', 'mcp', 'pageview']);
});

test('generated_at is an ISO-8601 instant the panel can compute an age from', async () => {
  const before = Date.now();
  const body = await (await worker.fetch(request('/api/activity'), createEnv())).json();
  const at = Date.parse(body.generated_at);
  assert.ok(Number.isFinite(at), `generated_at is not parseable: ${body.generated_at}`);
  assert.ok(at >= before - 60000 && at <= Date.now() + 1000, body.generated_at);
  // No milliseconds, so it is byte-comparable with `sync_site_activity.py`'s `generated_at`.
  assert.match(body.generated_at, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
});

// ── the TTL ──────────────────────────────────────────────────────────────────────────────────────

test('the response carries a minutes-scale TTL and is not no-store', async () => {
  const response = await worker.fetch(request('/api/activity'), createEnv());
  const header = response.headers.get('Cache-Control') || '';
  assert.equal(header, ACTIVITY_CACHE_CONTROL, header);
  assert.ok(!/no-store/i.test(header), `a shared TTL and no-store cannot both be the point: ${header}`);
  const maxAge = Number((/max-age=(\d+)/.exec(header) || [])[1]);
  assert.ok(Number.isFinite(maxAge), header);
  assert.ok(maxAge >= 60 && maxAge <= 900,
    `the homepage staleness is this number; ${maxAge}s is no longer "minutes"`);
  assert.equal(maxAge, ACTIVITY_TTL_SECONDS, 'the header drifted from the constant the panel assumes');
});

test('a second request inside the TTL is served from the edge cache, not recomputed', async () => {
  await withFakeCache(async () => {
    const env = createEnv();
    const first = await worker.fetch(request('/api/activity'), env);
    const firstBody = await first.json();

    // Move the counters underneath. A recompute would answer 9999; a cache hit answers the old total.
    env.MISAKANET_D1.rows.set(`traffic|mcp|${DAY}`, 9999);
    const second = await worker.fetch(request('/api/activity'), env);
    const secondBody = await second.json();

    assert.equal(secondBody.total, firstBody.total, 'the cached body was not reused');
    assert.equal(secondBody.generated_at, firstBody.generated_at);
    assert.equal(second.headers.get('Cache-Control'), ACTIVITY_CACHE_CONTROL,
      'the cached copy lost the TTL it was stored with');
  });
});

test('a cache-busting query string cannot bypass the TTL', async () => {
  await withFakeCache(async () => {
    const env = createEnv();
    const first = await worker.fetch(request('/api/activity'), env);
    const firstBody = await first.json();
    env.MISAKANET_D1.rows.set(`traffic|mcp|${DAY}`, 9999);
    // The panel sends no query, but a proxy or a curious caller could: if the query were part of the
    // cache key, `?cb=<random>` would be a way to force the recompute this route exists to avoid.
    const second = await worker.fetch(request(`/api/activity?cb=${Math.random()}`), env);
    assert.equal((await second.json()).total, firstBody.total, 'the query string changed the cache key');
  });
});

test('with no cache available the route still answers (a missing cache is not an error)', async () => {
  // The other half of the guard: `caches` is absent here by construction, and a route that threw
  // without it would take the panel down in any runtime that does not provide one.
  assert.equal(typeof globalThis.caches, 'undefined');
  const response = await worker.fetch(request('/api/activity'), createEnv());
  assert.equal(response.status, 200);
  assert.equal((await response.json()).total, 6645);
});

// ── what must not be published ───────────────────────────────────────────────────────────────────

test('it is anonymous-only: the maintainer token changes nothing', async () => {
  // The property that makes a *shared* TTL safe. If this ever fails, a cached response could carry
  // one caller's payload to the next visitor — which is why `/api/analytics/traffic` is not cached.
  const anonymous = await (await worker.fetch(request('/api/activity'), createEnv())).json();
  const maintainer = await (await worker.fetch(
    request('/api/activity', { Authorization: `Bearer ${TOKEN}` }), createEnv())).json();
  assert.deepEqual(Object.keys(maintainer).sort(), Object.keys(anonymous).sort(),
    `the body varies by caller: ${JSON.stringify(maintainer)}`);
  assert.equal(maintainer.total, anonymous.total);
});

test('a wrong token is not a way in either', async () => {
  const body = await (await worker.fetch(
    request('/api/activity', { Authorization: 'Bearer not-the-token' }), createEnv())).json();
  assert.deepEqual(Object.keys(body).sort(), [...SNAPSHOT_KEYS].sort(), JSON.stringify(body));
});

test('no per-client counts and no failed-query text are published', async () => {
  // 2026-09-29: `mcpClients` is third-party tooling and `knowledge_gaps` is verbatim failed queries.
  // Neither may be reachable from a route that anyone can cache and read.
  const text = await (await worker.fetch(request('/api/activity'), createEnv())).text();
  for (const field of ['mcpClients', 'knowledge_gaps', 'top_searches', 'withheld']) {
    assert.ok(!text.includes(field), `/api/activity published ${field}: ${text}`);
  }
});

// ── one computation, two routes ──────────────────────────────────────────────────────────────────

test('both routes read the same counters and cannot disagree about today', async () => {
  const env = createEnv();
  const activity = await (await worker.fetch(request('/api/activity'), env)).json();
  const traffic = await (await worker.fetch(request('/api/analytics/traffic'), env)).json();
  assert.deepEqual(activity.calls, traffic.breakdown);
  assert.equal(activity.total, traffic.total);
  assert.equal(activity.date, traffic.date);
});

test('the traffic endpoint keeps its per-client field — this change did not remove it', async () => {
  const traffic = await (await worker.fetch(request('/api/analytics/traffic'), createEnv())).json();
  assert.ok('mcpClients' in traffic, JSON.stringify(traffic));
  assert.deepEqual(traffic.mcpClients, {}, 'no D1 bucket rows are seeded, so the map is empty');
});

test('readTrafficBreakdown is the single reader both routes import', async () => {
  const env = createEnv();
  const direct = await readTrafficBreakdown(env, DAY);
  assert.deepEqual(direct, { date: DAY, breakdown: { mcp: 6499, agent: 84, crawler: 18, pageview: 44 },
                             total: 6645 });
});

// ── degradation ──────────────────────────────────────────────────────────────────────────────────

test('with no counter store at all the route says so instead of inventing a zero', async () => {
  const response = await worker.fetch(request('/api/activity'), createEnv({ d1: null, kv: false }));
  assert.equal(response.status, 503);
  const body = await response.json();
  assert.ok(body.error, JSON.stringify(body));
  assert.equal(body.total, undefined, 'a zero total would render as "no calls today"');
});

test('a counter read that throws degrades to the KV fallback rather than a 500', async () => {
  const throwing = {
    prepare() {
      return { bind() { return this; },
               async all() { throw new Error('D1_ERROR: no such table: counters at prepare'); },
               async run() { throw new Error('D1_ERROR'); } };
    },
  };
  const env = createEnv({ d1: throwing });
  const response = await worker.fetch(request('/api/activity'), env);
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.total, 0, 'no KV counts seeded: the honest answer is zero here, not a failure');
});
