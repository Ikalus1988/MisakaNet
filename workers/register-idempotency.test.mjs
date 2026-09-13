// A registering client must keep the same identity across calls (2026-09-13).
//
// Found in production: two identical `misakanet_register` calls returned
// Misaka10130 and Misaka10131, because registration minted a node per request. The
// same agent therefore accumulated nothing — reuse evidence (E4), receipts and
// history restarted on every call, and the leaderboard counted one agent as many.
// Mature practice is the opposite: the client supplies a stable identifier and the
// server replays the same record (Stripe's Idempotency-Key, OAuth's client_id).
//
// These tests pin the contract, including the property that matters for the KV
// free tier: a returning client must not create new distinct keys — rewrites of
// existing keys are free, new keys are what exhausts the daily budget (#1648).
//
// Run: node --test workers/register-idempotency.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';

function createEnv({ failClientKeyWrites = false } = {}) {
  const store = new Map();
  return {
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) {
        if (failClientKeyWrites && key.startsWith('client:')) {
          throw new Error('KV PUT failed: 429 Too Many Requests');
        }
        store.set(key, value);
      },
      async delete(key) { store.delete(key); },
    },
    _store: store,
  };
}

function mcpCall(args) {
  return new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'Origin': 'https://misakanet.org',
      'CF-Connecting-IP': '203.0.113.7',
    },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_register', arguments: args } }),
  });
}

async function register(env, args = {}) {
  const response = await worker.fetch(mcpCall(args), env);
  assert.equal(response.status, 200, `HTTP ${response.status} instead of a tool result`);
  const body = await response.json();
  return JSON.parse(body.result.content[0].text);
}

test('the same client_id returns the same node and token', async () => {
  const env = createEnv();
  const first = await register(env, { agent_type: 'claude-code', client_id: 'workspace-abc-123' });
  const second = await register(env, { agent_type: 'claude-code', client_id: 'workspace-abc-123' });

  assert.equal(first.node_id, second.node_id,
    'a client that identifies itself must not be handed a new identity on the next call');
  assert.equal(first.token, second.token, 'the token is the credential for that identity');
  assert.equal(second.reused, true, 'the caller should be able to tell it was recognised');
  assert.ok(String(first.token).startsWith('mcp_'), JSON.stringify(first));
});

test('a returning client creates no new KV keys', async () => {
  const env = createEnv();
  const before = await register(env, { client_id: 'kv-budget-client' });
  const keysAfterFirst = new Set(env._store.keys());

  const second = await register(env, { client_id: 'kv-budget-client' });
  assert.equal(second.node_id, before.node_id);

  // Only rewrites: the daily quota counts *distinct keys written*, so a renewal that
  // adds keys would make repeat registration the thing that runs the account dry.
  assert.deepEqual([...env._store.keys()].sort(), [...keysAfterFirst].sort(),
    `renewal added new keys: ${[...env._store.keys()].filter((k) => !keysAfterFirst.has(k))}`);
});

test('reuse renews the token expiry instead of letting it lapse', async () => {
  const env = createEnv();
  const first = await register(env, { client_id: 'renew-me-please' });
  const tokenKey = `mcp_token:${first.token}`;
  const before = JSON.parse(env._store.get(tokenKey)).expires;

  await new Promise((resolve) => setTimeout(resolve, 15));
  await register(env, { client_id: 'renew-me-please' });
  const after = JSON.parse(env._store.get(tokenKey)).expires;

  assert.ok(Date.parse(after) > Date.parse(before),
    `expiry should move forward on reuse, got ${before} -> ${after}`);
});

test('a different client_id gets its own node', async () => {
  const env = createEnv();
  const one = await register(env, { client_id: 'client-one-aaaa' });
  const two = await register(env, { client_id: 'client-two-bbbb' });
  assert.notEqual(one.node_id, two.node_id);
  assert.notEqual(one.token, two.token);
});

test('omitting client_id keeps the previous one-node-per-call behaviour', async () => {
  const env = createEnv();
  const one = await register(env, { agent_type: 'legacy-caller' });
  const two = await register(env, { agent_type: 'legacy-caller' });
  assert.notEqual(one.node_id, two.node_id,
    'callers that pass nothing must not change behaviour — this stays backward compatible');
  assert.equal(one.reused, undefined);
});

test('a malformed client_id is rejected before any key is written', async () => {
  const env = createEnv();
  for (const bad of ['short', 'has spaces here', 'semi;colon-not-allowed', 'x'.repeat(65)]) {
    const result = await register(env, { client_id: bad });
    assert.equal(result.code, 'invalid_client_id', `${bad} → ${JSON.stringify(result)}`);
    assert.ok(result.hint, 'the caller needs to know what a valid value looks like');
  }
  // Traffic telemetry is written for any call, so assert on registration keys only:
  // a rejected client_id must not mint a node, a token, or a mapping.
  const registrationKeys = [...env._store.keys()].filter((k) =>
    k.startsWith('node:') || k.startsWith('mcp_token:') || k.startsWith('client:'));
  assert.deepEqual(registrationKeys, [], `invalid input wrote keys: ${registrationKeys}`);
});

test('failing to store the client_id mapping still returns a usable token', async () => {
  const env = createEnv({ failClientKeyWrites: true });
  const result = await register(env, { agent_type: 'mapping-write-fails', client_id: 'mapping-fails-here' });

  // Losing the mapping costs continuity, not access: the token the caller receives
  // must be one that was actually stored, or its next authenticated call fails.
  assert.ok(String(result.token || '').startsWith('mcp_'), JSON.stringify(result));
  assert.ok(result.node_id, JSON.stringify(result));
  assert.ok(env._store.has(`mcp_token:${result.token}`), 'token must be persisted');
});
