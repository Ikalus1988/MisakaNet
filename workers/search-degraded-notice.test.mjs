// "No lesson matched" must not be printed while the corpus or the index is degraded.
//
// Measured 2026-10-18: two lessons merged into `main` were invisible to `misakanet_search` — and
// the caller was told "this is a knowledge gap, file an intake" — because the BM25 index is
// rebuilt from D1 and D1's daily row-read quota was spent. The product's most confident sentence
// was printed while the corpus was frozen.
//
// The response now carries `degraded: true` + `degraded_reasons` + `notice`. This file pins the
// three states, and it asserts against the same function the answer is assembled from, so the
// sentences cannot drift away from the code the callers actually read.
//
// Run: node --test workers/search-degraded-notice.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { loadLessons, lastLessonsReadOf, resetLessonsReadState, searchDegraded } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('degraded');
const QUOTA = new Error(
  "D1_ERROR: Your account has exceeded D1's free tier daily row read limit. Upgrade to a paid plan or "
  + 'wait until tomorrow (midnight UTC) to continue.',
);
const SNAPSHOT = [
  { id: 'pip-timeout', title: 'pip install timeout', domain: 'python', status: 'published', tags: ['pip'], path: 'lessons/core/pip-timeout.md' },
];

function refusingD1() {
  const refused = async () => { throw QUOTA; };
  const stmt = { bind() { return stmt; }, all: refused, run: refused, first: refused, raw: refused };
  return { prepare() { return stmt; }, exec: refused, batch: refused };
}

function withSnapshotFetch(fn) {
  const real = globalThis.fetch;
  globalThis.fetch = async (url) => {
    assert.match(String(url), /docs\/data\/lessons-lite\.json/, 'the fallback reads the snapshot');
    return { ok: true, status: 200, json: async () => SNAPSHOT };
  };
  return fn().finally(() => { globalThis.fetch = real; });
}

test('a healthy answer is not labelled degraded', () => {
  resetLessonsReadState();
  assert.deepEqual(searchDegraded('worker-bm25'), { degraded: false });
});

test('a missing index says the naive matcher answered, in its own reason', () => {
  resetLessonsReadState();
  const out = searchDegraded('worker-search');
  assert.equal(out.degraded, true);
  assert.deepEqual(out.degraded_reasons, ['index_unavailable']);
  assert.match(out.notice, /simpler matcher/);
  // The corpus reason must not be asserted by this case: nothing failed a read here, and a notice
  // that mentions the snapshot anyway would teach callers to ignore it.
  assert.doesNotMatch(out.notice, /snapshot copy/);
});

test('a quota-refused store marks the corpus as a snapshot, and says a miss is not proof', () =>
  withSnapshotFetch(async () => {
    resetLessonsReadState();
    await loadLessons({ MISAKANET_D1: refusingD1(), REGISTER_TOKEN: TOKEN });
    assert.equal(lastLessonsReadOf().ok, false, 'the read must have been recorded as failed');

    const out = searchDegraded('worker-bm25');
    assert.equal(out.degraded, true);
    assert.deepEqual(out.degraded_reasons, ['corpus_snapshot']);
    assert.match(out.notice, /not proof that no lesson exists/,
      'the sentence that matters: a degraded read is not an empty corpus');
  }));

test('both degradations can be true at once and are both reported', () =>
  withSnapshotFetch(async () => {
    resetLessonsReadState();
    await loadLessons({ MISAKANET_D1: refusingD1(), REGISTER_TOKEN: TOKEN });
    const out = searchDegraded('worker-search');
    assert.deepEqual(out.degraded_reasons, ['index_unavailable', 'corpus_snapshot']);
    assert.match(out.notice, /simpler matcher/);
    assert.match(out.notice, /snapshot copy/);
  }));

test('a stale verdict does not leak into a healthy isolate', () => {
  resetLessonsReadState();
  assert.deepEqual(searchDegraded('worker-bm25'), { degraded: false },
    'the state is per-isolate and must reset — a degradation that never clears is its own lie');
});
