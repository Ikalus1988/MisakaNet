// The site's search read has a ceiling, and says so when it hits it (2026-11-17).
//
// `/api/lessons?q=` fires once per keystroke from `docs/search/index.html` and reads the whole corpus.
// Measured on the zone 2026-11-14..17: 200 -> 238, **499 -> 321** (the browser gave up first),
// 204 -> 213, **504 -> 924**. A 504 is the worst of those: the page gets no rows and no reason.
//
// The tests pin the contract the page depends on — over the budget the answer is `source: "timeout"`
// with a 503, not a bare HTML error and not an empty result set that reads like "no matches".
//
// Run: node --test workers/lessons-read-budget.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, { readLessonsWithinBudget, resetLessonsReadState } from './register-proxy-sw.js';

/** A D1 whose read never settles — the shape a 6-second corpus read has from the request's side. */
function hangingD1() {
  const stmt = {
    bind() { return stmt; },
    all() { return new Promise(() => {}); },
    first() { return new Promise(() => {}); },
    run() { return new Promise(() => {}); },
  };
  return { prepare() { return stmt; }, async batch() { return []; }, async exec() { return { count: 0 }; } };
}

const ROWS = [{ id: 'a', title: 'A', domain: 'python', tags: ['x'], status: 'published', summary: 's' }];

function kvWith(rows) {
  return {
    async get(key, type) {
      if (key !== 'corpus:v1' || !rows) return null;
      const payload = { ts: Date.now(), rows };
      return type === 'json' ? payload : JSON.stringify(payload);
    },
    async put() {},
  };
}

test.beforeEach(() => resetLessonsReadState());

test('a slow corpus read is abandoned at the budget', async () => {
  const started = Date.now();
  const outcome = await readLessonsWithinBudget(
    { REGISTER_TOKEN: 'x', MISAKANET_D1: hangingD1() }, 60);
  const elapsed = Date.now() - started;
  assert.equal(outcome.timedOut, true);
  assert.equal(outcome.rows, null);
  assert.ok(elapsed < 2000, `the budget must be the thing that ends the wait, took ${elapsed}ms`);
});

test('a fast corpus read is returned untouched', async () => {
  const outcome = await readLessonsWithinBudget({ MISAKANET_KV: kvWith(ROWS) }, 60);
  assert.equal(outcome.timedOut, false);
  assert.deepEqual(outcome.rows.map((r) => r.id), ['a']);
});

test('over the budget, /api/lessons?q= answers 503 with source "timeout" rather than nothing', async () => {
  const env = { REGISTER_TOKEN: 'x', MCP_TOKEN: 'x', MISAKANET_D1: hangingD1() };
  const response = await Promise.race([
    worker.fetch(new Request('https://misakanet.org/api/lessons?q=pip'), env),
    new Promise((_, reject) => setTimeout(() => reject(new Error('the route did not answer within 20s')), 20000)),
  ]);
  assert.equal(response.status, 503);
  const body = await response.json();
  assert.equal(body.source, 'timeout', JSON.stringify(body));
  assert.deepEqual(body.results, []);
  assert.match(body.hint, /retry/i);
});
