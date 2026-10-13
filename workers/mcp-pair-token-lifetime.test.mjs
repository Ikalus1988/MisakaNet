// `/mcp/pair` had **no test at all** until this file — which is how it went on granting a 24-hour
// token while `misakanet_register` granted 30 days and `AGENTS.md` §3.3 promised 30.
//
// Measured against production 2026-10-13: `POST /mcp/pair` answered `expires_in: 86400`. The
// `/start` page is the path a *new human user* takes (`/connect` → `/start` → paste the code), so
// the page onboarding handed out a token 30× shorter than the documented one. A day later the
// caller is refused, and the reported symptom is "registration failed, I can't use MisakaNet".
// #2084 states it from the other side: "agent loses token after 24h silent period;
// misakanet_register returns a brand-new node_id every cold-start".
//
// These tests pin the *contract* (advertised == stored == documented) rather than the number, so
// the number can move once, in one place, without the paths drifting apart again.
//
// Run: node --test workers/mcp-pair-token-lifetime.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const THIRTY_DAYS = 86400 * 30;

function createEnv() {
  const store = new Map();
  return {
    MCP_TOKEN: testToken('pair-lifetime'),
    MCP_VERSION: 'pair-lifetime-test',
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) {
        store.set(key, value);
      },
      _store: store,
    },
  };
}

async function getCode(env) {
  const response = await worker.fetch(
    new Request('https://misakanet.org/mcp/connect', { method: 'POST' }), env);
  assert.equal(response.status, 200, 'connect must hand out a pairing code');
  const { code, expires_in } = await response.json();
  assert.ok(code, 'no code was issued, so the rest of this file would measure nothing');
  assert.equal(expires_in, 600, 'the *code* is the short-lived part, and it stays short-lived');
  return code;
}

async function pair(env, code) {
  const response = await worker.fetch(new Request('https://misakanet.org/mcp/pair', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  }), env);
  return { status: response.status, body: await response.json() };
}

test('the paired token is advertised with the documented lifetime, not a day', async () => {
  const env = createEnv();
  const { status, body } = await pair(env, await getCode(env));
  assert.equal(status, 200, JSON.stringify(body));
  assert.equal(body.expires_in, THIRTY_DAYS,
    'the page onboarding must not grant a shorter-lived credential than misakanet_register does');
});

test('the advertised lifetime is the one actually stored', async () => {
  // The defect was invisible in the response alone: 86400 looks like a considered choice. What made
  // it a bug is that `AGENTS.md` and the register path both said 30 days. So assert the agreement,
  // not the number.
  const env = createEnv();
  const { body } = await pair(env, await getCode(env));

  const stored = JSON.parse(env.MISAKANET_KV._store.get(`mcp_token:${body.token}`));
  assert.ok(stored, 'the token was never stored, so the caller would fail on its next call');
  const storedSeconds = (new Date(stored.expires).getTime() - Date.now()) / 1000;
  assert.ok(Math.abs(storedSeconds - body.expires_in) < 120,
    `advertised ${body.expires_in}s but stored ${Math.round(storedSeconds)}s — the response and `
    + 'the record disagree, which is how a client ends up discarding a token that still works');
});

test('a freshly paired token authenticates on its next use', async () => {
  // The end-to-end half: the whole point is that the developer can use MisakaNet afterwards. A
  // token that is advertised correctly but rejected anyway would pass both tests above.
  const env = createEnv();
  const { body } = await pair(env, await getCode(env));

  const response = await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '203.0.113.43',
      Authorization: `Bearer ${body.token}`,
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_preflight', arguments: { intent: 'rm -rf build/' } },
    }),
  }), env);

  assert.notEqual(response.status, 401, 'the token just issued was refused on its first use');
});
