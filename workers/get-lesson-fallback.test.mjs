// `misakanet_get_lesson` must survive a D1 quota refusal (2026-10-17).
//
// Measured during the D1 outage: search worked (it reads the KV index) but every get_lesson answered
// `internal_error`, so a user could find a lesson and then be unable to open it. The file it wanted is
// public on `main`, and `fetchLessonContent` already knows how to read it — the D1 exception simply
// escaped before that branch was reached.
//
// Run: node --test workers/get-lesson-fallback.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { fetchLessonContent } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('get-lesson');

const QUOTA = new Error(
  "D1_ERROR: Your account has exceeded D1's free tier daily row read limit. Upgrade to a paid plan or "
  + 'wait until tomorrow (midnight UTC) to continue.',
);

const refusingD1 = () => {
  const refused = async () => { throw QUOTA; };
  const stmt = { bind() { return stmt; }, all: refused, run: refused, first: refused, raw: refused };
  return { prepare() { return stmt; }, exec: refused, batch: refused };
};

const bodyOf = (n) => '---\ntitle: x\n---\n' + 'line\n'.repeat(n);

function withGitHubFile(path, content, fn) {
  const real = globalThis.fetch;
  globalThis.fetch = async (url) => {
    if (String(url).includes(encodeURIComponent(path)) || String(url).includes(path)) {
      return new Response(JSON.stringify({
        content: Buffer.from(content).toString('base64'), encoding: 'base64',
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }
    return new Response('{}', { status: 404, headers: { 'Content-Type': 'application/json' } });
  };
  return fn().finally(() => { globalThis.fetch = real; });
}

test('a D1 quota refusal falls through to the public file', () =>
  withGitHubFile('lessons/core/demo.md', bodyOf(3), async () => {
    const lesson = await fetchLessonContent(
      { MISAKANET_D1: refusingD1(), REGISTER_TOKEN: TOKEN }, null, 'demo');
    assert.equal(lesson.path, 'lessons/core/demo.md');
    assert.match(lesson.content, /^---/);
  }));

test('the 5,000-character cap is reported, not silent', () =>
  withGitHubFile('lessons/core/long.md', bodyOf(1200), async () => {
    const lesson = await fetchLessonContent(
      { MISAKANET_D1: refusingD1(), REGISTER_TOKEN: TOKEN }, null, 'long');
    assert.equal(lesson.content.length, 5000, 'the returned body is the cap');
    assert.ok(lesson.content_length > 5000, 'the full length travels with it');
  }));

test('without a GitHub token the failure is a reason, not a quota leak', async () => {
  await assert.rejects(
    () => fetchLessonContent({ MISAKANET_D1: refusingD1() }, null, 'demo'),
    (error) => !/D1_ERROR|daily row read/i.test(String(error.message)),
  );
});
