// The corpus read is the row budget: one search without a cache hit reads 516 rows, and the site
// serves ~9.4k calls a day. Measured 2026-10-19 from the dashboard: 6.24M rows read against a 5M
// free-plan limit, while the durable cache is itself read *through* D1 — so a "hit" also bills rows
// and an outage re-reads the whole corpus on every request.
//
// This file pins the per-isolate memo that removes the multiplication: within one isolate the second
// and later requests in the window touch no network at all, and the memo clears on the same seam the
// read state does.
//
// Run: node --test workers/lessons-memo.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { lastLessonsReadOf, loadLessons, resetLessonsReadState } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('lessons-memo');
const QUOTA = new Error(
  "D1_ERROR: Your account has exceeded D1's free tier daily row read limit. Upgrade to a paid plan or "
  + 'wait until tomorrow (midnight UTC) to continue.',
);
const SNAPSHOT = [
  { id: 'pip-timeout', title: 'pip install timeout', domain: 'python', status: 'published', tags: ['pip'], path: 'lessons/core/pip-timeout.md' },
  { id: 'wsl-perms', title: 'WSL permission denied', domain: 'wsl', status: 'published', tags: ['wsl'], path: 'lessons/core/wsl-perms.md' },
];

function refusingD1() {
  const refused = async () => { throw QUOTA; };
  const stmt = { bind() { return stmt; }, all: refused, run: refused, first: refused, raw: refused };
  return { prepare() { return stmt; }, exec: refused, batch: refused };
}

/** Serve the snapshot and count how many times the worker went to the network for it. */
function countingFetch() {
  const state = { calls: 0 };
  const real = globalThis.fetch;
  globalThis.fetch = async (url) => {
    assert.match(String(url), /lessons-lite\.json/, 'the fallback reads the lite snapshot');
    state.calls += 1;
    return { ok: true, status: 200, json: async () => SNAPSHOT };
  };
  state.restore = () => { globalThis.fetch = real; };
  return state;
}

// The memo is off unless the deployment turns it on (see the worker's `lessonsMemoTtlMs`), so a
// test states the window it is exercising instead of inheriting a hidden default.
const env = () => ({ MISAKANET_D1: refusingD1(), REGISTER_TOKEN: TOKEN, MISAKANET_LESSONS_MEMO_MS: '30000' });

test('two reads inside the window cost one network read, and the second says it was a memo', async () => {
  const fetch = countingFetch();
  try {
    resetLessonsReadState();
    const first = await loadLessons(env());
    const afterFirst = fetch.calls;
    assert.ok(afterFirst >= 1, 'the first read must actually load the corpus');

    const second = await loadLessons(env());
    assert.equal(fetch.calls, afterFirst, 'the second read must not go to the network');
    assert.deepEqual(second.map((l) => l.id), first.map((l) => l.id));
    assert.equal(lastLessonsReadOf().source, 'memo',
      'the health payload must say the answer came from the isolate memo, not from D1');
  } finally {
    fetch.restore();
    resetLessonsReadState();
  }
});

test('the memo clears on the same seam the read state does', async () => {
  const fetch = countingFetch();
  try {
    resetLessonsReadState();
    await loadLessons(env());
    const afterFirst = fetch.calls;
    resetLessonsReadState();
    await loadLessons(env());
    assert.equal(fetch.calls, afterFirst + 1, 'a reset must make the next read load again');
  } finally {
    fetch.restore();
    resetLessonsReadState();
  }
});
