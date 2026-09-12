// Issue #1605 regression: MCP tools/call responses must carry
// `result.structuredContent` (MCP 2025-06-18), otherwise strict clients
// (e.g. the DSH/cordis patch harness) reject the tool output with
// 'missing required property "value.structuredContent"'.
// Run: node --test workers/mcp-structured-output.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('structured-output');

const SAMPLE_LESSONS = [
  {
    id: 'pip-timeout-mirror',
    title: 'pip install timeout behind corporate proxy',
    domain: 'python',
    tags: ['pip', 'proxy'],
    description: 'Use an internal mirror and raise the timeout.',
    path: 'lessons/contrib/pip-timeout-mirror.md',
  },
];

function createEnv(lessons) {
  const store = new Map([
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: lessons })],
  ]);
  return {
    MCP_TOKEN: TOKEN,
    MCP_VERSION: 'structured-output-test',
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) {
        store.set(key, value);
      },
      async delete(key) {
        store.delete(key);
      },
    },
  };
}

function toolCall(query, name = 'misakanet_search', args = {}) {
  return new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '198.51.100.' + (Math.floor(Math.random() * 200) + 1),
    },
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: 1,
      method: 'tools/call',
      params: { name, arguments: query === null ? args : { query, ...args } },
    }),
  });
}

test('tools/call response includes object-typed structuredContent (#1605)', async () => {
  const resp = await worker.fetch(toolCall('pip install timeout'), createEnv(SAMPLE_LESSONS));
  assert.equal(resp.status, 200);
  const body = await resp.json();
  assert.equal(body.error, undefined, `unexpected error: ${JSON.stringify(body.error)}`);

  const result = body.result;
  assert.ok(result, 'result missing');
  assert.ok(Array.isArray(result.content) && result.content[0].text, 'content text missing');

  // The regression: structuredContent must exist and be a JSON object.
  assert.ok('structuredContent' in result, 'structuredContent missing');
  assert.equal(typeof result.structuredContent, 'object');
  assert.equal(Array.isArray(result.structuredContent), false);

  // And it must mirror the text payload (same JSON).
  assert.deepEqual(result.structuredContent, JSON.parse(result.content[0].text));
});

test('structuredContent also present on the no_match path', async () => {
  const resp = await worker.fetch(
    toolCall('zzz-no-such-topic-anywhere-999'),
    createEnv(SAMPLE_LESSONS),
  );
  const body = await resp.json();
  assert.ok('structuredContent' in body.result);
  assert.equal(body.result.structuredContent.no_match, true);
});

test('non-object tool results are wrapped under {value}', async () => {
  // misakanet_list_lessons (or any tool returning an array) must still yield an
  // object-typed structuredContent, per spec.
  const resp = await worker.fetch(
    toolCall(null, 'misakanet_search', { query: 'pip', top: 1 }),
    createEnv(SAMPLE_LESSONS),
  );
  const body = await resp.json();
  assert.equal(typeof body.result.structuredContent, 'object');
  assert.equal(Array.isArray(body.result.structuredContent), false);
});
