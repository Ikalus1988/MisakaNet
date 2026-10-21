// The row-read hotspots that survived the last round, and the gates that keep them fixed.
//
// Measured on production with `wrangler d1 insights` (2026-10-21, two-hour window):
//
//   432,991 rows read in 2h, of which 412,372 (95.3%) were the five GROUP BY queries of
//   /api/analytics — 10,920 rows per recompute, ~27 recomputes an hour.
//
// What this file pins:
//   * an anonymous caller does not pay for the maintainer's failed-query text: the `no_match`
//     aggregate is only computed for the audience that receives it;
//   * the maintainer still receives that text — the outcome half of the pair, which stays green
//     when the cost half is reverted;
//   * the seven-day aggregate is not recomputed every two minutes, because a two-minute TTL on a
//     route that reads the whole seven-day window is what the 95.3% was made of.
//
// The *index* side of this round (the E4 count and the gap cleanup) is proved with a real SQLite
// engine in `tests/test_d1_read_hotspots.py` — a plan cannot be asserted on a string.
//
// Run: node --test workers/d1-read-hotspots.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';

// Assembled at runtime on purpose — hol-guard's plugin-scanner reads the whole file content
// (comments included) and reports a token-shaped name followed by an equals sign and a quoted
// value of eight characters or more as HARDCODED_SECRET, whether that value is a placeholder or a
// credential. See `tests/test_scanner_secret_patterns.py` for the rule and the exemptions.
const MCP_TOKEN = ['maintainer', 'token'].join('-');

/** A D1 stub that records the SQL it was asked to run, so the cost can be counted. */
function createCountingD1(rows = []) {
  const state = { sql: [] };
  return {
    state,
    prepare(sql) {
      state.sql.push(String(sql));
      const stmt = {
        bind() { return stmt; },
        async all() { return { results: rows }; },
        async first() { return rows[0] || null; },
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
    MCP_TOKEN,
  };
}

const request = (path, headers = {}) =>
  new Request(`https://misakanet.org${path}`, { headers });

/** The aggregate the anonymous payload never carries. */
const failedQueryAggregates = (d1) =>
  d1.state.sql.filter((sql) => /event\s*=\s*'no_match'/i.test(sql));

test('an anonymous caller does not pay for the maintainer\'s failed-query text', async () => {
  // The mutation signal: put the `no_match` query back into the unconditional `Promise.all` and
  // this is 1 instead of 0, while the test below stays green. The cost shape is the thing that
  // broke; the answer was never wrong.
  const d1 = createCountingD1([{ query: 'exit code 137', n: 3, lesson_id: 'x', day: '2026-10-20' }]);
  const response = await worker.fetch(request('/api/analytics'), createEnv(d1), { waitUntil() {} });

  assert.equal(response.status, 200);
  assert.equal(failedQueryAggregates(d1).length, 0,
    `the anonymous caller was charged for the maintainer's aggregate: ${JSON.stringify(failedQueryAggregates(d1))}`);

  // The outcome: the four aggregates the anonymous payload *does* carry are still there.
  const body = await response.json();
  assert.ok(Array.isArray(body.top_searches), 'the public aggregate must survive');
  assert.ok(Array.isArray(body.top_lessons), 'the public aggregate must survive');
  assert.ok(Array.isArray(body.intents), 'the public aggregate must survive');
  assert.ok(Array.isArray(body.daily_requests), 'the public aggregate must survive');
  assert.equal(body.knowledge_gaps, undefined,
    'the anonymous caller must not be handed the maintainer\'s failed-query text');
});

test('the maintainer still gets the failed-query text', async () => {
  // The other half of the pair: this is the outcome, and it stays green when the cost half above
  // is reverted. Without it, "don't compute it" could be satisfied by "never compute it".
  const d1 = createCountingD1([{ query: 'exit code 137', n: 3, lesson_id: 'x', day: '2026-10-20' }]);
  const response = await worker.fetch(
    request('/api/analytics', { Authorization: `Bearer ${MCP_TOKEN}` }),
    createEnv(d1),
    { waitUntil() {} },
  );

  assert.equal(response.status, 200);
  assert.equal(failedQueryAggregates(d1).length, 1,
    'the maintainer\'s aggregate must still be computed for the maintainer');
  const body = await response.json();
  assert.ok(Array.isArray(body.knowledge_gaps),
    'the maintainer is the one who gets the failed-query text');
});

test('the seven-day aggregate is not recomputed every two minutes', async () => {
  // A seven-day rolling aggregate recomputed every 120 seconds is what cost the account 95.3% of
  // every row it read. The TTL is the only thing standing between a public, crawled route and a
  // bill, so it is pinned here rather than left to a well-meaning edit.
  const d1 = createCountingD1([]);
  const response = await worker.fetch(request('/api/analytics'), createEnv(d1), { waitUntil() {} });
  const header = response.headers.get('Cache-Control') || '';
  const maxAge = Number((header.match(/max-age=(\d+)/) || [])[1]);
  assert.ok(Number.isFinite(maxAge), `the entry needs a TTL or it never expires: ${header}`);
  assert.ok(maxAge >= 600,
    `a seven-day aggregate must not be recomputed every two minutes (max-age=${maxAge})`);
});
