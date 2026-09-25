// B35: a missing lesson is not a service fault, and a repository file is not a lesson.
//
// Measured against production on 2026-09-25, `misakanet_get_lesson` answered two ways it should not:
//
//   * `path=docs/CI.md` returned that file's text — the path went into the GitHub contents URL
//     unvalidated, so a tool documented as "fetch one public lesson" was also a read-anything-in-the-
//     repository endpoint, and it is the tool the whole product asks strangers' agents to call;
//   * a path that does not exist answered
//     `{"error":"Temporary service error. Retry shortly.","code":"internal_error"}` — the message for a
//     *service fault*. An agent that obeys it retries a 404 forever; an agent that reports it says
//     "MisakaNet is down" for a lesson that was never there. The id branch had the mirror-image bug:
//     `catch {}` swallowed a 401 and called it "Lesson not found".
//
// The fix is a reference check before any fetch, a 404-only not-found, and stable codes the caller can
// branch on. This file drives the real worker; the GitHub answers are a stub, because what is under
// test is which answer the worker gives for a given upstream answer.
//
// Run: node --test workers/get-lesson-guard.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('b35');
const REPO = fileURLToPath(new URL('../', import.meta.url));

function createEnv() {
  return { MCP_TOKEN: TOKEN, REGISTER_TOKEN: TOKEN, MCP_VERSION: 'b35-test' };
}

function mcpCall(args) {
  return worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '203.0.113.77',
      // Authenticated, so the anonymous read burst window (one counter per address per minute) does not
      // decide the outcome of a test that makes hundreds of calls in a second.
      Authorization: `Bearer ${TOKEN}`,
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_get_lesson', arguments: args },
    }),
  }), createEnv());
}

async function answer(args) {
  const resp = await mcpCall(args);
  const body = await resp.json();
  return { status: resp.status, payload: JSON.parse(body.result.content[0].text) };
}

/** Run one call against a stub GitHub that answers `status` for every contents request. */
const LESSON_BODY = '# A lesson\n\n## Root cause\n\nSomething real.\n';

async function withUpstream(status, args) {
  const seen = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    seen.push(String(url));
    if (status !== 200) {
      return new Response('{}', { status, headers: { 'content-type': 'application/json' } });
    }
    // A 200 has to look like a real contents-API answer. The worker only accepts
    // `encoding === "base64"` before using `content`, so a stub that answered `{content, encoding:
    // 'utf-8'}` would return *no* content for a lesson that exists — and a happy-path assertion
    // written against it would read "the guard rejected a valid lesson" from its own fixture.
    return new Response(JSON.stringify({
      content: Buffer.from(LESSON_BODY, 'utf-8').toString('base64'),
      encoding: 'base64',
    }), { status: 200, headers: { 'content-type': 'application/json' } });
  };
  try {
    const result = await answer(args);
    return { ...result, seen };
  } finally {
    globalThis.fetch = originalFetch;
  }
}

test('a repository file that is not a lesson is refused, not read', async () => {
  // The measured production call: `path=docs/CI.md` used to return that file.
  const { payload, seen } = await withUpstream(200, { path: 'docs/CI.md' });
  assert.equal(payload.code, 'invalid_lesson_path', JSON.stringify(payload));
  assert.equal(seen.length, 0, `nothing may be fetched for a refused reference: ${seen}`);
});

test('the refusal names what a lesson path looks like', async () => {
  const { payload } = await withUpstream(200, { path: 'data/lessons.json' });
  assert.equal(payload.code, 'invalid_lesson_path');
  assert.match(payload.error, /lessons\/<topic>\/<slug>\.md/);
});

for (const bad of ['lessons/../../data/lessons.json', '/lessons/core/x.md', 'lessons//core/x.md',
                   'lessons/core/x.txt', 'lessons/core/x.md.bak', '']) {
  test(`a reference that escapes the lesson tree is refused: ${JSON.stringify(bad)}`, async () => {
    const { payload, seen } = await withUpstream(200, { path: bad });
    assert.equal(payload.code, 'invalid_lesson_path', JSON.stringify(payload));
    assert.equal(seen.length, 0, 'no fetch may happen for a rejected reference');
  });
}

test('a lesson path that does not exist is lesson_not_found, not internal_error', async () => {
  const { payload, seen } = await withUpstream(404, { path: 'lessons/core/no-such-lesson.md' });
  assert.equal(payload.code, 'lesson_not_found', JSON.stringify(payload));
  assert.doesNotMatch(payload.error || '', /Retry shortly/, 'retrying a 404 is the bug this fixes');
  assert.equal(seen.length, 2, `both refs (main, data) are tried before saying not found: ${seen}`);
  assert.ok(seen.every((u) => u.includes('ref=main') || u.includes('ref=data')), seen.join(' '));
});

