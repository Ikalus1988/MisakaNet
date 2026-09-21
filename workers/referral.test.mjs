// The referral chain existed only inside the inviting machine (#1996).
//
// `scripts/referral.py --stats` counted invitations by grepping git history for the referral code in
// `misakanet/profile.json` — so it counted how many people had accidentally committed their own node
// state, and it stopped counting the day that file was untracked (#1991). A referral is a relation
// between two parties, and the worker did not know the word: registration accepted `agent_type` and
// `client_id` only.
//
// These tests drive the real HTTP path and pin five properties:
//
//   * a new node registered with a valid code records the relation on the node and counts it once;
//   * renewing the same node (same `client_id`) does **not** count again — otherwise every token
//     renewal would inflate the inviter's number, which is the kind of "looks like growth" a counter
//     must not produce;
//   * a code that is not code-shaped is ignored rather than fatal: an invitation is a courtesy, and
//     losing a registration over a malformed one would be the wrong trade;
//   * `GET /api/referrals` reads the number back, and answers 0 for a code nobody used;
//   * a bad query is rejected instead of being counted as a code.
//
// Run: node --test workers/referral.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const REGISTER_TOKEN = testToken('register-token');

/** KV: reads work, writes work, no quota. */
function kvStub(store = new Map()) {
  return {
    async get(key, type) {
      if (!store.has(key)) return null;
      const raw = store.get(key);
      return type === 'json' ? JSON.parse(raw) : raw;
    },
    async put(key, value) { store.set(key, value); },
    async delete(key) { store.delete(key); },
  };
}

/**
 * D1 that understands the two counter shapes the register path issues.
 *
 * Four bound args = the atomic counter upsert `(scope, bucket, period, delta)`; anything shorter is
 * the node counter, which spells its scope/bucket/period as literals.
 */
function d1Stub() {
  const kv = new Map();
  const counters = new Map();
  const k = (scope, bucket, period) => `${scope}|${bucket}|${period}`;
  return {
    _counters: counters,
    prepare(sql) {
      const stmt = {
        _bound: [],
        bind(...args) { stmt._bound = args; return stmt; },
        async run() {
          if (sql.includes('INSERT INTO kv_store')) {
            kv.set(String(stmt._bound[0]), { value: stmt._bound[1] });
            return { success: true };
          }
          if (sql.includes('INSERT INTO counters')) {
            const key = stmt._bound.length >= 4 ? k(stmt._bound[0], stmt._bound[1], stmt._bound[2]) : k('node', 'all', 'all-time');
            const delta = stmt._bound.length >= 4 ? Number(stmt._bound[3]) : 1;
            counters.set(key, (counters.get(key) || 0) + delta);
            return { success: true };
          }
          return { success: true };
        },
        async all() {
          if (sql.includes('SELECT value FROM kv_store')) {
            const row = kv.get(String(stmt._bound[0]));
            return row ? { results: [{ value: row.value }] } : { results: [] };
          }
          if (sql.includes('FROM counters')) {
            // Two callers: the node counter (no WHERE) and the referral read (scope/bucket/period).
            if (stmt._bound.length >= 1 && sql.includes('scope')) {
              const key = k('referral', String(stmt._bound[0]), 'all');
              return counters.has(key) ? { results: [{ count: counters.get(key) }] } : { results: [] };
            }
            const key = k('node', 'all', 'all-time');
            return counters.has(key) ? { results: [{ count: counters.get(key) }] } : { results: [] };
          }
          if (sql.includes('INSERT INTO counters') && sql.includes('RETURNING')) {
            const key = stmt._bound.length >= 4 ? k(stmt._bound[0], stmt._bound[1], stmt._bound[2]) : k('node', 'all', 'all-time');
            const delta = stmt._bound.length >= 4 ? Number(stmt._bound[3]) : 1;
            const next = (counters.get(key) || 0) + delta;
            counters.set(key, next);
            return { results: [{ count: next }] };
          }
          return { results: [] };
        },
      };
      return stmt;
    },
  };
}

function makeEnv() {
  const store = new Map();
  const d1 = d1Stub();
  return {
    _d1: d1,
    REGISTER_TOKEN,
    MISAKANET_KV: kvStub(store),
    MISAKANET_D1: d1,
  };
}

function call(env, name, args) {
  return worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json', Origin: 'https://misakanet.org' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name, arguments: args } }),
  }), env).then(async (r) => (await r.json()).result.structuredContent);
}

function referralCount(env, code) {
  return env._d1._counters.get(`referral|${code}|all`) || 0;
}

test('a new node registered with a code records the relation and counts it once', async () => {
  const env = makeEnv();
  const out = await call(env, 'misakanet_register', { agent_type: 'claude-code', client_id: 'client-referral-0001', referral_code: 'MDQIYJCP' });
  assert.match(out.node_id, /^Misaka\d+$/, JSON.stringify(out));
  assert.equal(out.referred_by, 'MDQIYJCP');
  assert.equal(out.referral_counted, true);
  assert.equal(referralCount(env, 'MDQIYJCP'), 1);
});

test('renewing the same node does not count the referral again', async () => {
  const env = makeEnv();
  const first = await call(env, 'misakanet_register', { agent_type: 'setup', client_id: 'client-referral-0002', referral_code: 'MDQIYJCP' });
  const again = await call(env, 'misakanet_register', { agent_type: 'setup', client_id: 'client-referral-0002', referral_code: 'MDQIYJCP' });
  assert.equal(again.node_id, first.node_id, 'the same client_id must come back as the same node');
  assert.equal(again.reused, true);
  assert.equal(referralCount(env, 'MDQIYJCP'), 1, 'a token renewal is not a new invitation');
});

test('a code that is not code-shaped never fails a registration', async () => {
  const env = makeEnv();
  for (const bad of ['a', 'has space', 'way-too-long-to-be-a-code', 'semi;colon']) {
    const out = await call(env, 'misakanet_register', { agent_type: 'setup', client_id: `client-bad-${bad.length}-x`, referral_code: bad });
    assert.ok(out.token, `registration must still succeed for referral_code=${JSON.stringify(bad)}`);
    assert.equal(out.referred_by, undefined);
    assert.equal(referralCount(env, bad), 0);
  }
});

test('the count is readable, and a code nobody used answers 0', async () => {
  const env = makeEnv();
  await call(env, 'misakanet_register', { agent_type: 'setup', client_id: 'client-referral-0003', referral_code: 'MDQIYJCP' });
  const used = await (await worker.fetch(new Request('https://misakanet.org/api/referrals?code=MDQIYJCP'), env)).json();
  assert.deepEqual(used, { code: 'MDQIYJCP', invited: 1, source: 'd1' });
  const unused = await (await worker.fetch(new Request('https://misakanet.org/api/referrals?code=NOBODYUSED'), env)).json();
  assert.deepEqual(unused, { code: 'NOBODYUSED', invited: 0, source: 'd1' });
});

test('a malformed query is rejected rather than counted as a code', async () => {
  const env = makeEnv();
  const res = await worker.fetch(new Request('https://misakanet.org/api/referrals?code=has%20space'), env);
  assert.equal(res.status, 400);
  const body = await res.json();
  assert.equal(body.code, 'invalid_code');
});
