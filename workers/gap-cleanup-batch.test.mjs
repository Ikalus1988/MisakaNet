// Gap cleanup: the covered-gap deletes go out as `d1.batch()`, not one `await …run()` per gap.
//
// Why this file exists: `cleanupCoveredGaps` read up to 500 gap rows and then deleted the covered
// ones **serially** — one D1 round trip per row, i.e. up to 500 subrequests and 500 statements inside
// a single `ctx.waitUntil()` sweep. Workers Free allows 50 subrequests per invocation, so on the free
// plan the tail of that list could not be deleted at all; the fix is one `d1.batch()` per chunk, which
// is one subrequest no matter how many rows it carries.
//
// The assertions are written against the *count* of calls, not against a magic batch size: a rewrite
// that keeps batching but changes the chunk size must still pass, and the old serial implementation
// must fail. `batchCalls === 0` is the mutation signal — put `await stmt.run()` back and the first test
// goes red while `gap-lifecycle.test.mjs` (which only checks the outcome) stays green. That pair is
// the mutation check quoted in the PR body.
//
// Run: node --test workers/gap-cleanup-batch.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { cleanupCoveredGaps } from './register-proxy-sw.js';

// One doc matching "dco sign off" through `bm25Tokenize`, and nothing matching the filler queries
// below — so "covered" and "not covered" are both reachable in one run.
const MOCK_BM25_INDEX = {
  version: 1,
  docCount: 1,
  avgDocLen: 10,
  terms: {
    dco: { idf: 1.5, docs: [{ doc: 0, tf: 2, len: 10 }] },
    signoff: { idf: 1.2, docs: [{ doc: 0, tf: 1, len: 10 }] },
    sign: { idf: 1.0, docs: [{ doc: 0, tf: 1, len: 10 }] },
    off: { idf: 0.8, docs: [{ doc: 0, tf: 1, len: 10 }] },
  },
  docs: [{ id: 'dco-signoff-force-push-pitfall', title: 'DCO Signoff Force Push Pitfall', domain: 'git', path: 'lessons/core/dco-signoff-force-push-pitfall.md' }],
};

const COVERED = 'dco sign-off';

/** D1 stand-in that answers the gap SELECT and records *how* the deletes were sent.
 *
 * `batch()` is what the old implementation never called — which is the point: a stub that omits it
 * makes the absence a `TypeError` inside the worker's own try/catch, so `state.batchCalls` stays 0 and
 * the mutation is caught rather than silently falling back to a passing serial path.
 */
function createGapD1({ rows = [], failBatch = false, failDeletes = false, failDeleteFor = () => false } = {}) {
  const state = {
    batchCalls: 0,
    batchStatements: [],   // rows sent to batch(), in order
    batchSql: [],          // the SQL each batch statement carried
    serialDeleteRuns: [],  // rows sent to .run() — must stay empty unless a batch was rejected
    serialDeleteSql: [],
    runCalls: [],          // every .run() this stub sees, DDL included
  };

  function prepared(sql) {
    const stmt = {
      _sql: sql,
      _bound: [],
      bind(...args) { stmt._bound = args; return stmt; },
      async all() {
        if (/FROM counters/i.test(sql) && /scope\s*=\s*'gap'/i.test(sql)) {
          return { results: rows.map(row => ({ bucket: row.bucket, period: row.period })) };
        }
        // kv_store: always empty, so `storeGet` falls through to the KV binding (which serves the
        // BM25 index). That keeps the index read out of this stub's statement bookkeeping.
        return { results: [] };
      },
      async run() {
        state.runCalls.push(sql);
        if (/^\s*DELETE/i.test(sql)) {
          if (failDeletes || failDeleteFor(stmt._bound[0])) {
            throw new Error('D1_ERROR: delete unavailable');
          }
          state.serialDeleteRuns.push(stmt._bound[0]);
          state.serialDeleteSql.push(sql);
        }
        return { success: true };
      },
    };
    return stmt;
  }

  return {
    state,
    prepare: prepared,
    async batch(statements) {
      state.batchCalls += 1;
      if (!Array.isArray(statements) || statements.length === 0) {
        throw new Error('d1.batch() called with no statements');
      }
      if (failBatch) throw new Error('D1_ERROR: batch rejected');
      for (const stmt of statements) {
        state.batchStatements.push(stmt._bound[0]);
        state.batchSql.push(stmt._sql);
      }
      return statements.map(() => ({ success: true, results: [] }));
    },
    /** Every DELETE that reached the database, whichever way it was sent. */
    deletesSent() {
      return [...state.batchStatements, ...state.serialDeleteRuns];
    },
  };
}

function createEnv(d1) {
  return {
    MISAKANET_D1: d1,
    MISAKANET_KV: {
      async get(key, opts) {
        if (key !== 'worker_search_index') return null;
        return (typeof opts === 'string' ? opts : opts?.type) === 'json'
          ? MOCK_BM25_INDEX
          : JSON.stringify(MOCK_BM25_INDEX);
      },
      async put() {},
      async delete() {},
    },
  };
}

/** N rows whose bucket is exactly COVERED's, plus 3 unmatched rows for every other query. */
function gapRows(matchedCount) {
  return [
    ...Array.from({ length: matchedCount }, () => ({ bucket: COVERED, period: '2026-10-01' })),
    ...Array.from({ length: 3 }, (_, i) => ({ bucket: `zzz-unrelated-topic-${i}`, period: '2026-10-01' })),
  ];
}

