// `client_id` is a key, not just a name (#2083).
//
// The register reuse branch returns the node's stored token to whoever presents the matching
// `client_id` — that is the renewal an agent depends on, and it stays. What was wrong was the
// description: two code comments and the tool description said "knowing someone's client_id grants
// nothing", and the guidance told callers to build it from "a workspace/hostname id", i.e. from values
// that are guessable and frequently public.
//
// Decided 2026-09-23 under the friction rule: the API behaves exactly as before (no extra step, no
// token ceremony added), the *claims* become true, and the advice moves to a random UUID — the same
// effort for the caller, strictly better secrecy.
//
// Run: node --test workers/client-id-is-a-key.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = 'mcp_' + testToken('client-id');
const CLIENT_ID = '8f14e45f-2b1c-4f3a-9d2e-7c6b5a4d3e2f';

function createEnv() {
  const store = new Map([['node_counter', '10050']]);
  return {
    _store: store,
    REGISTER_TOKEN: testToken('client-id-register'),
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

async function callTool(name, args, env) {
  const res = await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '198.51.100.' + (Math.floor(Math.random() * 200) + 1),
    },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name, arguments: args } }),
  }), env);
  const body = await res.json();
  return body?.result?.structuredContent || body?.result || {};
}

async function toolsList(env) {
  const res = await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '198.51.100.9' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/list' }),
  }), env);
  return (await res.json())?.result?.tools || [];
}

test('a second call with the same client_id hands back the same token', async () => {
  // This is the behaviour the documentation has to describe. If it ever changes, this test fails and
  // the description is what needs updating — not the other way round.
  const env = createEnv();
  const first = await callTool('misakanet_register', { agent_type: 'codex', client_id: CLIENT_ID }, env);
  assert.ok(first.token, `registration returned no token: ${JSON.stringify(first)}`);

  const second = await callTool('misakanet_register', { agent_type: 'codex', client_id: CLIENT_ID }, env);
  assert.equal(second.token, first.token,
    'the same client_id must renew the same node — that is the contract the description states');
  assert.equal(second.node_id, first.node_id);
  assert.equal(second.reused, true);
});

test('the tool description describes that, and tells the caller to keep the value private', async () => {
  const tools = await toolsList(createEnv());
  const register = tools.find((t) => t.name === 'misakanet_register');
  assert.ok(register, 'misakanet_register is not exposed');
  const description = register.description || '';

  assert.ok(!/grants nothing/i.test(description),
    'the description still claims that knowing a client_id grants nothing, which the reuse branch contradicts');
  assert.ok(/random UUID/i.test(description),
    'the guidance should point at a random UUID rather than a hostname or workspace id');
  assert.ok(/keep it private|Treat client_id|don't publish it/i.test(description),
    'the description must say the value is secret material, since presenting it returns the token');
  assert.ok(!/workspace id or hostname/i.test(description),
    'the old low-entropy suggestion is still there');
});
