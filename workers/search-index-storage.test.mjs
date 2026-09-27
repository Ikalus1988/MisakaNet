// The index lives in ONE row, under a hard cap, and a write that fails publishes nothing.
//
// Why this file exists (2026-09-26). The live worker served `GET /api/search-index` →
// `{docCount: 411, builtAt: "2026-09-26T08:16:11Z", stale: false}`, while D1 held 417 lessons and
// `/api/lessons` served all 417 — an index frozen for ~8 hours with a fresh source, so every lesson
// merged after 08:03 that day was retrievable by id and invisible to `misakanet_search`. The refresh
// runs every 15 minutes (`wrangler.toml` → `crons = ["*/15 * * * *"]`), so something in the publish
// step was failing silently, and the endpoint had no field that said what.
//
// The two facts that shape the fix:
//
// 1. `storePut` writes the index as one `kv_store.value` cell, and D1 caps a row at 2 MB
//    (https://developers.cloudflare.com/d1/platform/limits/). A production-shaped rich index measured
//    1.63 MB over 463 lesson files / 10,133 terms on the same day — ~80% of the cap, growing with the
//    corpus, and the KV fallback has been out of write budget since 2026-09-22 (#2111). So the publish
//    step is a cliff, and the failure mode past it is the silent one.
// 2. The diagnosis cannot live inside the index row: that row is the thing that fails to write. It
//    lives in a small row of its own, written on every attempt and reported by the endpoint.
//
// These tests are about the *storage shape* and the *reporting*, not about BM25 ranking — the ranking
// has its own files.
//
// Run: node --test workers/search-index-storage.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, {
  buildBM25Index,
  decodeIndexFromStorage,
  encodeIndexForStorage,
  readStoredIndex,
  refreshSearchIndex,
  BM25_INDEX_KEY,
  BM25_INDEX_HEALTH_KEY,
  storePut,
} from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('search-index-storage');

// A corpus big enough that its index has the shape of the real one (repeated words, long paths), so
// the compression ratio is not a property of three tiny documents.
function syntheticLessons(count = 300) {
  const words = ['timeout', 'proxy', 'mirror', 'sandbox', 'headless', 'keyring', 'dco', 'kubectl',
                 'webpack', 'landlock', 'wsl', 'chrome', 'pdf', 'supervisor', 'corpus'];
  const lessons = [];
  for (let i = 0; i < count; i += 1) {
    const body = Array.from({ length: 120 }, (_, j) => words[(i + j) % words.length]).join(' ');
    lessons.push({
      id: `lesson-${i}`,
      title: `Failure ${i} about ${words[i % words.length]}`,
      domain: 'devops',
      tags: [words[i % words.length], 'regression'],
      path: `lessons/contrib/lesson-${i}.md`,
      summary: body.slice(0, 400),
      preview: body,
    });
  }
  return lessons;
}

/** A durable store backed by a Map, with a per-row byte cap like D1's. */
function createStore({ rowLimitBytes = Infinity, lessons = syntheticLessons() } = {}) {
  const rows = new Map();
  const rejected = [];
  const kv = {
    async get(key, type) {
      if (!rows.has(key)) return null;
      const raw = rows.get(key);
      return type === 'json' ? JSON.parse(raw) : raw;
    },
    async put(key, value) {
      const raw = String(value);
      if (raw.length > rowLimitBytes) {
        rejected.push({ key, bytes: raw.length });
        throw new Error(`row too large: ${raw.length} > ${rowLimitBytes}`);
      }
      rows.set(key, raw);
      return { success: true };
    },
    async delete(key) { rows.delete(key); },
  };
  return {
    MCP_TOKEN: TOKEN,
    MISAKANET_KV: kv,
    _rows: rows,
    _rejected: rejected,
    // `refreshSearchIndex` reads the corpus through loadLessonsFresh → D1. No D1 binding here, so it
    // takes the cached-payload path this stub provides.
    _lessons: lessons,
  };
}

// `loadLessons` reads `proxy:lessons:d1` / `proxy:lessons` from the store; seeding the same KV shape
// keeps this file independent of the D1 stub.
function seedLessons(env, lessons = env._lessons) {
  env._seed = { ts: Date.now(), data: lessons };
  env.MISAKANET_KV.get = (async (key, type) => {
    if (key === 'proxy:lessons' || key === 'proxy:lessons:d1') {
      return type === 'json' ? env._seed : JSON.stringify(env._seed);
    }
    const raw = env._rows.get(key);
    if (raw === undefined) return null;
    return type === 'json' ? JSON.parse(raw) : raw;
  }).bind(env.MISAKANET_KV);
}

// ── the encoding ────────────────────────────────────────────────────────────────────────────────────

