// A client_id is a name; the token is the key (2026-10-31 audit, needs_validation).
//
// `misakanet_register` used to hand a node's token to anyone who presented its client_id. The audit
// called that what it is: an identifier documented as a key. The fix asks the caller for the token it
// was given — proof that it already holds the key — with a grace period so nobody is locked out on the
// day they renew.
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';

function createEnv(extra = {}) {
  const store = new Map();
  return {
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) { store.set(key, value); },
      async delete(key) { store.delete(key); },
    },
    _store: store,
    ...extra,
  };
}

function call(args, token) {
  const headers = {
    'Content-Type': 'application/json',
    'MCP-Protocol-Version': '2025-06-18',
    'Origin': 'https://misakanet.org',
    'CF-Connecting-IP': '203.0.113.9',
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  return new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers,
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_register', arguments: args } }),
  });
}

async function register(env, args, token) {
  const response = await worker.fetch(call(args, token), env);
  assert.equal(response.status, 200, `HTTP ${response.status}`);
  const body = await response.json();
  return JSON.parse(body.result.content[0].text);
}

test('presenting the token it was given renews the node, with no deprecation note', async () => {
  const env = createEnv();
  const first = await register(env, { client_id: 'proof-client-aaa1' });
  const second = await register(env, { client_id: 'proof-client-aaa1' }, first.token);
  assert.equal(second.node_id, first.node_id);
  assert.equal(second.reused, true);
  assert.equal(second.deprecated, undefined, 'a proven renewal is the supported path');
});

test('client_id alone still works during the grace period, and says what is coming', async () => {
  const env = createEnv();
  const first = await register(env, { client_id: 'proof-client-bbb2' });
  const second = await register(env, { client_id: 'proof-client-bbb2' });
  assert.equal(second.node_id, first.node_id);
  assert.match(String(second.deprecated), /token you were|Authorization: Bearer/);
});

test('strict mode refuses renewal by name alone', async () => {
  const env = createEnv({ MISAKANET_CLIENT_ID_PROOF: 'strict' });
  const first = await register(env, { client_id: 'proof-client-ccc3' });
  const refused = await register(env, { client_id: 'proof-client-ccc3' });
  assert.equal(refused.code, 'client_id_proof_required');
  assert.ok(!refused.token, 'no token may leak to a caller that only knows the name');
  // ...and the proven path still works in strict mode.
  const renewed = await register(env, { client_id: 'proof-client-ccc3' }, first.token);
  assert.equal(renewed.node_id, first.node_id);
});

test('another node\'s token is not proof', async () => {
  const env = createEnv({ MISAKANET_CLIENT_ID_PROOF: 'strict' });
  const mine = await register(env, { client_id: 'proof-client-ddd4' });
  const other = await register(env, { client_id: 'proof-client-eee5' });
  const refused = await register(env, { client_id: 'proof-client-ddd4' }, other.token);
  assert.equal(refused.code, 'client_id_proof_required');
  assert.notEqual(mine.node_id, other.node_id);
});

test('a garbage bearer is not proof either', async () => {
  const env = createEnv({ MISAKANET_CLIENT_ID_PROOF: 'strict' });
  await register(env, { client_id: 'proof-client-fff6' });
  const refused = await register(env, { client_id: 'proof-client-fff6' }, 'mcp_made_up_token');
  assert.equal(refused.code, 'client_id_proof_required');
});

test('a fresh registration is unaffected by strict mode', async () => {
  const env = createEnv({ MISAKANET_CLIENT_ID_PROOF: 'strict' });
  const fresh = await register(env, { client_id: 'proof-client-ggg7' });
  assert.equal(fresh.reused, false);
  assert.ok(String(fresh.token).startsWith('mcp_'));
});
