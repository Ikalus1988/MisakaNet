import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import {
  IDENTITY_AURA,
  getIdentityAura,
} from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

// One token for the whole file: the helpers below build requests from it.
const TOKEN = testToken('identity-aura');

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
  const env = { MCP_TOKEN: TOKEN, MISAKANET_KV: createFakeKV() };
  const aura = await getIdentityAura(env, TOKEN);
  assert.equal(aura, IDENTITY_AURA.static_token);
});

test('missing token falls back to the static badge (no KV needed)', async () => {
  const env = { MCP_TOKEN: TOKEN };
  const aura = await getIdentityAura(env, null);
  assert.equal(aura, IDENTITY_AURA.static_token);
});

test('no KV namespace falls back to the static badge', async () => {
  const env = { MCP_TOKEN: TOKEN };
  const aura = await getIdentityAura(env, TOKEN);
  assert.equal(aura, IDENTITY_AURA.static_token);
});

test('wrong static token without pairing identity falls back to basic badge', async () => {
  const env = { MCP_TOKEN: TOKEN, MISAKANET_KV: createFakeKV() };
  const aura = await getIdentityAura(env, 'wrong-token');
  assert.equal(aura, IDENTITY_AURA.basic);
});

// ── getIdentityAura: pairing token (basic) ──

test('pairing token with registered identity yields the failure-memory badge', async () => {
  const kv = createFakeKV({
    'mcp_token:mcp_test123': JSON.stringify({ ip: '203.0.113.7' }),
  });
  const env = { MCP_TOKEN: TOKEN, MISAKANET_KV: kv };
  const aura = await getIdentityAura(env, 'mcp_test123');
  assert.equal(aura, IDENTITY_AURA.basic);
});

test('pairing token without identity record falls back to the basic badge', async () => {
  const kv = createFakeKV({
    'mcp_token:mcp_test123': JSON.stringify({ ip: '203.0.113.7' }),
  });
  const env = { MCP_TOKEN: TOKEN, MISAKANET_KV: kv };
  const aura = await getIdentityAura(env, 'mcp_test123');
  assert.equal(aura, IDENTITY_AURA.basic);
});

// ── getIdentityAura: upgraded token ──

test('the upgraded badge has no producer, and the read that reached for it is gone (2026-09-24)', async () => {
  // The finding: `identity:<ip>` was read on every token-bearing MCP request and **written nowhere** —
  // not in this worker, not in a script, not in the docs. The badge was unreachable since the feature
  // shipped (9b7fe9813, 2026-08-08), and this test used to pass only because the fixture seeded the
  // key it was asking about. The read is removed; the constant stays, because it documents the intent
  // and `IDENTITY_AURA defines all three badge types` above asserts its text.
  //
  // To bring the feature back: add the writer for `identity:<ip>`, restore the read, and assert here
  // that a paired token returns `upgraded`. Until then this test is the note that says so.
  const source = readFileSync(new URL('./register-proxy-sw.js', import.meta.url), 'utf8');
  assert.ok(!source.includes('identity:${'),
    'the dead identity read is back — either wire a writer for it or remove it again');
  assert.ok(IDENTITY_AURA.upgraded.includes('AIM拡散力場'));
});

test('unknown pairing token falls back to the basic badge', async () => {
  const env = { MCP_TOKEN: TOKEN, MISAKANET_KV: createFakeKV() };
  const aura = await getIdentityAura(env, 'mcp_unknown');
  assert.equal(aura, IDENTITY_AURA.basic);
});