test('an index round-trips through storage unchanged', async () => {
  const index = buildBM25Index(syntheticLessons(20), { textMode: 'rich' });
  const json = JSON.stringify(index);
  const stored = await encodeIndexForStorage(json);
  assert.notEqual(stored, json, 'the payload was not encoded at all');
  const back = await decodeIndexFromStorage(stored);
  assert.deepEqual(back, index, 'the decoded index must be the one that was built');
});

test('the encoded row is much smaller than the plain one', async () => {
  const index = buildBM25Index(syntheticLessons(300), { textMode: 'rich' });
  const json = JSON.stringify(index);
  const stored = await encodeIndexForStorage(json);
  const ratio = stored.length / json.length;
  assert.ok(ratio < 0.5, `gzip+base64 kept ${(ratio * 100).toFixed(0)}% of the payload — expected ` +
    `well under half, or the row cap it exists to stay under is not actually being avoided`);
  assert.ok(json.length > 200_000, `the fixture is too small to say anything about size: ${json.length}`);
});

test('a legacy plain row still loads', async () => {
  // Deploying this must not throw the published index away: the old row is plain JSON.
  const index = buildBM25Index(syntheticLessons(10), { textMode: 'rich' });
  const back = await decodeIndexFromStorage(JSON.stringify(index));
  assert.deepEqual(back, index, 'a plain stored index must still decode');
  assert.equal(await decodeIndexFromStorage(null), null);
  assert.equal(await decodeIndexFromStorage('not json'), null);
});

test('an unreadable encoded row degrades to null rather than throwing', async () => {
  const broken = JSON.stringify({ __indexEncoding: 'gzip+base64', payload: 'bm90IGd6aXA=' });
  assert.equal(await decodeIndexFromStorage(broken), null);
});

// ── the cliff ───────────────────────────────────────────────────────────────────────────────────────

test('the index is published even where the plain payload would exceed the row cap', async () => {
  // The regression, stated as the storage it happens on: a cap that the *plain* index blows past and
  // the encoded one does not. Before the encoding this write failed, `refreshed` came back false with
  // `storage write failed`, and the previous index kept answering — which is the frozen state the live
  // worker was in.
  const lessons = syntheticLessons(300);
  const plain = JSON.stringify(buildBM25Index(lessons, { textMode: 'rich' }));
  const cap = Math.ceil(plain.length / 2);
  const env = createStore({ rowLimitBytes: cap, lessons });
  seedLessons(env, lessons);

  const result = await refreshSearchIndex(env);
  assert.equal(result.refreshed, true, JSON.stringify(result));
  assert.ok(result.storedBytes < cap, `stored ${result.storedBytes} bytes against a ${cap} cap`);
  assert.ok(result.plainBytes > cap, `the fixture must exceed the cap when plain: ${result.plainBytes}`);

  const published = await readStoredIndex(env);
  assert.equal(published.docCount, lessons.length, 'the published index is readable through the store');
});

// ── the reporting ───────────────────────────────────────────────────────────────────────────────────

test('a successful refresh records what it published', async () => {
  const env = createStore();
  seedLessons(env);
  const result = await refreshSearchIndex(env);
  assert.equal(result.refreshed, true, JSON.stringify(result));

  const health = JSON.parse(env._rows.get(BM25_INDEX_HEALTH_KEY));
  assert.equal(health.refreshed, true, JSON.stringify(health));
  assert.equal(health.docCount, result.docCount);
  assert.equal(health.corpusCount, result.corpusCount);
  assert.ok(health.plainBytes >= health.storedBytes, JSON.stringify(health));
  assert.equal(health.encoding, 'gzip+base64', JSON.stringify(health));
  assert.ok(Date.parse(health.at), 'the record must carry when it was made');
});

test('a failed publish is recorded where the index row cannot swallow the diagnosis', async () => {
  // Cap below the encoded index but above the health row: exactly the state where the index cannot be
  // written and a diagnosis *inside* it would never arrive.
  const lessons = syntheticLessons(300);
  const plain = JSON.stringify(buildBM25Index(lessons, { textMode: 'rich' }));
  const encoded = (await encodeIndexForStorage(plain)).length;
  // The worker's own build adds `syncStamp`, so the cap is derived from the encoder's output rather
  // than from a second build that could differ by a few bytes.
  const cap = encoded - 1;
  const env = createStore({ rowLimitBytes: cap, lessons });
  seedLessons(env, lessons);

  const result = await refreshSearchIndex(env);
  assert.equal(result.refreshed, false, JSON.stringify(result));
  assert.equal(result.reason, 'storage write failed', JSON.stringify(result));
  // `overRowLimit` reports D1's *documented* cap (2 MB), not this stub's: the encoded row is 12 KB, so
  // the flag is rightly false here and the refusal came from the synthetic cap. The flag exists for the
  // day the encoded payload crosses 2 MB, and a reader must be able to tell those two states apart.
  assert.equal(result.overRowLimit, false, JSON.stringify(result));
  assert.ok(result.storedBytes > cap, `the refused row is the stored one: ${JSON.stringify(result)}`);
  assert.ok(result.storedBytes < plain.length, JSON.stringify(result));
  assert.ok(result.plainBytes > result.storedBytes, JSON.stringify(result));

  const health = JSON.parse(env._rows.get(BM25_INDEX_HEALTH_KEY));
  assert.equal(health.reason, 'storage write failed');
  assert.equal(health.storedBytes, result.storedBytes, JSON.stringify(health));
  assert.equal(health.corpusCount, lessons.length, 'the size of the corpus it saw belongs in the record');
  assert.ok(env._rejected.some(r => r.key === BM25_INDEX_KEY), env._rejected);
});

