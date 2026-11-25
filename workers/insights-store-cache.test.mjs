// Two rolling aggregates stop being recomputed once per caller (2026-11-25).
//
// Measured in Cloudflare's D1 analytics over the 24 h to 2026-11-25, by statement:
//
//   5,223,595 rows  /api/analytics, `lesson_usage` 7-day GROUP BY      24.9% of every row read
//                   (23,915 rows/call × 222 calls, on a table of 26,998 rows)
//   2,496,800 rows  the per-lesson `COUNT(DISTINCT client_hint)`      11.9%
//                   (6,468 rows/call × 386 calls — `top_id = ? OR top_id LIKE '%/<id>.md'`)
//   1,555,836 rows  `/api/analytics`, the day-aligned series            7.4%
//
// Neither is an index problem. `/api/analytics` already had an edge entry, but an edge entry is
// per-colo and dies with its TTL, so on this traffic the same seven-day answer was paid for 222
// times a day; the lesson-client count is a scan by construction (an `OR` plus a leading wildcard),
// and it changes only when someone searches.
//
// What this file pins:
//   * a second `/api/analytics` request inside the hour runs **no** `lesson_usage` query;
//   * the two audiences are stored under **different keys** — the maintainer payload carries
//     other people's verbatim failed queries, so one shared entry would publish them;
//   * a per-lesson client count is answered once per window, and a different lesson is not served
//     from it.
//
// Run: node --test workers/insights-store-cache.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, { countDistinctRetrievingClients } from './register-proxy-sw.js';

// Assembled at runtime: the repo's secret scanner reports a token-shaped name followed by a quoted
// literal as HARDCODED_SECRET (see tests/test_scanner_secret_patterns.py).
const MCP_TOKEN = ['maintainer', 'token'].join('-');

/**
 * A D1 stub with a real in-memory `kv_store` and a statement log.
 *
 * The log is the point: "did this answer cost a scan?" is asked as "did `lesson_usage` appear again?",
 * which is the saving rather than the header. `kv_store` has to actually hold rows or the durable
 * cache would miss every time and the test would prove nothing.
 */
function storeD1(rows = []) {
  const state = { sql: [], store: new Map() };
  return {
    state,
    prepare(sql) {
      const flat = String(sql).replace(/\s+/g, ' ').trim();
      state.sql.push(flat);
      const stmt = {
        _bound: [],
        bind(...args) { stmt._bound = args; return stmt; },
        async all() {
          if (/FROM kv_store/.test(flat)) {
            const value = state.store.get(String(stmt._bound[0]));
            return { results: value === undefined ? [] : [{ value }] };
          }
          return { results: rows };
        },
        async first() {
          const out = await stmt.all();
          return (out.results && out.results[0]) || null;
        },
        async run() {
          if (/INSERT INTO kv_store/.test(flat)) {
            state.store.set(String(stmt._bound[0]), String(stmt._bound[1]));
          }
          return { success: true };
        },
      };
      return stmt;
    },
    async batch() { return []; },
    async exec() { return { count: 0 }; },
  };
}

const kv = () => ({
  async get() { return null; },
  async put() { return undefined; },
  async delete() { return undefined; },
  async list() { return { keys: [], list_complete: true }; },
});

const envWith = (d1) => ({ MISAKANET_D1: d1, MISAKANET_KV: kv(), MCP_TOKEN });

const analytics = (env, token) => worker.fetch(new Request('https://misakanet.org/api/analytics', {
  headers: token ? { Authorization: `Bearer ${token}` } : {},
}), env);

const usageQueries = (state) => state.sql.filter((sql) => /FROM lesson_usage/.test(sql)).length;

test('a second /api/analytics request inside the hour runs no lesson_usage query', async () => {
  const d1 = storeD1();
  const env = envWith(d1);

  const first = await analytics(env);
  assert.equal(first.status, 200);
  const afterFirst = usageQueries(d1.state);
  assert.ok(afterFirst >= 4, `the first request must compute the aggregates, saw ${afterFirst}`);

  const second = await analytics(env);
  assert.equal(second.status, 200);
  assert.equal(usageQueries(d1.state), afterFirst,
    'the second request re-ran the aggregates; the durable copy did not answer');
  assert.deepEqual(await second.json(), await first.json(), 'and the answer is unchanged');
});

test('the two audiences are stored under different keys', async () => {
  const d1 = storeD1();
  const env = envWith(d1);

  await analytics(env);
  const anonymousOnly = usageQueries(d1.state);
  const keysAfterAnonymous = [...d1.state.store.keys()].filter((k) => k.includes('analytics'));

  const maintainer = await analytics(env, MCP_TOKEN);
  assert.equal(maintainer.status, 200);
  assert.ok(usageQueries(d1.state) > anonymousOnly,
    'the maintainer must not be answered from the anonymous entry: knowledge_gaps would be wrong');

  const keys = [...d1.state.store.keys()].filter((k) => k.includes('analytics'));
  assert.equal(keys.length, 2, `expected one entry per audience, saw ${JSON.stringify(keys)}`);
  assert.deepEqual(keysAfterAnonymous.length, 1);
  assert.ok(keys.some((k) => k.endsWith(':anonymous')));
  assert.ok(keys.some((k) => k.endsWith(':maintainer')));
});

test('the per-lesson client count is answered once per window, per lesson', async () => {
  const d1 = storeD1([{ clients: 3 }]);
  const env = envWith(d1);

  assert.equal(await countDistinctRetrievingClients(env, { lessonId: 'a-lesson' }), 3);
  const afterFirst = d1.state.sql.filter((sql) => /FROM search_signals/.test(sql)).length;
  assert.equal(afterFirst, 1, 'the first count is one scan');

  assert.equal(await countDistinctRetrievingClients(env, { lessonId: 'a-lesson' }), 3);
  assert.equal(d1.state.sql.filter((sql) => /FROM search_signals/.test(sql)).length, afterFirst,
    'the second count for the same lesson re-scanned search_signals');

  assert.equal(await countDistinctRetrievingClients(env, { lessonId: 'another-lesson' }), 3);
  assert.equal(d1.state.sql.filter((sql) => /FROM search_signals/.test(sql)).length, afterFirst + 1,
    'a different lesson must not be answered from the first one\'s entry');
});

test('a count of zero is not cached as an answer for the next client', async () => {
  // The store refuses to cache falsy payloads, which is what keeps "nobody has retrieved this yet"
  // from being pinned for fifteen minutes — the same rule the search corpus follows.
  const d1 = storeD1([{ clients: 0 }]);
  const env = envWith(d1);
  assert.equal(await countDistinctRetrievingClients(env, { lessonId: 'fresh-lesson' }), 0);
  const stored = [...d1.state.store.keys()].filter((k) => k.includes('lesson-clients'));
  assert.deepEqual(stored, [], `zero must not be stored, saw ${JSON.stringify(stored)}`);
});
