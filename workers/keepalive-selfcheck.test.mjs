// The keepalive must not ask this worker to serve its own request (#2126).
//
// Measured 2026-09-24 from the zone's own analytics (72h, cf-diagnostics run 5): the zone recorded
// 2,398 HTTP 522s and every one of them came from the keepalive's three self-probes —
// `/api/lessons` 826, `/api/health` 790, `/api/counter` 782, summing to exactly the zone total —
// while `/journey/`, served by the *site* worker, recorded none. A cron handler that awaits a fetch
// to its own zone URL is waiting for a response the same single-threaded isolate has to produce, so
// the subrequest dies at the edge every time. The keepalive was an alarm that rang on every run, and
// it buried the 504s that were the actual signal.
//
// Two properties are pinned here: the list may not contain a route this worker serves (that is the
// invariant that failed), and the in-process replacement must be able to both pass and fail.
//
// Run: node --test workers/keepalive-selfcheck.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { KEEPALIVE_ENDPOINTS, probeSelfInProcess, runKeepaliveSweep } from './register-proxy-sw.js';

// The paths `workers/wrangler.toml`'s zone routes send to *this* worker (read from the zone on
// 2026-09-24: /mcp, /mcp/*, /ping, /api/*, /connect*, /start*). A keepalive entry matching any of
// these is a request this worker would have to answer while awaiting it.
const SELF_ROUTES = [/^\/api\//, /^\/ping$/, /^\/mcp(\/|$)/, /^\/connect/, /^\/start/];

test('no keepalive endpoint is a route this worker serves', () => {
  assert.ok(KEEPALIVE_ENDPOINTS.length > 0, 'the keepalive has no cross-worker endpoint left to probe');
  for (const endpoint of KEEPALIVE_ENDPOINTS) {
    const path = new URL(endpoint.url).pathname;
    assert.ok(!SELF_ROUTES.some((re) => re.test(path)),
      `${endpoint.url} is served by this worker, so awaiting it can only 522 — probe it in-process ` +
      '(probeSelfInProcess) or from another worker');
  }
});

test('the endpoint that survived is the cross-worker one', () => {
  // Not decoration: if this list is ever emptied, the HTTP half of the keepalive is gone and nobody
  // would notice until a real outage.
  assert.deepEqual(KEEPALIVE_ENDPOINTS.map((e) => new URL(e.url).pathname), ['/journey/']);
});

function fakeKV() {
  const store = new Map();
  return {
    async get(key) { return store.has(key) ? store.get(key) : null; },
    async put(key, value) { store.set(key, value); },
    async delete(key) { store.delete(key); },
    _store: store,
  };
}

function fakeD1() {
  const queries = [];
  return {
    _queries: queries,
    prepare(sql) {
      const stmt = {
        bind: () => stmt,
        async first() { queries.push(sql); return { ok: 1 }; },
        async all() { queries.push(sql); return { results: [] }; },
        async run() { queries.push(sql); return { success: true }; },
      };
      return stmt;
    },
  };
}

test('the in-process self-check reads the store, and asks D1 when it is bound', async () => {
  const kv = fakeKV();
  const d1 = fakeD1();
  const result = await probeSelfInProcess({ MISAKANET_KV: kv, MISAKANET_D1: d1 });
  assert.equal(result.inProcess, true);
  assert.deepEqual(result.checks, ['store_read', 'd1_query']);
  assert.ok(d1._queries.length >= 1, 'D1 was bound but never queried');
});

test('the self-check fails when nothing is bound to persist with', async () => {
  // The failure this replaces the 522-noise with: an outage that is real and reported once.
  await assert.rejects(() => probeSelfInProcess({}), /no durable store/);
});

test('a broken store fails the sweep rather than passing quietly', async () => {
  const broken = {
    async get() { throw new Error("KV GET failed"); },
    async put() { throw new Error("KV PUT failed"); },
    async delete() { throw new Error("KV DELETE failed"); },
  };
  const result = await runKeepaliveSweep('*/15 * * * *', { MISAKANET_KV: broken });
  assert.equal(result.ok, false);
  assert.ok(result.failures.some((f) => /store|GET|failed/.test(f)), JSON.stringify(result.failures));
});

test('a healthy sweep reports which checks ran, not just "ok"', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response('<!doctype html><html></html>', {
    status: 200, headers: { 'content-type': 'text/html' },
  });
  try {
    const result = await runKeepaliveSweep('*/15 * * * *', { MISAKANET_KV: fakeKV(), MISAKANET_D1: fakeD1() });
    assert.equal(result.ok, true);
    assert.deepEqual(result.checks, ['store_read', 'd1_query']);
  } finally {
    globalThis.fetch = original;
  }
});
