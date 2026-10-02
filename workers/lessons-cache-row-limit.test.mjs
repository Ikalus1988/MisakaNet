// The corpus cache is the one payload in this worker that grows with the corpus — and it was stored
// as ONE `kv_store` row, 9% under a hard cap, with the refusal swallowed.
//
// The state on 2026-10-02, measured by driving this worker's own shaping code over the repo's 436
// rich rows (`/api/lessons` with a D1 stub holding them): `getWithCache` hands `storePut`
// **1,821,172 bytes** for `proxy:lessons:d1` — 91% of D1's 2 MB row cap
// (https://developers.cloudflare.com/d1/platform/limits/), and ~4.2 KB per lesson, so ~43 lessons of
// headroom. At the corpus' own recent rate (426 rows on 2026-09-29 → 436 on 2026-10-02) that is under
// two weeks.
//
// What happens at the cap is the part worth a test: `storePut` is refused, falls back to KV (whose
// write budget has been spent since 2026-09-22, #2111), and the old `getWithCache` discarded
// `storePut`'s answer and swallowed both errors — so this key would silently stop being durable,
// which is the entire property #2116 migrated it for. `search-index-storage.test.mjs` (#2327) covers
// the same cliff for the search index; this file covers the cache that carries the corpus.
//
// The fix is a *storage shape*, not a new cache: a payload that would cross `CACHE_SINGLE_ROW_BYTES`
// (1.9 MB, 95% of the cap) is written as a small manifest row plus chunk rows, and no row we write
// exceeds that budget. The cached value is byte-identical, so no reader changes — only
// `getWithCache` joins the chunks.
//
// These tests are deliberately about the storage decision and the *reporting*: a payload over the cap
// must be an explicit success (sharded) or an explicit refusal (warned), never a quiet "fine".
//
// Run: node --test workers/lessons-cache-row-limit.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, {
  D1_ROW_LIMIT_BYTES,
  CACHE_SINGLE_ROW_BYTES,
  CACHE_CHUNK_BYTES,
  CACHE_CHUNK_MARK,
  readCachePayload,
  storeCachePayload,
  splitByUtf8Bytes,
  storePut,
  utf8Bytes,
} from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('lessons-cache-row-limit');
const CACHE_KEY = 'proxy:lessons:d1';

// A corpus in the shape `scripts/sync_lessons_to_d1.py` writes: every `lessons` column the rich
// projection selects, as text (the sync stores strings; `tags` is already JSON text). The bodies are
// the payload: `indexText` is `content_md[:6000]` and is ~72% of what the cache holds, so a fixture
// without realistic bodies would never reach the cap this file is about.
function d1Rows(count = 560, bodyChars = 3_600) {
  const words = ['timeout', 'proxy', 'mirror', 'sandbox', 'headless', 'keyring', 'dco', 'kubectl',
                 'webpack', 'landlock', 'wsl', 'chrome', 'supervisor', 'corpus', '证据'];
  const rows = [];
  for (let i = 0; i < count; i += 1) {
    const body = Array.from({ length: Math.ceil(bodyChars / 8) },
      (_, j) => words[(i * 7 + j) % words.length]).join(' ').slice(0, bodyChars);
    rows.push({
      id: `lesson-${i}`,
      title: `Failure ${i} about ${words[i % words.length]}`,
      domain: 'devops',
      status: 'published',
      tags: JSON.stringify([words[i % words.length], 'regression']),
      path: `lessons/contrib/lesson-${i}.md`,
      summary: body.slice(0, 400),
      problem: body.slice(0, 400),
      created: '2026-09-01T00:00:00Z',
      updated: '2026-10-01T00:00:00Z',
      root_cause: body.slice(0, 300),
      solution: body.slice(0, 200),
      verification: 'verified',
      content_md: body,
      frontmatter: JSON.stringify({ evidence_level: 'reproduced' }),
    });
  }
  return rows;
}

/**
 * A D1 stand-in that implements `kv_store` with D1's per-row byte cap, the way `search-index-storage`
 * uses a KV stand-in with the same cap: a stub that accepts everything would let a 2.5 MB single row
 * look stored.
 */
