// A D1 *quota* refusal must degrade to the snapshot, not take search down (2026-10-17).
//
// Measured: `/api/lessons` answered HTTP 502, `/api/lessons?domain=python` answered 502, and every
// `misakanet_search` returned the D1_ERROR text to the caller while `/api/health` said `status: ok` and
// the data-branch snapshot held the same 500 lessons. The rows-read budget is a daily quota, so it is
// not a fault the caller can retry around — the only correct behaviour is to serve the corpus from
// somewhere else.
//
// Run: node --test workers/lessons-fallback.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { filterSnapshot, loadLessons } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

// Synthetic token (workers/_test-token.mjs explains why this is never a literal).
const TOKEN = testToken('lessons-fallback');

const QUOTA = new Error(
  "D1_ERROR: Your account has exceeded D1's free tier daily row read limit. Upgrade to a paid plan or "
  + 'wait until tomorrow (midnight UTC) to continue.',
);

const SNAPSHOT = [
  { id: 'pip-timeout', title: 'pip install timeout', domain: 'python', status: 'published', tags: ['pip'], path: 'lessons/core/pip-timeout.md' },
  { id: 'wsl-perms', title: 'WSL permission denied', domain: 'wsl', status: 'published', tags: ['wsl'], path: 'lessons/core/wsl-perms.md' },
  { id: 'draft-one', title: 'a draft', domain: 'python', status: 'draft', tags: ['pip'], path: 'lessons/core/draft-one.md' },
];

/** A D1 binding whose every statement fails the way an exhausted quota fails. */
function refusingD1() {
  const refused = async () => { throw QUOTA; };
  const stmt = { bind() { return stmt; }, all: refused, run: refused, first: refused, raw: refused };
  return { prepare() { return stmt; }, exec: refused, batch: refused };
}

/** Serve the snapshot through the GitHub contents API, the way the worker reads it. */
function withSnapshotFetch(fn) {
  const real = globalThis.fetch;
  globalThis.fetch = async (url) => {
    assert.match(String(url), /contents\/lessons\.json/, 'only the snapshot may be fetched here');
    return {
      ok: true,
      status: 200,
      json: async () => ({ content: Buffer.from(JSON.stringify(SNAPSHOT)).toString('base64'), encoding: 'base64' }),
    };
  };
  return fn().finally(() => { globalThis.fetch = real; });
}

test('an unfiltered read falls back to the snapshot when D1 refuses', () =>
  withSnapshotFetch(async () => {
    const lessons = await loadLessons({ MISAKANET_D1: refusingD1(), REGISTER_TOKEN: TOKEN });
    assert.deepEqual(lessons.map((l) => l.id), ['pip-timeout', 'wsl-perms', 'draft-one']);
  }));

test('a filtered read filters the snapshot instead of answering 502', () =>
  withSnapshotFetch(async () => {
    const lessons = await loadLessons({ MISAKANET_D1: refusingD1(), REGISTER_TOKEN: TOKEN },
      { domain: 'python' });
    assert.deepEqual(lessons.map((l) => l.id), ['pip-timeout', 'draft-one']);
  }));

test('filterSnapshot applies the same predicates the SQL built', () => {
  assert.deepEqual(filterSnapshot(SNAPSHOT, { domain: 'PYTHON' }).map((l) => l.id), ['pip-timeout', 'draft-one']);
  assert.deepEqual(filterSnapshot(SNAPSHOT, { status: 'published' }).map((l) => l.id), ['pip-timeout', 'wsl-perms']);
  assert.deepEqual(filterSnapshot(SNAPSHOT, { tag: 'wsl' }).map((l) => l.id), ['wsl-perms']);
  assert.deepEqual(filterSnapshot(SNAPSHOT, { id: 'draft-one' }).map((l) => l.id), ['draft-one']);
  assert.equal(filterSnapshot(SNAPSHOT, { limit: 1 }).length, 1);
});
