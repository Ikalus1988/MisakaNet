// The 401 must tell the caller how to recover, in the body it actually receives.
//
// The user-visible symptom this pins (measured against production 2026-10-13): a developer whose
// token expired gets `{"code":-32000,"message":"Unauthorized"}` and nothing else. The SDK behind
// DeepSeek Harness classifies that as a *transport* fault and retries rather than recovering (the
// same shape as the `server/discover` bug at `mcp-anonymous-read.test.mjs:161`), so the agent
// never re-registers — and the person's report is "registration failed, I can't use MisakaNet".
//
// That is a dead end the server already knows the way out of: `misakanet_register` with the same
// `client_id` returns the same node and a fresh token (`reused: true`, measured). The gap was
// purely that the 401 did not say so.
//
// Run: node --test workers/mcp-auth-error-is-actionable.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const SHARED_TOKEN = testToken('auth-hint');

function createEnv() {
  const store = new Map();
  return {
    MCP_TOKEN: SHARED_TOKEN,
    MCP_VERSION: 'auth-hint-test',
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

// A Bearer-gated tool: `misakanet_search` is public, so it would never reach the auth gate and the
// test would pass while measuring nothing.
function call(env, token) {
  const headers = {
    'Content-Type': 'application/json',
    'MCP-Protocol-Version': '2025-06-18',
    'CF-Connecting-IP': '203.0.113.42',
  };
  if (token !== undefined) headers.Authorization = `Bearer ${token}`;
  return worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers,
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_preflight', arguments: { intent: 'rm -rf build/' } },
    }),
  }), env);
}

async function bodyOf(response) {
  return { status: response.status, body: await response.json() };
}

test('an expired token is answered with a recovery the caller can act on', async () => {
  const env = createEnv();
  // The real shape: the caller presents a well-formed `mcp_` token whose stored expiry has passed.
  env.MISAKANET_KV._store.set('mcp_token:mcp_expired_for_the_test', JSON.stringify({
    expires: '2020-01-01T00:00:00.000Z',
    node_id: 'Misaka00001',
  }));

  const { status, body } = await bodyOf(await call(env, 'mcp_expired_for_the_test'));

  assert.equal(status, 401);
  assert.equal(body.error.data.reason, 'token_invalid_or_expired');
  assert.equal(body.error.data.recovery, 'misakanet_register',
    'the error must name the call that fixes it, because the SDK retries a bare 401 forever');
  assert.match(body.error.data.recovery_hint, /client_id/,
    'the hint is useless if it does not say what makes re-registration return the *same* node');
});

test('a missing token says so, distinctly from an expired one', async () => {
  const { status, body } = await bodyOf(await call(createEnv()));
  assert.equal(status, 401);
  assert.equal(body.error.data.reason, 'no_token_provided');
  assert.equal(body.error.data.recovery, 'misakanet_register');
});

test('the recovery survives the production debug level', async () => {
  // `addDebugContext` returns the bare object when DEBUG_LEVEL < 1, which is production — so a hint
  // placed inside it would be invisible exactly where it is needed. This env sets no debug level.
  const env = createEnv();
  assert.equal(env.DEBUG_LEVEL, undefined, 'this test is only meaningful with debug off');
  const { body } = await bodyOf(await call(env, 'mcp_also_invalid'));
  assert.ok(body.error.data, 'error.data disappeared — was the hint moved inside `debug`?');
  assert.equal(body.error.debug, undefined, 'debug context must not appear in production');
});

test('code and message are unchanged, because clients match on them', async () => {
  const { body } = await bodyOf(await call(createEnv(), 'mcp_invalid'));
  assert.equal(body.error.code, -32000);
  assert.equal(body.error.message, 'Unauthorized');
});

test('the token itself is never echoed back', async () => {
  const secret = 'mcp_this_must_not_appear_in_the_response';
  const { body } = await bodyOf(await call(createEnv(), secret));
  assert.doesNotMatch(JSON.stringify(body), new RegExp(secret),
    'the rejected token must not be reflected, not even for debugging');
});

test('a valid token is not sent down this path at all', async () => {
  // Guards the guard: if the auth gate broke and rejected everything, the four assertions above
  // would still pass while the endpoint was unusable.
  const env = createEnv();
  const response = await call(env, SHARED_TOKEN);
  assert.notEqual(response.status, 401, 'a valid token must not produce a 401');
});
