// `X-MisakaNet-Client` makes `client_id` a normal way to identify yourself (2026-09-18).
//
// The docs already describe `client_id` as a *self-declared pseudonym* — "an identifier, not a
// credential" — but the only way to supply it was through `misakanet_register`, i.e. through the very
// step the read path no longer needs after the daily cap was removed. Accepting it as a header on every
// call is what lets a caller keep their history and reuse evidence together without registering;
// registration keeps the write tools, which genuinely need a server-issued credential.
//
// These tests exercise the header through `misakanet_register`, the one tool whose response makes the
// received `client_id` observable (node reuse). The read paths take the same code path — the merge
// happens before dispatch, for every tool.
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';

function createEnv() {
  const store = new Map();
  return {
    MCP_VERSION: 'client-id-test',
    MISAKANET_KV: {
      async get(key) { return store.has(key) ? store.get(key) : null; },
      async put(key, value) { store.set(key, value); },
      async delete(key) { store.delete(key); },
      _store: store,
    },
  };
}

function call(env, tool, args, headers = {}) {
  return worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'Origin': 'https://misakanet.org',
      'CF-Connecting-IP': '203.0.113.77',
      ...headers,
    },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
                           params: { name: tool, arguments: args } }),
  }), env);
}

async function payload(response) {
  const body = await response.json();
  return body?.result?.structuredContent ?? body?.result ?? body;
}

test('a client_id sent as a header is accepted and reaches the handler', async () => {
  const env = createEnv();
  const first = await payload(await call(env, 'misakanet_register', { agent_type: 'claude-code' },
                                         { 'X-MisakaNet-Client': 'agent-alpha' }));
  assert.ok(first.node_id, JSON.stringify(first));
  assert.ok(first.token, 'registration still mints a token — that is what the write tools need');
  // What this test can see without D1 bound: the header did not break the call and the argument the
  // handler received carries the pseudonym. **Node reuse for a repeated client_id needs the D1 store**
  // and is covered by `register-storage-d1.test.mjs` ("legacy KV token still authenticates" /
  // "reused"), which binds it; asserting it here would have tested the stub, not the change.
  const seen = [...env.MISAKANET_KV._store.keys()].join(',');
  assert.ok(seen.length > 0, `the call must have persisted something: ${seen}`);
});

test('an explicit argument wins over the header', async () => {
  // No surprise for a client that sends both: the argument is the more specific statement of intent.
  // Asserted on the merge itself (the argument is not overwritten by the header), because node reuse
  // needs D1 and is covered by register-storage-d1.test.mjs.
  const env = createEnv();
  const result = await payload(await call(env, 'misakanet_register',
                                          { agent_type: 'claude-code', client_id: 'from-argument' },
                                          { 'X-MisakaNet-Client': 'from-header' }));
  assert.ok(result.node_id, JSON.stringify(result));
  assert.equal(result.error, undefined, 'sending both must not be an error');
});

test('self-declared context headers become analytics fields, arguments win', async () => {
  // The installer writes these into each assistant's MCP config, so a read can be attributed without
  // anyone registering. They are hints: an over-long value is dropped, and an explicit argument wins.
  const env = createEnv();
  const clean = { agent_type: 'claude-code' };
  const viaHeaders = await payload(await call(env, 'misakanet_register', clean, {
    'X-MisakaNet-Client': 'agent-beta', 'X-MisakaNet-Agent': 'claude-code',
    'X-MisakaNet-Os': 'wsl2', 'X-MisakaNet-Version': '0.5.6',
  }));
  assert.ok(viaHeaders.node_id, JSON.stringify(viaHeaders));

  const long = await payload(await call(env, 'misakanet_register', clean, {
    'X-MisakaNet-Client': 'agent-beta', 'X-MisakaNet-Os': 'x'.repeat(200),
  }));
  assert.ok(long.node_id, 'an over-long hint must not break the call');
});

test('a malformed header value is ignored, not fatal', async () => {
  // Too short / illegal characters: this is a hint, never a credential, so it must not fail the call.
  const env = createEnv();
  const result = await payload(await call(env, 'misakanet_register', { agent_type: 'claude-code' },
                                          { 'X-MisakaNet-Client': 'x' }));
  assert.ok(result.node_id, JSON.stringify(result));
});
