// The corpus is read from KV, not through D1 (2026-11-17).
//
// Why: the durable cache the corpus used before reads *through* D1 (`storeGet` → `d1.prepare`), so a
// cache hit still billed a row read. Measured on the dashboard 2026-11-13..16: 30k read queries a day
// (flat) against 240M / 1.43B / 1.38B / 1.91B rows read. The Analytics Engine phase breakdown put
// `corpus read (memo/KV/D1)` at p95 6440 ms against `misakanet_search` p95 6337 ms — the read *is*
// the search.
//
// These tests pin the two properties that make the change worth making, and the one that keeps it safe:
//
//   * a fresh KV corpus answers with **zero** D1 statements prepared;
//   * a stale or malformed KV value falls back to D1 and rewrites KV;
//   * with no KV binding at all, the previous behaviour is untouched.
//
// Run: node --test workers/corpus-kv-cache.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, { loadLessons, resetLessonsReadState, lastLessonsReadOf } from './register-proxy-sw.js';

const ROWS = [
  { id: 'kv-lesson-one', title: 'One', domain: 'python', tags: ['pip'], status: 'published', summary: 'a' },
  { id: 'kv-lesson-two', title: 'Two', domain: 'git', tags: ['git'], status: 'published', summary: 'b' },
];

/** A KV that records reads/writes and can serve one prepared value. */
function kvWith(value, { getThrows = false } = {}) {
  const log = { gets: [], puts: [] };
  return {
    log,
    async get(key, type) {
      log.gets.push(key);
      if (getThrows) throw new Error('kv unavailable');
      // Only the corpus key is prepared: a fake that answered for *every* key would also satisfy the
      // durable store the D1 path reads through, which is a different call site.
      if (key !== 'corpus:v1' || value === undefined) return null;
      return type === 'json' ? value : JSON.stringify(value);
    },
    async put(key, text) { log.puts.push({ key, bytes: String(text).length }); },
  };
}

/** A D1 binding that counts statements, so "did this read bill a row?" is answerable. */
function countingD1(rows = ROWS) {
  const state = { prepares: 0, alls: 0 };
  const stmt = {
    bind() { return stmt; },
    async all() { state.alls += 1; return { results: rows }; },
    async first() { state.alls += 1; return rows[0] ?? null; },
    async run() { return { success: true }; },
  };
  return {
    state,
    prepare() { state.prepares += 1; return stmt; },
    async batch() { return []; },
    async exec() { return { count: 0 }; },
  };
}

function envWith({ kv, d1 } = {}) {
  const env = { REGISTER_TOKEN: 'x', MCP_TOKEN: 'x' };
  if (kv) env.MISAKANET_KV = kv;
  if (d1) env.MISAKANET_D1 = d1;
  return env;
}

test.beforeEach(() => resetLessonsReadState());

test('a fresh KV corpus answers without preparing a single D1 statement', async () => {
  const kv = kvWith({ ts: Date.now(), rows: ROWS });
  const d1 = countingD1();
  const rows = await loadLessons(envWith({ kv, d1 }), {});
  assert.deepEqual(rows.map((r) => r.id), ['kv-lesson-one', 'kv-lesson-two']);
  assert.equal(d1.state.prepares, 0, 'a KV hit must not touch D1 at all');
  assert.equal(lastLessonsReadOf().source, 'kv');
});

test('a stale KV corpus is not served, and the D1 read rewrites it', async () => {
  const kv = kvWith({ ts: Date.now() - 10 * 60 * 1000, rows: ROWS }); // older than PROXY_CACHE_TTL
  const d1 = countingD1();
  const rows = await loadLessons(envWith({ kv, d1 }), {});
  assert.equal(rows.length, 2);
  assert.ok(d1.state.prepares > 0, 'the stale entry must be re-read from D1');
  assert.equal(kv.log.puts.length, 1, 'and the fresh read must be written back to KV');
  assert.equal(kv.log.puts[0].key, 'corpus:v1');
});

test('a malformed KV value falls back instead of throwing', async () => {
  for (const value of [{ ts: Date.now() }, { rows: [] }, { rows: 'not-an-array' }, null]) {
    resetLessonsReadState();
    const kv = kvWith(value);
    const rows = await loadLessons(envWith({ kv, d1: countingD1() }), {});
    assert.equal(rows.length, 2, `value ${JSON.stringify(value)} must not be served as the corpus`);
  }
});

test('an unreadable KV falls back to D1 rather than failing the search', async () => {
  const kv = kvWith(undefined, { getThrows: true });
  const rows = await loadLessons(envWith({ kv, d1: countingD1() }), {});
  assert.equal(rows.length, 2);
});

test('with no KV binding the previous D1 path is unchanged', async () => {
  const d1 = countingD1();
  const rows = await loadLessons(envWith({ d1 }), {});
  assert.equal(rows.length, 2);
  assert.ok(d1.state.prepares > 0);
});

test('a filtered read still goes to D1 — KV holds the whole corpus, not a view of it', async () => {
  const kv = kvWith({ ts: Date.now(), rows: ROWS });
  const d1 = countingD1();
  await loadLessons(envWith({ kv, d1 }), { domain: 'python' });
  assert.ok(d1.state.prepares > 0, 'filters must not be answered from the unfiltered KV copy');
});
