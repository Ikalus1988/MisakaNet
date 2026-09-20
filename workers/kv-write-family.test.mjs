// Which key family spends the free tier's KV write allowance (2026-09-20, #1890).
//
// The quota counts *distinct keys written per day* (1,000 on the free plan), not write operations, which
// is why an earlier attempt to pick the next migration target went wrong: it ranked families by how many
// keys exist in the namespace and named `node:`, `mcp_token:` and `client:` — three families that already
// write through `storePut` (D1 first, KV only as a fallback) and therefore cost the KV budget nothing.
// Measure, then move.
//
// These tests pin the measurement itself: the family mapping (the bucket becomes a D1 row key, so the set
// is bounded on purpose), the "distinct key once per isolate" rule (rewrites of the same key are free, and
// the quota charges in the same shape), and that the counter never routes through `kvPut` — its own KV
// fallback sits one call away and would recurse the moment D1 was unhappy.
//
// Run: node --test workers/kv-write-family.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, { kvKeyFamily } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('kv-family');
const LESSONS = [
  { id: 'pip-timeout-mirror', title: 'pip install timeout', domain: 'python', tags: ['pip'],
    path: 'lessons/core/pip-timeout-mirror.md', summary: 'pip install times out' },
];

/** Minimal D1 stand-in that records counters upserts and fails KV writes. */
function createCountersD1({ fail = false } = {}) {
  const counters = new Map();
  return {
    counters,
    prepare(sql) {
      const stmt = {
        _bound: [],
        bind(...args) { stmt._bound = args; return stmt; },
        async all() {
          if (fail) throw new Error('D1_ERROR: no such table: counters');
          if (/SELECT bucket, count FROM counters/i.test(sql)) {
            const [period] = stmt._bound;
            return { results: [...counters.entries()]
              .filter(([key]) => key.endsWith(`|${period}`))
              .map(([key, count]) => ({ bucket: key.split('|')[0], count })) };
          }
          return { results: [] };
        },
        async run() {
          if (fail) throw new Error('D1_ERROR: no such table: counters');
          if (/INSERT INTO counters/i.test(sql)) {
            // The kvwrite upsert binds only (bucket, period) — `scope` is a literal in the SQL — so
            // destructuring three values here silently keyed every row on `undefined`, which is how the
            // first version of this mock made the counter look broken.
            const [bucket, period] = stmt._bound;
            const key = `${bucket}|${period}`;
            counters.set(key, (counters.get(key) || 0) + 1);
            return { success: true };
          }
          return { success: true };
        },
      };
      return stmt;
    },
  };
}

function createEnv({ d1 = null } = {}) {
  const store = new Map([['proxy:lessons', JSON.stringify({ ts: Date.now(), data: LESSONS })]]);
  const env = {
    MCP_TOKEN: TOKEN,
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) {
        // Every KV write fails: the day's allowance is gone, which is the state this measurement has to
        // keep working in.
        throw new Error('KV PUT failed: 429 [code: 10048]');
      },
      async delete(key) { store.delete(key); },
    },
  };
  if (d1) env.MISAKANET_D1 = d1;
  return env;
}

/**
 * A useful vote: `POST /api/helpful` writes `helpful:<lesson_id>` through `kvPut` unconditionally — one
 * KV key per lesson, which is exactly the "per entity, KV first" shape this measurement exists to rank.
 *
 * (A search miss would *not* do: `logSearchGap` short-circuits to `bumpCounter` whenever D1 is bound, so
 * with D1 present it creates no KV key at all. That is also why the first version of this test failed —
 * and a useful reminder that "the family looks KV-heavy" is a claim to measure, not to infer.)
 */
const vote = (env, lessonId) => worker.fetch(new Request('https://misakanet.org/api/helpful', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ lesson_id: lessonId }),
}), env);

// The counter is fire-and-forget by design (measurement must not add a round trip to a write path), so a
// test has to let the microtask queue drain before it looks.
const settle = () => new Promise((resolve) => setTimeout(resolve, 10));

const totalFor = (d1, family) => [...d1.counters.entries()]
  .filter(([key]) => key.startsWith(`${family}|`))
  .reduce((sum, [, count]) => sum + count, 0);

test('the family is the key prefix, and unknown prefixes stay bounded', () => {
  assert.equal(kvKeyFamily('gap:abc123'), 'gap');
  assert.equal(kvKeyFamily('rate:read:203.0.113.7:burst-2026-09-20T09-00'), 'rate');
  assert.equal(kvKeyFamily('client:8f14e45f-2b1c'), 'client');
  assert.equal(kvKeyFamily('mcp_token:abcdef'), 'mcp_token');
  // Everything unrecognised collapses into one bucket: a family name becomes a D1 row key, so an
  // unbounded set of them would trade a KV problem for a D1 one.
  assert.equal(kvKeyFamily('some-new-family:whatever'), 'other');
  assert.equal(kvKeyFamily('node_counter'), 'bare');
  assert.equal(kvKeyFamily(''), 'bare');
});

test('a failing KV write still attributes its key family', async () => {
  const d1 = createCountersD1();
  const env = createEnv({ d1 });
  await vote(env, 'pip-timeout-mirror');
  await settle();
  assert.ok(totalFor(d1, 'helpful') >= 1,
    'the family must be counted even though the write failed - an outage is when the ranking matters most');
});

test('the same key is counted once, because the quota charges per distinct key', async () => {
  const d1 = createCountersD1();
  const env = createEnv({ d1 });
  await vote(env, 'pip-timeout-mirror');
  await settle();
  const after = totalFor(d1, 'helpful');
  await vote(env, 'pip-timeout-mirror');
  await settle();
  assert.equal(totalFor(d1, 'helpful'), after,
    'a rewrite of the same key is free on the free tier, and must be free here too');

  // ...but a different key in the same family is a new unit of the budget, and must show up.
  await vote(env, 'wsl-terminal-underscore-corruption');
  await settle();
  assert.equal(totalFor(d1, 'helpful'), after + 1, 'a second distinct key is a second charge');
});

test('a broken counters table never breaks the request', async () => {
  const env = createEnv({ d1: createCountersD1({ fail: true }) });
  const response = await vote(env, 'pip-timeout-mirror');
  assert.equal(response.status, 200, 'measurement is not allowed to take the search path down');
});

test('the ranking is exposed on /api/health', async () => {
  const d1 = createCountersD1();
  const env = createEnv({ d1 });
  // A lesson id this file has not voted with before: the dedupe set lives in the worker module, so every
  // test in one process shares one "isolate" (exactly as production isolates do, and the reason a family
  // can only be counted once per isolate).
  await vote(env, 'health-payload-probe');
  await settle();
  const body = await (await worker.fetch(new Request('https://misakanet.org/api/health'), env)).json();
  assert.ok(body.kv_writes.families, 'the payload must carry the day\'s families');
  assert.ok(Object.keys(body.kv_writes.families).includes('helpful'),
    JSON.stringify(body.kv_writes.families));
});

test('without D1 the ranking is absent rather than wrong', async () => {
  const env = createEnv({ d1: null });
  const body = await (await worker.fetch(new Request('https://misakanet.org/api/health'), env)).json();
  assert.equal(body.kv_writes.families, null);
});