test('the endpoint reports the last refresh next to the index it published', async () => {
  const env = createStore();
  seedLessons(env);
  await refreshSearchIndex(env);

  const resp = await worker.fetch(new Request('https://misakanet.org/api/search-index'), env);
  const body = await resp.json();
  assert.equal(body.available, true, JSON.stringify(body));
  assert.equal(body.docCount, env._lessons.length, JSON.stringify(body));
  assert.equal(body.behindBy, 0, `published and seen must agree right after a refresh: ${JSON.stringify(body)}`);
  assert.equal(body.lastRefresh?.reason, undefined, 'a successful refresh has no failure reason');
  assert.equal(body.lastRefresh?.refreshed, true, JSON.stringify(body.lastRefresh));
  assert.equal(body.lastRefresh?.corpusCount, env._lessons.length, JSON.stringify(body.lastRefresh));
});

test('a frozen index is visible as stuck, not only as old', async () => {
  // The live state on 2026-09-26: `docCount 411`, `builtAt` 8 hours old, `stale: false` (the threshold
  // is 20 hours), and a corpus of 417 — a reader had `corpusHint` and no number. What has to be visible
  // is "a refresh ran, it saw 300, and the published index still says 290 — and here is why".
  const env = createStore();
  seedLessons(env);
  await refreshSearchIndex(env);

  // Put a *stale* index in storage: the state after a corpus change whose publish failed. Written
  // directly so the refusal below is what stops the refresh, not this setup line.
  const published = await readStoredIndex(env);
  published.docCount = published.docCount - 10;
  env._rows.set(BM25_INDEX_KEY, await encodeIndexForStorage(JSON.stringify(published)));

  // A cap between the two rows: the index row is too big to write, the health row is not. That is the
  // shape of the real cliff, and it is why the diagnosis has a row of its own.
  env.MISAKANET_KV_ROW_LIMIT = null;
  env._rowLimit = 5_000;
  env.MISAKANET_KV.put = (async (key, value) => {
    const raw = String(value);
    if (raw.length > 5_000) {
      env._rejected.push({ key, bytes: raw.length });
      throw new Error(`row too large: ${raw.length} > 5000`);
    }
    env._rows.set(key, raw);
    return { success: true };
  }).bind(env.MISAKANET_KV);

  // The refresh runs, sees 300 against a published 290, rebuilds, and cannot publish.
  const failed = await refreshSearchIndex(env);
  assert.equal(failed.refreshed, false, JSON.stringify(failed));
  assert.equal(failed.reason, 'storage write failed', JSON.stringify(failed));
  assert.equal(failed.docCount, 300, JSON.stringify(failed));

  const body = await (await worker.fetch(new Request('https://misakanet.org/api/search-index'), env)).json();
  assert.equal(body.docCount, 290, `the published index is still the stale one: ${JSON.stringify(body)}`);
  assert.equal(body.lastRefresh.docCount, 300, JSON.stringify(body.lastRefresh));
  assert.equal(body.lastRefresh.reason, 'storage write failed', JSON.stringify(body.lastRefresh));
  assert.equal(body.behindBy, 10, `behindBy must expose the gap: ${JSON.stringify(body)}`);
});

test('the health row survives a store that refuses everything else', async () => {
  // `storePut` falls back to KV when D1 refuses. Both paths are stubbed here to refuse *large* values
  // only, which is the failure this file is about; the health row is small by design and must land.
  const env = createStore({ rowLimitBytes: 2_048 });
  seedLessons(env);
  const result = await refreshSearchIndex(env);
  assert.equal(result.refreshed, false, JSON.stringify(result));
  const stored = [...env._rows.keys()];
  assert.deepEqual(stored, [BM25_INDEX_HEALTH_KEY],
    `only the health row may be written when the index row is refused: ${stored.join(', ')}`);
  await storePut(env, 'probe', 'x'.repeat(3_000));
  assert.ok(env._rejected.length >= 2, 'the cap must be real — a stub that accepts everything proves nothing');
});
