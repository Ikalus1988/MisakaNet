// When D1 refuses counters reads, stop asking for a minute.
//
// Measured 2026-10-19: with the daily row quota spent, every load of the homepage (and of
// `/api/funnel`, `/api/activity/history`) still issued its 35 counters queries into a database that
// was refusing them. The lessons path has had a cooldown since 2026-10-17; the counters path had none,
// so an outage was also a self-inflicted traffic burst.
//
// Run: node --test workers/counters-read-cooldown.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import {
  countersReadable,
  readActivitySeries,
  readFunnelSeries,
  resetCountersReadState,
} from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('counters-cooldown');
const QUOTA = new Error(
  "D1_ERROR: Your account has exceeded D1's free tier daily row read limit.",
);

/** A D1 that fails every counters query and counts how many times it was asked. */
function refusingD1() {
  const state = { queries: 0 };
  const fail = async () => { state.queries += 1; throw QUOTA; };
  const stmt = { bind() { return stmt; }, all: fail, run: fail, first: fail, raw: fail };
  state.prepare = () => stmt;
  state.batch = fail;
  state.exec = fail;
  return state;
}

// The cool-down is off unless the deployment asks for it (see the worker's `countersCooldownMs`), so
// the test states the window it is exercising instead of inheriting a hidden default.
const env = (d1) => ({ MISAKANET_D1: d1, MCP_TOKEN: TOKEN, MISAKANET_COUNTERS_COOLDOWN_MS: '60000' });

test('one failing read silences the rest of the window', async () => {
  resetCountersReadState();
  const d1 = refusingD1();
  await readActivitySeries(env(d1), 7);
  const afterFirst = d1.queries;
  assert.ok(afterFirst > 0, 'the first attempt must actually query');
  assert.equal(countersReadable(), false, 'a failure must put the reader into its cool-down');

  await readActivitySeries(env(d1), 7);
  await readFunnelSeries(env(d1), 7);
  assert.equal(d1.queries, afterFirst,
    'while cooling down, page loads must not add a query each — that burst is what this fixes');
});

test('the cool-down clears, and the next read queries again', async () => {
  resetCountersReadState();
  const d1 = refusingD1();
  await readFunnelSeries(env(d1), 7);
  assert.equal(countersReadable(), false);
  resetCountersReadState();
  assert.equal(countersReadable(), true);
  const before = d1.queries;
  await readFunnelSeries(env(d1), 7);
  assert.ok(d1.queries > before, 'after the reset the reader must try D1 again');
});

test('a cool-down that never clears would be its own lie, so it is time-bounded', async () => {
  resetCountersReadState();
  const d1 = refusingD1();
  await readFunnelSeries(env(d1), 7);
  // The constant is one minute; asserting the bound rather than sleeping keeps this file fast and
  // still fails if someone makes the cooldown permanent.
  const started = Date.now();
  await readFunnelSeries(env(d1), 7);
  assert.ok(Date.now() - started < 1000, 'a cooled-down read must return without waiting on D1');
});
