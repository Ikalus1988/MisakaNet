// The corpus is read from KV, not through D1 (2026-11-17), and it stays in KV for an hour (2026-11-25).
//
// Why KV: the durable cache the corpus used before reads *through* D1 (`storeGet` → `d1.prepare`), so a
// cache hit still billed a row read. Measured on the dashboard 2026-11-13..16: 30k read queries a day
// (flat) against 240M / 1.43B / 1.38B / 1.91B rows read.
//
// Why an hour: measured 2026-11-25 in production. The KV copy was written with a 330 s
// `expirationTtl` and read back with a 300 s window, while searches arrive ~14 times an hour — so the
// key was expired for most of the day (`corpus:v1` answered `key not found` on a direct read) and the
// 4.38 MB corpus was rewritten every 6-7 minutes, always on a search request. That is the shape of the
// phase breakdown: `corpus read` p50 26 ms against p90 5649 ms / p95 9153 ms, 41 of 343 searches over
// 5 s with a 9.07 s median corpus phase among them. The window bought no freshness either —
// `lessons.synced_at` holds one distinct value, because the corpus is written by a sync run and not by
// traffic.
//
// These tests pin the properties that make the cache worth having, and the ones that keep it safe:
//
//   * a fresh KV corpus answers with **zero** D1 statements prepared;
//   * a corpus from minutes ago is served, not rejected (the 300 s regression);
//   * a stale or malformed KV value falls back to D1 and rewrites KV;
//   * a KV miss reads `lessons` **once** and does not also read the 4.38 MB `kv_store` shards;
//   * the cron warm populates KV without a search behind it;
//   * with no KV binding at all, the previous behaviour is untouched.
//
// Run: node --test workers/corpus-kv-cache.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, {
  loadLessons,
  resetLessonsReadState,
  lastLessonsReadOf,
  storeKvCorpus,
  warmCorpusCache,
  CORPUS_KV_KEY,
  CORPUS_KV_MAX_AGE_MS,
} from './register-proxy-sw.js';

const ROWS = [
  { id: 'kv-lesson-one', title: 'One', domain: 'python', tags: ['pip'], status: 'published', summary: 'a' },
  { id: 'kv-lesson-two', title: 'Two', domain: 'git', tags: ['git'], status: 'published', summary: 'b' },
];

/** A KV that records reads/writes (and their options) and can serve one prepared value. */
function kvWith(value, { getThrows = false } = {}) {
  const log = { gets: [], puts: [] };
  return {
    log,
    async get(key, type) {
      log.gets.push(key);
      if (getThrows) throw new Error('kv unavailable');
      // Only the corpus key is prepared: a fake that answered for *every* key would also satisfy the
      // durable store the D1 path reads through, which is a different call site.
      if (key !== CORPUS_KV_KEY || value === undefined) return null;
      return type === 'json' ? value : JSON.stringify(value);
    },
    async put(key, text, options) { log.puts.push({ key, bytes: String(text).length, options }); },
  };
}

/** A D1 binding that counts statements and remembers their text, so "what did this read bill?" is answerable. */
function countingD1(rows = ROWS) {
  const state = { prepares: 0, alls: 0, sql: [] };
  return {
    state,
    prepare(sql) {
      state.prepares += 1;
      state.sql.push(String(sql).replace(/\s+/g, ' ').trim());
      const stmt = {
        bind() { return stmt; },
        async all() { state.alls += 1; return { results: rows }; },
        async first() { state.alls += 1; return rows[0] ?? null; },
        async run() { return { success: true }; },
      };
      return stmt;
    },
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

test('a corpus from ten minutes ago is served, not re-read from D1', async () => {
  // The 300 s window rejected exactly this payload — which is why every search that was not inside a
  // 30 s isolate memo paid 4.38 MB. Age here is well inside the hour and well outside the old window.
  const age = 10 * 60 * 1000;
  assert.ok(age < CORPUS_KV_MAX_AGE_MS);
  const kv = kvWith({ ts: Date.now() - age, rows: ROWS });
  const d1 = countingD1();
  const rows = await loadLessons(envWith({ kv, d1 }), {});
  assert.equal(rows.length, 2);
  assert.equal(d1.state.prepares, 0, 'a ten-minute-old corpus must not cost a D1 read');
  assert.equal(kv.log.puts.length, 0, 'and must not be rewritten either');
  assert.equal(lastLessonsReadOf().source, 'kv');
});

test('a corpus older than the window is re-read from D1 and written back', async () => {
  const kv = kvWith({ ts: Date.now() - CORPUS_KV_MAX_AGE_MS - 1000, rows: ROWS });
  const d1 = countingD1();
  const rows = await loadLessons(envWith({ kv, d1 }), {});
  assert.equal(rows.length, 2);
  assert.ok(d1.state.prepares > 0, 'the stale entry must be re-read from D1');
  assert.equal(kv.log.puts.length, 1, 'and the fresh read must be written back to KV');
  assert.equal(kv.log.puts[0].key, CORPUS_KV_KEY);
});

test('the KV copy is written with an hour of life, not five minutes', async () => {
  const kv = kvWith(undefined);
  assert.equal(await storeKvCorpus(envWith({ kv }), ROWS), true);
  assert.equal(kv.log.puts.length, 1);
  const ttl = kv.log.puts[0].options?.expirationTtl;
  assert.ok(typeof ttl === 'number', 'the write must set an explicit expirationTtl');
  assert.ok(ttl >= 3600, `a KV entry that dies in ${ttl}s cannot survive a sparse traffic hour`);
});

test('a KV miss reads the lessons table once and never the 4.38 MB shard cache', async () => {
  // Before 2026-11-25 a miss read `proxy:lessons:d1` (manifest + four ~1 MB chunk rows) and then read
  // the same corpus from `lessons`, and wrote all of it back. The assertion is on the SQL, not just the
  // count: `kv_store` is the shard cache, and touching it on this path is the regression.
  const kv = kvWith(undefined);
  const d1 = countingD1();
  const rows = await loadLessons(envWith({ kv, d1 }), {});
  assert.equal(rows.length, 2);
  const touched = d1.state.sql;
  assert.ok(touched.some((sql) => /FROM lessons/.test(sql)), 'the corpus must come from `lessons`');
  assert.ok(
    touched.every((sql) => !/kv_store/.test(sql)),
    `the corpus read must not go through the shard cache, got: ${JSON.stringify(touched)}`,
  );
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

test('the cron warm puts the corpus in KV with no search behind it', async () => {
  const kv = kvWith(undefined);
  const d1 = countingD1();
  assert.equal(await warmCorpusCache(envWith({ kv, d1 })), true);
  assert.equal(kv.log.puts.length, 1);
  assert.equal(kv.log.puts[0].key, CORPUS_KV_KEY);
  // A warm that answered from the corpus it just wrote would be a no-op after the first run; the
  // point of the cron is that it reads D1 every time and the *readers* never do.
  assert.ok(d1.state.sql.some((sql) => /FROM lessons/.test(sql)));
});

test('the cron warm is a no-op without a KV binding', async () => {
  assert.equal(await warmCorpusCache(envWith({ d1: countingD1() })), false);
});