function createD1({ rows = d1Rows(), rowLimitBytes = D1_ROW_LIMIT_BYTES } = {}) {
  const kvStore = new Map();
  const rejected = [];
  const sql = [];
  return {
    kvStore,
    rejected,
    sql,
    rowLimitBytes,
    _rows: rows,
    prepare(text) {
      const statement = String(text);
      sql.push(statement);
      const limitMatch = statement.match(/LIMIT\s+(\d+)/i);
      const limit = limitMatch ? Number(limitMatch[1]) : Infinity;
      const stmt = {
        _bound: [],
        bind(...args) { stmt._bound = args; return stmt; },
        async all() {
          if (/FROM lessons/i.test(statement)) return { results: rows.slice(0, limit) };
          if (/SELECT value FROM kv_store/i.test(statement)) {
            const row = kvStore.get(String(stmt._bound[0]));
            // The expiry predicate is the worker's (`storeGet`); this fixture only ever writes none.
            return { results: row ? [{ value: row }] : [] };
          }
          return { results: [] };
        },
        async run() {
          if (/INSERT INTO kv_store/i.test(statement)) {
            const [key, value] = stmt._bound;
            const raw = String(value);
            if (utf8Bytes(raw) > rowLimitBytes) {
              rejected.push({ key: String(key), bytes: utf8Bytes(raw) });
              throw new Error(`row too large: ${utf8Bytes(raw)} > ${rowLimitBytes}`);
            }
            kvStore.set(String(key), raw);
          }
          return { success: true, meta: { changes: 1 } };
        },
      };
      return stmt;
    },
  };
}

/**
 * A KV namespace backed by a Map that records every write, and can be told to refuse them the way a
 * spent budget does (`429 … daily write limit exceeded`). It is a real store rather than a recorder,
 * so the fallback can be *read back* — "the KV path still holds the payload" is the property this
 * file must not break on its way to making D1 durable.
 */
function createKv({ refuse = false } = {}) {
  const writes = [];
  const rows = new Map();
  return {
    writes,
    rows,
    async get(key, type) {
      if (!rows.has(String(key))) return null;
      const raw = rows.get(String(key));
      return type === 'json' ? JSON.parse(raw) : raw;
    },
    async put(key, value) {
      writes.push({ key: String(key), bytes: utf8Bytes(String(value)) });
      if (refuse) throw new Error('KV PUT failed: 429 daily write limit exceeded');
      rows.set(String(key), String(value));
      return { success: true };
    },
    async delete(key) { rows.delete(String(key)); },
  };
}

function makeEnv(d1, kv) {
  const env = { MCP_TOKEN: TOKEN, MISAKANET_D1: d1 };
  if (kv) env.MISAKANET_KV = kv;
  return env;
}

const lessonsRequest = () => new Request('https://misakanet.org/api/lessons');

/** Capture `console.warn` for the duration of `fn`. */
async function withWarnings(fn) {
  const lines = [];
  const original = console.warn;
  console.warn = (...args) => lines.push(args.map(String).join(' '));
  try {
    return { result: await fn(), lines };
  } finally {
    console.warn = original;
  }
}

// ── the storage shape ────────────────────────────────────────────────────────────────────────────

test('a corpus the cap would refuse is stored as a manifest plus chunks, every row under the cap',
  async () => {
    const d1 = createD1();
    const env = makeEnv(d1, createKv());

    const resp = await worker.fetch(lessonsRequest(), env);
    assert.equal(resp.status, 200);
    assert.equal((await resp.json()).length, d1._rows.length);
    assert.deepEqual(d1.rejected, [], 'no row of this write may be refused');

    const manifest = JSON.parse(d1.kvStore.get(CACHE_KEY));
    assert.equal(manifest.sharded, true,
      `the fixture must actually cross the single-row budget: ${JSON.stringify({ ...manifest, gen: '…' })}`);
    // The fixture is over D1's *documented* cap as one row — the state the report describes and the
    // state this storage shape exists to make impossible.
    assert.ok(manifest.bytes > D1_ROW_LIMIT_BYTES,
      `the payload must be over the cap for this test to prove anything: ${manifest.bytes}`);
    assert.ok(manifest.chunks >= 2, JSON.stringify(manifest));

    const chunkKeys = [...d1.kvStore.keys()].filter((key) => key.startsWith(`${CACHE_KEY}${CACHE_CHUNK_MARK}`));
    assert.equal(chunkKeys.length, manifest.chunks, `one row per chunk: ${chunkKeys.length}`);
    for (const [key, value] of d1.kvStore) {
      assert.ok(utf8Bytes(value) <= CACHE_SINGLE_ROW_BYTES,
        `every row must stay under the budget we set, not just under D1's cap: ${key} ${utf8Bytes(value)}`);
    }

    // …and the shape it replaces really is refused by the same store, with the same bytes. Without
    // this the test would pass on a stub that refuses nothing.
    const restored = await readCachePayload(env, CACHE_KEY);
    const singleRow = JSON.stringify({ ts: manifest.ts, data: restored.data });
    assert.equal(utf8Bytes(singleRow), manifest.bytes, 'the shards must carry the payload unchanged');
    // Both destinations refused, the way production looks once KV is out of budget (#2111): `storePut`
    // reporting `true` here would mean KV saved it, which is the fallback working, not the cap.
    env.MISAKANET_KV = createKv({ refuse: true });
    const accepted = await storePut(env, 'probe:single-row', singleRow);
    assert.equal(accepted, false, 'the single-row shape must be the one this store refuses');
    assert.ok(d1.rejected.some((row) => row.key === 'probe:single-row'), JSON.stringify(d1.rejected));
  });

