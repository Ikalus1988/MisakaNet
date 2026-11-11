// #4640: the daily series is published as a trajectory, so its window has to be day-aligned.
//
// `WHERE created_at >= datetime('now','-7 days')` starts the window at the *current time* seven days
// ago. The oldest bucket therefore holds only the hours after that instant — and loses one more hour
// every hour the query runs — while the newest bucket is a partial day (the heartbeat already caveats
// that end). Measured: 2026-11-04 read 729 in the 11-10 heartbeat and 649 on 11-11, the difference
// being that morning's hours sliding out of the window.
//
// `datetime(date('now','-7 days'))` starts at midnight: the oldest day is whole and only the newest
// day is partial. This test pins the SQL, because the drift is invisible in any single response.
//
// Run: node --test workers/analytics-daily-window.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

function createD1(seen) {
  const rowsFor = (sql) => {
    if (/GROUP BY day/.test(sql)) return [{ day: '2026-11-04', n: 649 }];
    return [];
  };
  return {
    prepare(sql) {
      seen.push(sql);
      const stmt = {
        bind() { return stmt; },
        async all() { return { results: rowsFor(sql) }; },
        async first() { return rowsFor(sql)[0] || null; },
        async run() { return { success: true }; },
      };
      return stmt;
    },
  };
}

test('the daily series window starts at midnight, not at a rolling timestamp', async () => {
  const seen = [];
  const env = { MCP_TOKEN: testToken('analytics-daily-window'), MISAKANET_D1: createD1(seen) };
  const response = await worker.fetch(new Request('https://misakanet.org/api/analytics'), env);
  const body = await response.json();
  assert.ok(Array.isArray(body.daily_requests), 'the public aggregate must still carry daily_requests');

  const daily = seen.find((sql) => /GROUP BY day/.test(sql));
  assert.ok(daily, 'the daily query must run');
  assert.match(daily, /datetime\(date\('now'\s*,\s*'-7 days'\)\)/, daily);
  assert.doesNotMatch(daily, /datetime\('now'\s*,\s*'-7 days'\)/,
    'a rolling timestamp truncates the oldest bucket and drifts downward every hour (#4640)');
});