test('an unknown id is lesson_not_found too', async () => {
  const { payload } = await withUpstream(404, { id: 'no-such-lesson' });
  assert.equal(payload.code, 'lesson_not_found', JSON.stringify(payload));
});

test('a real lesson path still returns the body — the guard must not block the happy path', async () => {
  const { payload, seen } = await withUpstream(200, { path: 'lessons/core/auto-merge-ci-pipeline.md' });
  assert.equal(payload.path, 'lessons/core/auto-merge-ci-pipeline.md', JSON.stringify(payload).slice(0, 200));
  assert.match(payload.content, /## Root cause/);
  assert.equal(payload.code, undefined, 'a found lesson carries no code');
  assert.equal(seen.length, 1, `the first ref that answers wins, and only it: ${seen.join(' ')}`);
  assert.match(seen[0], /ref=main/);
});

test('an id that is not a slug is refused before six useless fetches', async () => {
  const { payload, seen } = await withUpstream(404, { id: '../../data/lessons' });
  assert.equal(payload.code, 'invalid_lesson_path', JSON.stringify(payload));
  assert.equal(seen.length, 0, seen.join(' '));
});

test('a real upstream fault stays internal_error — the code has to keep meaning something', async () => {
  for (const status of [401, 403, 500, 503]) {
    const { payload } = await withUpstream(status, { path: 'lessons/core/x.md' });
    assert.equal(payload.code, 'internal_error', `HTTP ${status} answered ${JSON.stringify(payload)}`);
    assert.match(payload.error, /Retry shortly/);
  }
});

test('the two new codes are documented in the tool description', async () => {
  // The description is the contract a caller's model reads; a code that exists only in the handler is
  // only discoverable by hitting it.
  const listed = await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'MCP-Protocol-Version': '2025-06-18' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/list' }),
  }), createEnv());
  const body = await listed.json();
  const tool = body.result.tools.find((t) => t.name === 'misakanet_get_lesson');
  assert.ok(tool, 'misakanet_get_lesson is gone');
  for (const code of ['lesson_not_found', 'invalid_lesson_path', 'internal_error']) {
    assert.match(tool.description, new RegExp(code), `${code} is not described`);
  }
  assert.match(tool.inputSchema.properties.path.description, /lessons\//, 'the path argument is not documented');
});

// ── The guard against the real corpus, not against its own idea of a filename ────────────────────────
//
// The first version of the guard was `[A-Za-z0-9._/-]`, and the corpus contains
// `lessons/contrib/자바-버전-불일치-빌드-오류.md` — a published lesson whose index id is the same Korean
// string. Both the path and the id were refused with `invalid_lesson_path`, i.e. the guard answered
// "your argument is malformed" for a lesson `misakanet_search` returns by name. That is worse than the
// bug it fixed, and no test written against this file's idea of a filename could see it: the rule has
// to be checked against the lesson set. Both of these read it from the checkout.

function lessonFiles() {
  const out = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (entry.name.endsWith('.md')) out.push(path.relative(REPO, full).split(path.sep).join('/'));
    }
  };
  walk(path.join(REPO, 'lessons'));
  return out;
}

test('every lesson file in this checkout passes the path guard', async () => {
  const files = lessonFiles();
  assert.ok(files.length > 400, `the corpus probe found ${files.length} lessons — it is broken, not the guard`);
  const refused = [];
  for (const rel of files) {
    const { payload } = await withUpstream(200, { path: rel });
    if (payload.code === 'invalid_lesson_path') refused.push(rel);
  }
  assert.deepEqual(refused, [], `the guard refuses lessons that exist: ${refused.slice(0, 5).join(', ')}`);
});

test('every id in the public index passes the id guard', async () => {
  const index = JSON.parse(readFileSync(path.join(REPO, 'data', 'lessons.json'), 'utf8'));
  const ids = [...new Set(index.map((row) => row.id).filter(Boolean))];
  assert.ok(ids.length > 300, `the index probe found ${ids.length} ids — it is broken, not the guard`);
  const refused = [];
  for (const id of ids) {
    const { payload } = await withUpstream(200, { id });
    if (payload.code === 'invalid_lesson_path') refused.push(id);
  }
  assert.deepEqual(refused, [], `the guard refuses ids the index publishes: ${refused.slice(0, 5).join(', ')}`);
});