test('the sharded row is read back by the worker, and served without touching D1 lessons again',
  async () => {
    const d1 = createD1();
    const env = makeEnv(d1, createKv());
    const first = await (await worker.fetch(lessonsRequest(), env)).json();
    assert.equal(first.length, d1._rows.length);

    // If the cached corpus could not be read back, this second request would find no lessons at all —
    // which is how a shard set that is written but not readable shows up.
    d1._rows = [];
    const second = await (await worker.fetch(lessonsRequest(), env)).json();
    assert.equal(second.length, first.length, 'the cache must serve the corpus, not an empty list');
    assert.deepEqual(second.map((row) => row.id), first.map((row) => row.id));
    // `publicLessonRow` strips the searchable body, and the shards must not have leaked it into the API.
    assert.equal(second[0].indexText, undefined, 'indexText never leaves the worker');
  });

test('a legacy single-row payload still reads — the new shape is additive', async () => {
  const d1 = createD1({ rows: [] });
  d1.kvStore.set(CACHE_KEY, JSON.stringify({ ts: Date.now(), data: [{ id: 'legacy-marker', title: 'Legacy' }] }));
  const body = await (await worker.fetch(lessonsRequest(), makeEnv(d1, createKv()))).json();
  assert.deepEqual(body.map((row) => row.id), ['legacy-marker'],
    'a row written before this change must not need a migration');
});

// ── the reporting: a refusal is never quiet ──────────────────────────────────────────────────────

test('a write D1 and KV both refuse is reported with the key and the bytes, and the caller still gets the corpus',
  async () => {
    // D1 refuses even one chunk, and KV is out of budget — the production state since 2026-09-22
    // (#2111). The old code threw the boolean away, so this was indistinguishable from success.
    const d1 = createD1({ rowLimitBytes: 100_000 });
    const kv = createKv({ refuse: true });
    const env = makeEnv(d1, kv);

    const { result: body, lines } = await withWarnings(async () =>
      (await worker.fetch(lessonsRequest(), env)).json());

    assert.equal(body.length, d1._rows.length, 'a refused cache write is a slow path, not a failed request');
    assert.deepEqual(d1.kvStore.size, 0, 'nothing durable may be reported as stored');
    const refusal = lines.find((line) => line.includes('durable write refused'));
    assert.ok(refusal, `the refusal must be observable, got: ${JSON.stringify(lines)}`);
    assert.ok(refusal.includes(`key=${CACHE_KEY}`), `the line must name the key: ${refusal}`);
    assert.ok(refusal.includes('bytes='), `the line must carry the payload size: ${refusal}`);
    assert.ok(refusal.includes('overRowLimit=true'), `the line must say why: ${refusal}`);
    // The KV fallback is not deleted — it is what this refusal falls back *to*, and the record of the
    // attempt is what makes "out of budget" distinguishable from "never tried".
    assert.ok(kv.writes.length > 0, 'the KV fallback must still be tried');
    assert.ok(kv.writes.every((row) => row.key === CACHE_KEY || row.key.startsWith(`${CACHE_KEY}${CACHE_CHUNK_MARK}`)),
      `and tried with this cache's payload: ${JSON.stringify(kv.writes)}`);
    // Nothing readable landed anywhere, so the next request must refetch rather than serve a fragment.
    assert.equal(await readCachePayload({ MISAKANET_KV: kv }, CACHE_KEY), null);
  });

test('a payload D1 refuses but KV takes is still readable, from either store', async () => {
  const d1 = createD1({ rowLimitBytes: 100_000 });
  const kv = createKv();
  const env = makeEnv(d1, kv);

  const { result: body, lines } = await withWarnings(async () =>
    (await worker.fetch(lessonsRequest(), env)).json());

  assert.equal(body.length, d1._rows.length);
  assert.equal(lines.filter((line) => line.includes('durable write refused')).length, 0,
    `a write KV accepted is not a refusal: ${JSON.stringify(lines)}`);
  // The manifest is small enough for D1; the chunks are not. That split — one key in D1, the rest in
  // KV — is the real shape of "D1 refuses this payload, KV still takes it", and the reader has to
  // follow each key to wherever it landed.
  assert.deepEqual([...d1.kvStore.keys()], [CACHE_KEY], `only the small manifest fits: ${[...d1.kvStore.keys()]}`);
  assert.equal((await readCachePayload(env, CACHE_KEY)).data.length, d1._rows.length,
    `the reader must join a split across both stores: ${JSON.stringify(kv.writes)}`);
  assert.ok(kv.writes.some((row) => row.key.includes(CACHE_CHUNK_MARK)), JSON.stringify(kv.writes));
});

