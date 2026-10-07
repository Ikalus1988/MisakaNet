// The results this worker returns must carry the fields the protocol version it advertises
// actually requires.
//
// `#2968` reported the symptom — a client with `versionNegotiation: {mode: 'auto'}` picks the
// modern epoch, then throws `SdkError(INVALID_RESULT)` and reports `server is disconnected` —
// and pointed at the wrong layer. Negotiation is the client's; what is wrong is ours.
//
// `SUPPORTED_PROTOCOL_VERSIONS` is `["2025-06-18", "2026-07-28"]`, and in
// `schema/2026-07-28/schema.json` (read 2026-10-07) the results for the two methods this worker
// answers are:
//
//     ListToolsResult.required  = ['cacheScope', 'resultType', 'tools', 'ttlMs']
//     CallToolResult.required   = ['content', 'resultType']
//
// `server/discover` had this defect first and was fixed when it became reachable; `tools/list`
// and `tools/call` carried on without the fields. `tools/list` is the one nearly every client
// calls, so its omission was the more exposed of the two.
//
// The assertions run against real responses rather than the source text, so they hold however the
// handler is refactored. `initialize` is deliberately absent: that schema file does not define
// `InitializeResult` at all — it lives in the lifecycle specification — so there is nothing here
// to check it against, and inventing the field list would be worse than not checking it.
//
// Run: node --test workers/mcp-result-shape.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('result-shape');

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

function createEnv() {
  const store = new Map([
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: SAMPLE_LESSONS })],
  ]);
  return {
    // Synthetic and per-run — a literal here is indistinguishable from a credential to a scanner.
    // See workers/_test-token.mjs.
    MCP_TOKEN: TOKEN,
    MCP_VERSION: 'result-shape-test',
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) { store.set(key, value); },
      async delete(key) { store.delete(key); },
    },
  };
}

function mcpRequest(method, params = {}) {
  return worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2026-07-28',
      'CF-Connecting-IP': '203.0.113.7',
    },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }),
  }), createEnv());
}

/** A reply is SSE-framed when the client asked for text/event-stream, plain JSON otherwise. */
async function bodyOf(response) {
  const text = await response.text();
  const line = text.split('\n').find((l) => l.startsWith('data: '));
  return JSON.parse(line ? line.slice(6) : text);
}

test('tools/list carries every field ListToolsResult requires for 2026-07-28', async () => {
  const response = await mcpRequest('tools/list');
  assert.equal(response.status, 200);
  const { result } = await bodyOf(response);

  assert.ok(result, 'tools/list returned no result');
  for (const field of ['tools', 'resultType', 'ttlMs', 'cacheScope']) {
    assert.ok(field in result, `tools/list omits ${field}, which ListToolsResult requires`);
  }
  assert.equal(result.resultType, 'complete');
  // The tool definitions are identical for every caller and the method is public, so `public` is
  // the truthful scope. A wrong value here would be worse than an absent one: the client would
  // cache across authorization contexts on the strength of it.
  assert.equal(result.cacheScope, 'public');
});

test('tools/call carries every field CallToolResult requires for 2026-07-28', async () => {
  const response = await mcpRequest('tools/call', {
    name: 'misakanet_search',
    arguments: { query: 'pip install timeout' },
  });
  assert.equal(response.status, 200);
  const body = await bodyOf(response);
  assert.equal(body.error, undefined, `unexpected error: ${JSON.stringify(body.error)}`);

  const { result } = body;
  for (const field of ['content', 'resultType']) {
    assert.ok(field in result, `tools/call omits ${field}, which CallToolResult requires`);
  }
  // `cacheScope` belongs to CacheableResult, which CallToolResult does not extend. A tool result
  // can be per-node — `misakanet_me_events` returns one node's evidence — so declaring it public
  // would be a lie the client is entitled to act on.
  assert.ok(!('cacheScope' in result), 'tools/call must not declare a cacheScope it cannot honour');
});

test('server/discover still answers with all five DiscoverResult fields', async () => {
  const response = await mcpRequest('server/discover');
  assert.equal(response.status, 200);
  const { result } = await bodyOf(response);

  assert.ok(result, 'server/discover returned no result');
  for (const field of ['capabilities', 'supportedVersions', 'resultType', 'ttlMs', 'cacheScope']) {
    assert.ok(field in result, `server/discover omits ${field}, which DiscoverResult requires`);
  }
});