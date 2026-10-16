// `POST /api/helpful` gained an optional constant `source` field (2026-10-16).
//
// Why it exists. Before it, the handler read `{lesson_id}` and nothing else, so a helpful vote cast from
// the DSH panel was byte-identical to one cast by `curl`. The panel therefore shipped a feature whose
// outcome could not be measured at all — the one number it moved was the same number every other caller
// moved. The fix is a **surface label**, not an identity: a constant string, the same for every person and
// every session, with no account, no client_id, no cookie and no per-session value anywhere near it.
//
// What these tests pin:
//   * `count` — the number `GET /api/helpful` and `misakanet_me_events` read — is unchanged in every case;
//   * a vote with a source writes the extra counter through the same `bumpCounter` shape `traffic:` and
//     `gap:` already use, bucketed by UTC day, so "how many panel votes, and when" is answerable later;
//   * an absent (or unusable) source writes no extra counter at all, so the pre-change behaviour is exact.
//
// Run: node --test workers/helpful-source.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('helpful-source');

/**
 * A D1 stand-in for the two tables these paths touch.
 *
 * `counters` records `bumpCounter` upserts (the per-source row), and `kv_store` answers the durable
 * store, because with a D1 binding `storeGet`/`storePut` read *there* and only fall back to KV — a mock
 * that ignored `kv_store` would silently test the fallback instead of the deployed path.
 */
function createCountersD1({ fail = false } = {}) {
  const counters = new Map();
  const kvStore = new Map();
  function handle(sql, bound) {
    if (/CREATE TABLE/i.test(sql)) return { success: true, results: [] };
    if (/INSERT INTO counters/i.test(sql)) {
      const [scope, bucket, period, delta] = bound;
      const key = `${scope}|${bucket}|${period}`;
      counters.set(key, (counters.get(key) || 0) + Number(delta));
      return { results: [{ count: counters.get(key) }] };
    }
    if (/INSERT INTO kv_store/i.test(sql)) {
      const [key, value] = bound;
      kvStore.set(String(key), String(value));
      return { success: true, results: [] };
    }
    if (/SELECT value FROM kv_store/i.test(sql)) {
      const raw = kvStore.get(String(bound[0]));
      return { results: raw === undefined ? [] : [{ value: raw }] };
    }
    return { success: true, results: [] };
  }
  return {
    counters,
    kvStore,
    prepare(sql) {
      const stmt = {
        _bound: [],
        bind(...args) { stmt._bound = args; return stmt; },
        async all() {
          if (fail) throw new Error('D1_ERROR: no such table');
          return handle(sql, stmt._bound);
        },
        async run() {
          if (fail) throw new Error('D1_ERROR: no such table');
          return handle(sql, stmt._bound);
        },
      };
      return stmt;
    },
  };
}

/** The KV fallback, as a plain Map; a D1 error routes here. */
function createEnv({ d1 = null } = {}) {
  const kv = new Map();
  const env = {
    MCP_TOKEN: TOKEN,
    MISAKANET_KV: {
      async get(key, type) {
        if (!kv.has(key)) return null;
        const raw = kv.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) { kv.set(String(key), String(value)); },
      async delete(key) { kv.delete(key); },
      _store: kv,
    },
  };
  if (d1) env.MISAKANET_D1 = d1;
  return env;
}

const vote = (env, body) => worker.fetch(new Request('https://misakanet.org/api/helpful', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
}), env);

const countOf = (env, lessonId) => worker.fetch(
  new Request(`https://misakanet.org/api/helpful?lesson_id=${lessonId}`), env);

