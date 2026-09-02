import assert from 'node:assert/strict';
import test from 'node:test';
import {
  IDENTITY_AURA,
  getIdentityAura,
} from './register-proxy-sw.js';

function createFakeKV(seed = {}) {
  const store = new Map(Object.entries(seed));
  return {
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
    _store: store,
  };
}

// ── IDENTITY_AURA constants ──

test('IDENTITY_AURA defines all three badge types', () => {
  assert.equal(IDENTITY_AURA.static_token, '🧠 MisakaNet MCP — public read-only access.');
  assert.equal(IDENTITY_AURA.basic, '🧠 MisakaNet failure-memory connected.');
  assert.ok(IDENTITY_AURA.upgraded.includes('AIM拡散力場'));
});

// ── getIdentityAura: static token ──

test('static MCP_TOKEN yields the public read-only badge', async () => {
  const env = { MCP_TOKEN: 'static-secret-token', MISAKANET_KV: createFakeKV() };
  const aura = await getIdentityAura(env, 'static-secret-token');
  assert.equal(aura, IDENTITY_AURA.static_token);
});

test('missing token falls back to the static badge (no KV needed)', async () => {
  const env = { MCP_TOKEN: 'static-secret-token' };
  const aura = await getIdentityAura(env, null);
  assert.equal(aura, IDENTITY_AURA.static_token);
});

test('no KV namespace falls back to the static badge', async () => {
  const env = { MCP_TOKEN: 'static-secret-token' };
  const aura = await getIdentityAura(env, 'static-secret-token');
  assert.equal(aura, IDENTITY_AURA.static_token);
});

test('wrong static token without pairing identity falls back to basic badge', async () => {
  const env = { MCP_TOKEN: 'static-secret-token', MISAKANET_KV: createFakeKV() };
  const aura = await getIdentityAura(env, 'wrong-token');
  assert.equal(aura, IDENTITY_AURA.basic);
});

// ── getIdentityAura: pairing token (basic) ──

test('pairing token with registered identity yields the failure-memory badge', async () => {
  const kv = createFakeKV({
    'mcp_token:mcp_test123': JSON.stringify({ ip: '203.0.113.7' }),
    'identity:203.0.113.7': JSON.stringify({ status: 'basic' }),
  });
  const env = { MCP_TOKEN: 'static-secret-token', MISAKANET_KV: kv };
  const aura = await getIdentityAura(env, 'mcp_test123');
  assert.equal(aura, IDENTITY_AURA.basic);
});

test('pairing token without identity record falls back to the basic badge', async () => {
  const kv = createFakeKV({
    'mcp_token:mcp_test123': JSON.stringify({ ip: '203.0.113.7' }),
  });
  const env = { MCP_TOKEN: 'static-secret-token', MISAKANET_KV: kv };
  const aura = await getIdentityAura(env, 'mcp_test123');
  assert.equal(aura, IDENTITY_AURA.basic);
});

// ── getIdentityAura: upgraded token ──

test('upgraded identity yields the Japanese AIM拡散力場 badge', async () => {
  const kv = createFakeKV({
    'mcp_token:mcp_test123': JSON.stringify({ ip: '203.0.113.7' }),
    'identity:203.0.113.7': JSON.stringify({ status: 'upgraded' }),
  });
  const env = { MCP_TOKEN: 'static-secret-token', MISAKANET_KV: kv };
  const aura = await getIdentityAura(env, 'mcp_test123');
  assert.equal(aura, IDENTITY_AURA.upgraded);
  assert.ok(aura.includes('AIM拡散力場'));
});

test('unknown pairing token falls back to the basic badge', async () => {
  const env = { MCP_TOKEN: 'static-secret-token', MISAKANET_KV: createFakeKV() };
  const aura = await getIdentityAura(env, 'mcp_unknown');
  assert.equal(aura, IDENTITY_AURA.basic);
});