test('one batch call carries every covered gap — not one .run() per gap', async () => {
  const d1 = createGapD1({ rows: gapRows(3) });
  const result = await cleanupCoveredGaps(createEnv(d1));

  assert.equal(result.cleaned, 3);
  assert.deepEqual(d1.state.batchStatements.map(String).sort(), [COVERED, COVERED, COVERED].sort());
  assert.equal(d1.deletesSent().length, 3, 'exactly the covered rows, no more');
  assert.equal(d1.state.serialDeleteRuns.length, 0,
    'no DELETE may go out through .run() — that is the per-gap round trip this change removes');

  // The mutation guard: with `await …run()` restored this is 0 and the test fails here.
  assert.equal(d1.state.batchCalls, 1, 'three covered gaps must cost exactly one batch call');
  assert.equal(d1.state.batchStatements.length, 3, 'the batch must carry all three statements');
});

test('cost does not grow with the row count: 3 rows is 1 call, 120 rows is still single digits', async () => {
  // Same implementation, same module, one order of magnitude more covered rows. The point is the
  // *shape*: batch calls are ceil(N / chunkSize), never N.
  const small = createGapD1({ rows: gapRows(3) });
  await cleanupCoveredGaps(createEnv(small));

  const big = createGapD1({ rows: gapRows(120) });
  const result = await cleanupCoveredGaps(createEnv(big));

  assert.equal(result.cleaned, 120);
  assert.equal(big.deletesSent().length, 120, 'every covered row still gets its own statement');
  assert.equal(big.state.serialDeleteRuns.length, 0, 'still no per-gap .run()');

  const expectedChunks = Math.ceil(120 / 50);
  assert.equal(big.state.batchCalls, expectedChunks,
    `120 rows must be ${expectedChunks} batch calls (one per 50-row chunk), not 120`);
  assert.ok(big.state.batchCalls < 120,
    `batching must beat serial: ${big.state.batchCalls} calls for 120 rows`);
});

test('a full 500-row sweep stays inside the free plan subrequest budget', async () => {
  // 500 is the read's own `LIMIT`, so this is the worst case one sweep can reach: with the DELETE
  // backlog the old code spent up to 500 subrequests here, and Workers Free allows 50 per invocation —
  // the SELECT, the BM25 index read and the counter writes have to fit in the same 50. Ten is the
  // ceiling this test pins, which leaves the rest of the budget untouched.
  const d1 = createGapD1({ rows: gapRows(500) });
  const result = await cleanupCoveredGaps(createEnv(d1));

  assert.equal(result.cleaned, 500);
  assert.equal(d1.deletesSent().length, 500, 'the backlog is fully drained, not truncated');
  assert.equal(d1.state.serialDeleteRuns.length, 0);
  assert.ok(d1.state.batchCalls <= 10,
    `a 500-row sweep cost ${d1.state.batchCalls} batch subrequests; the free plan allows 50 per invocation`);
});

test('the batch carries only rows a lesson covers, and only in the gap scope', async () => {
  const d1 = createGapD1({ rows: gapRows(2) });
  const result = await cleanupCoveredGaps(createEnv(d1));

  assert.equal(result.cleaned, 2);
  for (const query of d1.deletesSent()) {
    assert.equal(query, COVERED, `deleted a row that no lesson covers: ${query}`);
  }
  // Every DELETE — batched or not — must keep the literal scope filter. A statement of the shape
  // `DELETE FROM counters WHERE bucket = ?1` would take out a rate or traffic bucket of the same name.
  assert.ok(d1.state.batchSql.length >= 1);
  for (const sql of [...d1.state.batchSql, ...d1.state.serialDeleteSql]) {
    assert.match(sql, /scope\s*=\s*'gap'/i, `DELETE without the gap scope guard: ${sql}`);
  }
});

test('a rejected batch falls back to per-row deletes and still reports the truth', async () => {
  // A batch is a transaction: if it throws, none of its rows were deleted. The fallback is the old
  // behaviour, applied only where the old behaviour is needed.
  const d1 = createGapD1({ rows: gapRows(3), failBatch: true });
  const result = await cleanupCoveredGaps(createEnv(d1));

  assert.equal(d1.state.batchCalls, 1, 'the batch is still attempted once');
  assert.equal(d1.state.serialDeleteRuns.length, 3, 'the whole chunk is retried row by row');
  assert.equal(result.cleaned, 3);
  assert.deepEqual(result.details.map(entry => entry.query), [COVERED, COVERED, COVERED]);
});

test('a failed delete is not reported as cleaned', async () => {
  const d1 = createGapD1({ rows: gapRows(2), failBatch: true, failDeletes: true });
  const result = await cleanupCoveredGaps(createEnv(d1));

  assert.equal(result.cleaned, 0, 'rows still in counters must not be counted as cleaned');
  assert.deepEqual(result.details, []);
});

test('the fallback reports only the rows it actually deleted', async () => {
  // The interesting middle case: the batch is rejected, most rows then delete one by one, and one row
  // stays behind. `details` must name the two that committed — not all three attempted.
  let seen = 0;
  const d1 = createGapD1({
    rows: gapRows(3),
    failBatch: true,
    failDeleteFor: () => { seen += 1; return seen === 2; },
  });
  const result = await cleanupCoveredGaps(createEnv(d1));

  assert.equal(result.cleaned, 2);
  assert.equal(result.details.length, 2);
  assert.deepEqual(result.details.map(entry => entry.query), [COVERED, COVERED]);
  assert.equal(d1.state.serialDeleteRuns.length, 2, 'only the committed deletes are recorded');
  assert.ok(result.details.every(entry => typeof entry.matchedLesson === 'string'),
    'a reported gap still carries the lesson that covered it');
});
