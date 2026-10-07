// The frontend shield: safeFetchLessons / buildErrorHTML / isValidLesson.
//
// Why `node:test` and not vitest: this file used to `import { describe, it, expect,
// vi } from 'vitest'`, which the root `package.json` does not depend on and
// `node_modules/vitest` does not contain, so it had never run — and because
// `pytest` only collects `test_*.py`, it was invisible to the `audit` job too. The
// same shape as `tests/dsh/`, which #2920 deleted. Rather than add a dependency
// and a lockfile regeneration for one file, this uses the runner the other 74
// worker tests and `packages/fatal-guard/tests/smoke.test.js` already use.
//
// Run: node --test tests/frontend.test.js
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  safeFetchLessons,
  buildErrorHTML,
  isValidLesson,
} from '../docs/js/core.js';

// Minimal DOM shim: the production code assigns through `errorUI`, and the test
// needs somewhere for that to land.
function setupDOM() {
  let innerHTML = '';
  const el = {
    get innerHTML() { return innerHTML; },
    set innerHTML(v) { innerHTML = String(v); },
    style: { display: '' },
    getElementById: () => el,
  };
  globalThis.document = { getElementById: () => el };
  return el;
}

// `safeFetchLessons` logs to console.error on every blocked load, which is the
// behaviour under test — so silence it for the duration rather than leaving the
// output unreadable, and put it back afterwards.
function silenceConsoleError() {
  const original = console.error;
  console.error = () => {};
  return () => { console.error = original; };
}

// A `fetch` stub returning one canned response, then restoring the real one.
function stubFetch(impl) {
  const original = globalThis.fetch;
  globalThis.fetch = impl;
  return () => { globalThis.fetch = original; };
}

test('🚨 lessons.json root is not an array → error boundary, empty result', async () => {
  const searchEl = setupDOM();
  const restoreLog = silenceConsoleError();
  const restoreFetch = stubFetch(async () => ({
    ok: true,
    json: async () => ({ last_updated: 12345, lessons: 'not-an-array' }),
  }));
  try {
    const lessons = await safeFetchLessons('./lessons.json', (msg) => {
      searchEl.innerHTML = buildErrorHTML(msg);
    });
    assert.deepEqual(lessons, []);
    assert.ok(searchEl.innerHTML.includes('Frontend Shield'));
    assert.ok(searchEl.innerHTML.includes('lessons.json'));
  } finally {
    restoreFetch();
    restoreLog();
  }
});

test('🧹 valid JSON with invalid entries → the invalid ones are filtered out', async () => {
  const restoreFetch = stubFetch(async () => ({
    ok: true,
    json: async () => [
      { id: 'v1', title: 'Good', domain: 'python' },
      { id: 'b1', title: null, domain: 't' },
      { id: 'b2', domain: 'missing-title' },
      null,
      { id: 'v2', title: 'Another', domain: 'devops' },
    ],
  }));
  try {
    const lessons = await safeFetchLessons('./lessons.json');
    assert.equal(lessons.length, 2);
    assert.equal(lessons[0].title, 'Good');
    assert.equal(lessons[1].title, 'Another');
  } finally {
    restoreFetch();
  }
});

test('🧹 isValidLesson accepts what it should and rejects what it should not', () => {
  assert.equal(isValidLesson({ title: 'a', domain: 'b' }), true);
  // An empty title still type-checks; the gate is `typeof`, not emptiness.
  assert.equal(isValidLesson({ title: '', domain: 'b' }), true);
  assert.equal(isValidLesson({ title: 'a' }), false);
  assert.ok(!isValidLesson(null));
  assert.equal(isValidLesson({}), false);
});

test('🚨 network failure → error boundary, empty result', async () => {
  const searchEl = setupDOM();
  const restoreLog = silenceConsoleError();
  const restoreFetch = stubFetch(async () => { throw new Error('Network failure'); });
  try {
    const lessons = await safeFetchLessons('./lessons.json', (msg) => {
      searchEl.innerHTML = buildErrorHTML(msg);
    });
    assert.deepEqual(lessons, []);
    assert.ok(searchEl.innerHTML.includes('Frontend Shield'));
  } finally {
    restoreFetch();
    restoreLog();
  }
});

test('🧹 buildErrorHTML escapes the message it is handed', () => {
  const html = buildErrorHTML('test <script> malicious');
  assert.ok(html.includes('test'));
  assert.ok(!html.includes('<script>'));
  // The message is URI-encoded, so the tag arrives as text rather than markup.
  assert.ok(html.includes(encodeURIComponent('<script>')));
});

// Dropped from the vitest version: "XSS script 注入被 DOMPurify 拦截" asserted on a
// `DOMPurify` **mock this file defined itself**, so it exercised no production code and
// passed no matter what `core.js` did — a green that meant nothing. The test above
// covers the same property against `buildErrorHTML`, which is the code that actually
// builds HTML. `core.js` does not use DOMPurify at all.