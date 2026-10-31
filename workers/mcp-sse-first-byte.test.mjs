// The SSE answer must start moving before the work does (#4072).
//
// Measured on production 2026-10-31 with `Accept: text/event-stream`: median first byte 8,100 ms
// against a total of 8,279 ms — the whole frame was built and returned, so the link dropped anything
// slower than ~3 s. The fix is a ReadableStream whose first chunk is a comment, enqueued before any
// await; these tests pin exactly that ordering, because a refactor that awaits first recreates the bug
// while still "returning SSE".
import test from 'node:test';
import assert from 'node:assert/strict';

import { mcpSseStreamedResponse } from './register-proxy-sw.js';

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

async function chunks(response, limit = 4) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const out = [];
  for (let i = 0; i < limit; i += 1) {
    const { value, done } = await reader.read();
    if (done) break;
    out.push(decoder.decode(value));
  }
  return out;
}

test('the first chunk is the comment, before the work resolves', async () => {
  let released;
  const gate = new Promise((resolve) => { released = resolve; });
  const response = mcpSseStreamedResponse(async () => {
    await gate;
    return jsonResponse({ jsonrpc: '2.0', id: 1, result: { ok: true } });
  });
  const reader = response.body.getReader();
  const first = await reader.read();
  const text = new TextDecoder().decode(first.value);
  assert.equal(text, ': connected\n\n', 'the comment is the first bytes, not the frame');
  released();
  const rest = [];
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    rest.push(new TextDecoder().decode(value));
  }
  const frame = rest.join('');
  assert.match(frame, /^event: message\ndata: \{.*\}\n\n$/s);
  assert.deepEqual(JSON.parse(frame.split('data: ')[1]), { jsonrpc: '2.0', id: 1, result: { ok: true } });
});

test('the content type is SSE and the status is 200', () => {
  const response = mcpSseStreamedResponse(async () => jsonResponse({}));
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('content-type'), 'text/event-stream');
  assert.equal(response.headers.get('cache-control'), 'no-cache');
});

test('a handler that throws becomes a JSON-RPC error frame, not a dead stream', async () => {
  const response = mcpSseStreamedResponse(async () => { throw new Error('boom'); });
  const all = (await chunks(response, 8)).join('');
  assert.match(all, /^-?\s*: connected/);
  const frame = all.split('event: message\ndata: ')[1];
  const body = JSON.parse(frame);
  assert.equal(body.error.code, -32603);
  assert.match(body.error.message, /boom/);
});

test('a handler that returns non-JSON still yields a parseable frame', async () => {
  const response = mcpSseStreamedResponse(async () => new Response('<html>nope</html>'));
  const all = (await chunks(response, 8)).join('');
  const body = JSON.parse(all.split('event: message\ndata: ')[1]);
  assert.equal(body.error.code, -32603);
  assert.match(body.error.message, /did not return JSON/);
});

test('the stream closes after the frame', async () => {
  const response = mcpSseStreamedResponse(async () => jsonResponse({ jsonrpc: '2.0', id: 2, result: {} }));
  const reader = response.body.getReader();
  const seen = [];
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    seen.push(new TextDecoder().decode(value));
  }
  assert.equal(seen.length, 2, seen);
  assert.ok(seen[1].includes('"result"'));
});
