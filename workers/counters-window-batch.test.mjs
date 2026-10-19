// The counters series must cost ONE query for the window, not days × classes.
//
// Measured 2026-10-19 from the CF dashboard: 6.24M D1 rows read in a day. `/api/activity/history` was
// 7 days × 4 classes = 28 separate `counters` point reads, and the funnel series 7 more, per uncached
// load. The window is a contiguous `period` range under one `scope`, so the happy path is a single
// `BETWEEN`; the per-day loop stays as the fallback (it is the path that consults KV).
//
// This file pins both halves: the batch is what runs, and a batch that cannot answer falls back
// rather than reporting a quiet week.
//
// Run: node --test workers/counters-window-batch.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { readActivitySeries, readFunnelSeries, utcDayKey } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('counters-batch');

/**
 * A D1 stand-in that answers BOTH shapes and counts them, so the assertion is "one query" rather
 * than "the numbers look plausible". `failWindow` makes the range query throw, which is how the
 * fallback gets exercised without pretending the table is empty.
 */
function createBatchD1({ seed, failWindow = false }) {
  const queries = [];
  const rows = new Map(Object.entries(seed || {})); // `${scope}|${bucket}|${period}` -> count
  return {
    queries,
    prepare(sql) {
      const stmt = {
        _bound: [],
        bind(...args) { stmt._bound = args; return stmt; },
        async all() {
          if (/BETWEEN/i.test(sql)) {
            queries.push("window");
            if (failWindow) throw new Error("boom");
            const [scope, from, to] = stmt._bound;
            const results = [];
            for (const [key, count] of rows) {
              const [s, bucket, period] = key.split("|");
              if (s === scope && period >= from && period <= to) results.push({ bucket, period, count });
            }
            return { results };
          }
          if (/SELECT count FROM counters/i.test(sql)) {
            queries.push("point");
            const [scope, bucket, period] = stmt._bound;
            const value = rows.get(`${scope}|${bucket}|${period}`);
            return value === undefined ? { results: [] } : { results: [{ count: value }] };
          }
          queries.push("other");
          return { results: [] };
        },
        async run() { return { success: true }; },
      };
      return stmt;
    },
  };
}

function seed(thing, span, base) {
  const out = {};
  for (let i = 0; i < span; i++) {
    const day = utcDayKey(i);
    for (const [bucket, n] of Object.entries(base)) out[`${thing}|${bucket}|${day}`] = n + i;
  }
  return out;
}

const TRAFFIC = seed("traffic", 10, { mcp: 100, agent: 3, crawler: 1, pageview: 2 });
const FUNNEL = seed("funnel", 10, { visit: 5, register: 2, authorize: 0, pair: 0, search: 4 });
const envWith = (d1) => ({ MISAKANET_D1: d1, MCP_TOKEN: TOKEN });

test('a 7-day traffic series is one range query, and the numbers are its rows', async () => {
  const d1 = createBatchD1({ seed: TRAFFIC });
  const series = await readActivitySeries(envWith(d1), 7);

  assert.equal(d1.queries.filter(q => q === "window").length, 1, `queries: ${d1.queries}`);
  assert.equal(d1.queries.filter(q => q === "point").length, 0, "the per-day loop must not run");
  assert.equal(series.length, 7);
  assert.equal(series[series.length - 1].date, utcDayKey(0));
  assert.equal(series[series.length - 1].calls.mcp, 100, "today is i=0, so it carries the base");
  assert.equal(series[series.length - 1].total, 100 + 3 + 1 + 2);
});

test('a 7-day funnel series is one range query too', async () => {
  const d1 = createBatchD1({ seed: FUNNEL });
  const series = await readFunnelSeries(envWith(d1), 7);

  assert.equal(d1.queries.filter(q => q === "window").length, 1, `queries: ${d1.queries}`);
  assert.equal(d1.queries.filter(q => q === "point").length, 0);
  assert.equal(series[series.length - 1].visit, 5, "today is i=0, so it carries the base");
});

test('a batch that cannot answer falls back to the per-day reader instead of a quiet week', async () => {
  const d1 = createBatchD1({ seed: TRAFFIC, failWindow: true });
  const series = await readActivitySeries(envWith(d1), 7);

  assert.equal(d1.queries.filter(q => q === "window").length, 1);
  assert.equal(d1.queries.filter(q => q === "point").length, 7 * 4, "the fallback is one read per class per day");
  assert.equal(series[series.length - 1].total > 0, true, "the fallback still returns the data");
});

test('a batch that returns nothing is treated as unreadable, not as zero traffic', async () => {
  const empty = createBatchD1({ seed: {} });
  const series = await readActivitySeries(envWith(empty), 7);
  assert.equal(series.every(day => day.total === 0), true,
    "nothing recorded here either way, but the fallback must have run first");
  assert.equal(empty.queries.filter(q => q === "point").length, 7 * 4,
    "an all-zero window from the batch must still consult the per-day path");
});
