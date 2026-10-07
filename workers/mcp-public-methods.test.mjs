// Every MCP method this worker answers must be reachable without a token.
//
// The public-method gate was three explicit `===` comparisons — `initialize`, `tools/list`,
// `server/discover` — and every other method fell behind a 401 that the handler behind it never
// sees. The MCP SDK classifies a 401 as a *transport* failure rather than a protocol miss, so to
// the client an answered-but-gated method and an unimplemented one are the same event.
//
// #2963 is that, measured: DSH's `list_mcp_resources` calls `resources/list` on this server and
// reports `mcp-client(misakanet): server is disconnected`. Before this change, unauthenticated:
//
//     initialize / tools/list / server/discover   200 / result
//     ping, resources/list,                       401 / -32000
//     resources/templates/list, prompts/list
//
// and the same four answered fine with a token. The gate is also asserted from the other side, so
// it cannot be satisfied by simply making everything public: `tools/call` is the quota-bounded
// read-and-write path and must keep returning 401 to an anonymous caller.
//
// Run: node --test workers/mcp-public-methods.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('public-methods');

function createEnv() {
  const store = new Map([
    ['proxy:lessons', JSON.stringify({
      ts: Date.now(),
      data: [{ id: 'x', title: 't', description: 'd', path: 'lessons/core/x.md', tags: [] }],
    })],
  ]);
  return {
    // Synthetic and per-run; see workers/_test-token.mjs.
    MCP_TOKEN: TOKEN,
    MCP_VERSION: 'public-methods-test',
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

async function call(method, params = {}, { authed = false } = {}) {
  const headers = {
    'Content-Type': 'application/json',
    'MCP-Protocol-Version': '2026-07-28',
    'CF-Connecting-IP': '203.0.113.7',
  };
  if (authed) headers.Authorization = `Bearer ${TOKEN}`;
  const response = await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers,
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }),
  }), createEnv());
  const text = await response.text();
  const line = text.split('\n').find((l) => l.startsWith('data: '));
  let body = null;
  try {
    body = JSON.parse(line ? line.slice(6) : text);
  } catch {
    // left null — the assertions below say what a missing body means
  }
  return { status: response.status, body };
}

// Every method the handler answers. `tools/call` is excluded: see the gate test at the bottom.
const DISCOVERY_METHODS = [
  'initialize',
  'ping',
  'tools/list',
  'resources/list',
  'resources/templates/list',
  'prompts/list',
  'server/discover',
];

test('every discovery method is reachable without a token (#2963)', async () => {
  for (const method of DISCOVERY_METHODS) {
    const { status, body } = await call(method);
    assert.notEqual(status, 401,
      `${method} answers 401 to an anonymous caller, which the SDK reports as a transport ` +
      'failure — "server is disconnected" rather than the protocol error it actually is');
    assert.equal(status, 200, `${method} returned ${status} anonymously`);
    assert.ok(body && (body.result !== undefined || body.error),
      `${method} returned no JSON-RPC payload: ${JSON.stringify(body)}`);
  }
});

test('an anonymous discovery call carries no lesson data', async () => {
  // Being reachable is only safe if what comes back is public. `tools/list` is the one method
  // that returns real content, and it returns tool definitions — not corpus rows.
  const { body } = await call('tools/list');
  const serialised = JSON.stringify(body);
  assert.ok(!serialised.includes('lessons/core/x.md'),
    'tools/list leaked a corpus path to an anonymous caller');

  const { body: discover } = await call('server/discover');
  assert.ok(JSON.stringify(discover).includes('serverInfo') ||
    JSON.stringify(discover).includes('io.modelcontextprotocol/serverInfo'));
});

test('a tool outside the open set is still refused to an anonymous caller', async () => {
  // The guard against the obvious over-correction. The open set is deliberate and pre-existing —
  // search, get_lesson, submit_intake, register and me_events are anonymous by design, with the
  // read quota enforced inside the handler (`mcp-anonymous-read.test.mjs`). What must *not* happen
  // is that widening the discovery set also widened this one.
  const anonymous = await call('tools/call', {
    name: 'misakanet_write_lesson', arguments: { title: 'x', body: 'y' },
  });
  assert.equal(anonymous.status, 401);
  assert.equal(anonymous.body.error.code, -32000);

  const authed = await call(
    'tools/call', { name: 'misakanet_write_lesson', arguments: { title: 'x', body: 'y' } },
    { authed: true },
  );
  assert.notEqual(authed.status, 401);
});

test('an open tool is still reachable without a token', async () => {
  // The other anonymous surface, via `isIntakeCall` rather than `isPublicMethod`. Asserted so a
  // future change to the discovery set cannot quietly close it.
  const { status, body } = await call('tools/call', {
    name: 'misakanet_search', arguments: { query: 'pip mirror' },
  });
  assert.notEqual(status, 401, 'misakanet_search is open by design');
  assert.ok(body && (body.result !== undefined || body.error));
});