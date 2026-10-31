// A one-time pairing code must be redeemable exactly once (#audit 2026-10-31).
//
// The handler used to read the KV row, check `status === "pending"`, then write `used` — three steps
// with two gaps. The audit drove two concurrent `/mcp/pair` requests through this file's own handler
// with an in-memory KV and got **two 200s with two distinct tokens**, while a sequential second attempt
// correctly got 409. The claim below is the fix: a primary-key insert that exactly one writer wins.
import test from 'node:test';
import assert from 'node:assert/strict';

import { claimOnce } from './register-proxy-sw.js';

/** A D1 stub with the one property that matters: a duplicate key is a constraint error, not an upsert. */
function fakeD1() {
  const rows = new Map();
  const statements = [];
  return {
    rows,
    statements,
    prepare(sql) {
      const record = { sql, args: [], meta: { changes: 0 } };
      statements.push(record);
      return {
        bind(...args) { record.args = args; return this; },
        async run() {
          if (sql.includes('CREATE TABLE')) return { meta: { changes: 0 } };
          if (sql.includes('INSERT INTO kv_store')) {
            const [key, value] = record.args;
            if (rows.has(key)) return { meta: { changes: 0 } };  // ON CONFLICT DO NOTHING
            rows.set(key, value);
            return { meta: { changes: 1 } };
          }
          return { meta: { changes: 0 } };
        },
      };
    },
  };
}

test('one claim succeeds and every later one fails', async () => {
  const d1 = fakeD1();
  const env = { MISAKANET_D1: d1 };
  assert.equal(await claimOnce(env, 'pair_claim:ABC123', '{}'), true);
  assert.equal(await claimOnce(env, 'pair_claim:ABC123', '{}'), false);
  assert.equal(await claimOnce(env, 'pair_claim:ABC123', '{}'), false);
});

test('two concurrent claims cannot both win', async () => {
  const d1 = fakeD1();
  const env = { MISAKANET_D1: d1 };
  const results = await Promise.all([
    claimOnce(env, 'pair_claim:XYZ789', '{}'),
    claimOnce(env, 'pair_claim:XYZ789', '{}'),
  ]);
  assert.equal(results.filter(Boolean).length, 1, results);
});

test('distinct codes do not block each other', async () => {
  const d1 = fakeD1();
  const env = { MISAKANET_D1: d1 };
  assert.equal(await claimOnce(env, 'pair_claim:AAA111', '{}'), true);
  assert.equal(await claimOnce(env, 'pair_claim:BBB222', '{}'), true);
});

test('without D1 the claim refuses instead of pretending', async () => {
  // KV has no conditional write. A deployment with only KV cannot make this atomic, and the caller has
  // to know that rather than receive a second token that looks legitimate.
  assert.equal(await claimOnce({}, 'pair_claim:CCC333', '{}'), false);
});

test('a D1 error is a failed claim, not a crash', async () => {
  const env = { MISAKANET_D1: { prepare() { throw new Error('d1 down'); } } };
  assert.equal(await claimOnce(env, 'pair_claim:DDD444', '{}'), false);
});