test('a vote with a source still answers the same count and keeps `helpful:<id>` intact', async () => {
  const d1 = createCountersD1();
  const env = createEnv({ d1 });
  const first = await vote(env, { lesson_id: 'pip-timeout', source: 'dsh-web' });
  assert.equal(first.status, 200);
  assert.deepEqual(await first.json(), { lesson_id: 'pip-timeout', count: 1 },
    'adding `source` must not change the response body the client reads');
  assert.equal(d1.kvStore.get('helpful:pip-timeout'), '1',
    'the lesson counter is still the store key every reader uses');
  const second = await vote(env, { lesson_id: 'pip-timeout', source: 'dsh-web' });
  assert.deepEqual(await second.json(), { lesson_id: 'pip-timeout', count: 2 });
  const read = await countOf(env, 'pip-timeout');
  assert.deepEqual(await read.json(), { lesson_id: 'pip-timeout', count: 2 },
    'GET /api/helpful is unchanged and sees both votes');
});

test('votes are counted per source and per UTC day', async () => {
  const d1 = createCountersD1();
  const env = createEnv({ d1 });
  await vote(env, { lesson_id: 'a-lesson', source: 'dsh-web' });
  await vote(env, { lesson_id: 'b-lesson', source: 'dsh-web' });
  await vote(env, { lesson_id: 'a-lesson', source: 'site' });
  const day = new Date().toISOString().slice(0, 10);
  assert.equal(d1.counters.get(`helpful-source|dsh-web|${day}`), 2,
    'two panel votes on two lessons are two panel votes');
  assert.equal(d1.counters.get(`helpful-source|site|${day}`), 1,
    'and another surface is counted separately, not folded in');
  // The lesson counters are untouched by the source bookkeeping.
  assert.equal(d1.kvStore.get('helpful:a-lesson'), '2');
  assert.equal(d1.kvStore.get('helpful:b-lesson'), '1');
});

test('an absent source behaves exactly as before: no source row at all', async () => {
  const d1 = createCountersD1();
  const env = createEnv({ d1 });
  const resp = await vote(env, { lesson_id: 'curl-lesson' });
  assert.deepEqual(await resp.json(), { lesson_id: 'curl-lesson', count: 1 });
  assert.equal(d1.kvStore.get('helpful:curl-lesson'), '1');
  assert.equal(d1.counters.size, 0,
    'a caller that sends no source must not appear in the per-source counters at all');
});

test('an unusable source degrades to "no source" rather than inventing one', async () => {
  const d1 = createCountersD1();
  const env = createEnv({ d1 });
  const blank = await vote(env, { lesson_id: 'a-lesson', source: '  ' });
  assert.equal(blank.status, 200, 'a blank source is not the voter\'s problem; the vote still counts');
  assert.deepEqual(await blank.json(), { lesson_id: 'a-lesson', count: 1 });
  assert.equal(d1.counters.size, 0, 'a blank label must not become a counter bucket');
  // `sanitizeIdentifier` is the guard every other field goes through, and it keeps the source a plain
  // word: a label that could carry the counter's own delimiter could forge a row.
  await vote(env, { lesson_id: 'a-lesson', source: 'dsh:web|2026-10-16' });
  const keys = [...d1.counters.keys()];
  assert.equal(keys.length, 1, keys.join(','));
  assert.match(keys[0], /^helpful-source\|[A-Za-z0-9_-]+\|\d{4}-\d{2}-\d{2}$/, keys[0]);
  assert.ok(!keys[0].includes('web|'), 'the delimiter in the label must not survive: ' + keys[0]);
});

test('a counter failure does not cost the vote', async () => {
  const d1 = createCountersD1({ fail: true });
  const env = createEnv({ d1 });
  const resp = await vote(env, { lesson_id: 'a-lesson', source: 'dsh-web' });
  assert.equal(resp.status, 200, 'the lesson counter is the product; the source counter is telemetry');
  assert.deepEqual(await resp.json(), { lesson_id: 'a-lesson', count: 1 });
  // With D1 unhappy both stores fall back to KV, which is the documented shape.
  assert.ok([...env.MISAKANET_KV._store.keys()].some((k) => k.startsWith('counters:helpful-source:')),
    'the fallback still records the source: ' + [...env.MISAKANET_KV._store.keys()].join(','));
  assert.equal(env.MISAKANET_KV._store.get('helpful:a-lesson'), '1',
    'and the vote itself still landed, in the same fallback');
});
