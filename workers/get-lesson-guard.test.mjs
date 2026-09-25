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
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('b35');

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
async function withUpstream(status, args) {
  const seen = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    seen.push(String(url));
    return new Response(status === 200 ? JSON.stringify({ content: '', encoding: 'utf-8' }) : '{}',
      { status, headers: { 'content-type': 'application/json' } });
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