test('the KV fallback alone holds a complete copy of the sharded payload', async () => {
  // D1 refuses *every* row here (even the manifest), which is the deployment shape the fallback
  // exists for: KV must end up with a complete, readable cache, not a fragment of one.
  const d1 = createD1({ rowLimitBytes: 50 });
  const kv = createKv();
  const env = makeEnv(d1, kv);

  const { result: body } = await withWarnings(async () =>
    (await worker.fetch(lessonsRequest(), env)).json());
  assert.equal(body.length, d1._rows.length);
  assert.deepEqual(d1.kvStore.size, 0, 'D1 took nothing in this fixture');

  const restored = await readCachePayload({ MISAKANET_KV: kv }, CACHE_KEY);
  assert.equal(restored.data.length, d1._rows.length,
    `the fallback must hold the whole corpus, not a shard: ${JSON.stringify(kv.writes)}`);
  assert.ok(kv.writes.some((row) => row.key === CACHE_KEY), 'the manifest goes to KV too');
  assert.ok(kv.writes.filter((row) => row.key.includes(CACHE_CHUNK_MARK)).length >= 2,
    JSON.stringify(kv.writes));
});

test('a missing chunk is a miss with a reason, never half a corpus', async () => {
  const d1 = createD1();
  const env = makeEnv(d1, createKv());
  await worker.fetch(lessonsRequest(), env);

  const chunkKeys = [...d1.kvStore.keys()].filter((key) => key.includes(CACHE_CHUNK_MARK));
  assert.ok(chunkKeys.length >= 2, `the fixture must be sharded: ${chunkKeys.length}`);
  d1.kvStore.delete(chunkKeys[1]);

  const { result: restored, lines } = await withWarnings(async () => readCachePayload(env, CACHE_KEY));
  assert.equal(restored, null, 'an incomplete shard set must not be joined into a smaller corpus');
  assert.ok(lines.some((line) => line.includes('incomplete shard set')),
    `and it must say so: ${JSON.stringify(lines)}`);
});

// ── the splitter the shape depends on ────────────────────────────────────────────────────────────

test('the splitter keeps every piece under the byte limit and never cuts a character', () => {
  // CJK and an astral emoji: 3- and 4-byte characters, where `String.length` and byte length diverge,
  // and where a naive `slice` cuts a surrogate pair into two replacement characters.
  const text = JSON.stringify({ ts: 1, data: ['证据 🚨 kubectl crashloopbackoff 超时', 'ok'] }).repeat(400);
  const limit = 1_000;
  const parts = splitByUtf8Bytes(text, limit);
  assert.equal(parts.join(''), text, 'the pieces must reassemble byte-identically');
  assert.ok(parts.length > 1, 'the fixture must need more than one piece');
  for (const part of parts) {
    assert.ok(utf8Bytes(part) <= limit, `a piece is over the limit: ${utf8Bytes(part)}`);
    assert.ok(!/[\uD800-\uDBFF]$/.test(part), 'a piece must not end on a high surrogate');
    assert.ok(!/^[\uDC00-\uDFFF]/.test(part), 'a piece must not start on a low surrogate');
  }
});

test('a payload that fits keeps the single-row shape — no query cost is paid before it is needed', async () => {
  const d1 = createD1({ rows: d1Rows(12, 400) });
  const env = makeEnv(d1, createKv());
  const stored = await storePut(env, 'probe:small', JSON.stringify({ ts: Date.now(), data: [1, 2, 3] }));
  assert.equal(stored, true);
  assert.equal(d1.kvStore.has('probe:small:chunk'), false);

  await worker.fetch(lessonsRequest(), env);
  const manifest = JSON.parse(d1.kvStore.get(CACHE_KEY));
  assert.equal(manifest.sharded, undefined, `a small payload stays one row: ${JSON.stringify(manifest)}`);
  assert.ok(manifest.data, 'and it is still the {ts, data} shape every existing reader expects');
});

test('a deployment without D1 keeps one KV key — the ceiling being dodged is D1\'s', async () => {
  // KV stores 25 MiB values, so sharding here would only multiply this cache's distinct keys — the
  // budget #2115 is about — to avoid a limit the store does not have.
  const kv = createKv();
  const payload = { ts: Date.now(), data: [{ id: 'big', indexText: 'y'.repeat(2_400_000) }] };
  const stored = await storeCachePayload({ MISAKANET_KV: kv }, 'proxy:lessons', payload, {});
  assert.equal(stored.written, true);
  assert.equal(stored.sharded, false, JSON.stringify(stored));
  assert.ok(stored.bytes > D1_ROW_LIMIT_BYTES, `the fixture must be over D1's cap: ${stored.bytes}`);
  assert.deepEqual([...kv.rows.keys()], ['proxy:lessons'], 'one key, as before');
});
