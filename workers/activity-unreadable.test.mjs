// "The counters store refused" and "no calls that day" must not render the same.
//
// Measured 2026-10-19: with D1's row quota spent, the activity panel showed six zero days and one real
// day. The rows were still in the store — the heartbeat had read 2026-10-17 that morning — the reads
// were being refused, and `readTrafficCount` turned that into 0. #3544: the day now carries the
// classes it could not read, so the panel can draw a gap instead of a zero.
//
// Run: node --test workers/activity-unreadable.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { readTrafficBreakdown, resetCountersReadState } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('activity-unreadable');
const QUOTA = new Error("D1_ERROR: Your account has exceeded D1's free tier daily row read limit.");
const DAY = '2026-10-19';

function refusingD1() {
  const fail = async () => { throw QUOTA; };
  const stmt = { bind() { return stmt; }, all: fail, run: fail, first: fail, raw: fail };
  return { prepare() { return stmt; }, exec: fail, batch: fail };
}

function answeringD1(counts) {
  const stmt = {
    bind(...args) { stmt.args = args; return stmt; },
    async all() { return { results: [{ count: counts[stmt.args[1]] ?? 0 }] }; },
    async run() { return { success: true }; },
  };
  return { prepare() { return stmt; } };
}

test('a refused read names the classes it could not read', async () => {
  resetCountersReadState();
  const day = await readTrafficBreakdown(
    { MISAKANET_D1: refusingD1(), MCP_TOKEN: TOKEN },
    DAY,
  );
  assert.deepEqual(day.unreadable, ['mcp', 'agent', 'crawler', 'pageview'],
    'every class failed, so every class is named');
  assert.equal(day.total, 0, 'the total is a lower bound, not a fabricated count');
});

test('a healthy read carries no unreadable key at all', async () => {
  resetCountersReadState();
  const day = await readTrafficBreakdown(
    { MISAKANET_D1: answeringD1({ mcp: 7, agent: 1, crawler: 2, pageview: 3 }), MCP_TOKEN: TOKEN },
    DAY,
  );
  assert.equal('unreadable' in day, false, 'an empty list is not a fact worth carrying');
  assert.equal(day.total, 13);
});

test('a zero day that was actually read is not labelled unreadable', async () => {
  resetCountersReadState();
  const day = await readTrafficBreakdown(
    { MISAKANET_D1: answeringD1({}), MCP_TOKEN: TOKEN },
    DAY,
  );
  assert.equal('unreadable' in day, false, 'D1 answered "no rows", which is a real zero');
  assert.equal(day.total, 0);
});
