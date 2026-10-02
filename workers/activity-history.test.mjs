// The activity *trend* route: our own per-day counters read back as a series (issue #2521, option A).
//
// The homepage panel shows one day. This route is the week under it, and it is the half of #2521 that
// needs no Cloudflare credential: the counters are already written per day per class, so a trend is
// `readTrafficBreakdown` called once per day and nothing else — no new counter family, no ring buffer,
// no edge metric, no token.
//
// What this file pins:
//   * the shape is its own contract (`generated_at`/`source`/`window`/`series`), and it is the same
//     shape `scripts/sync_activity_series.py` publishes to `docs/data/activity-series.json` — one
//     producer contract for the live route and the static fallback, like the single-day pair above it;
//   * the window is clamped (2–30) and is part of the cache key, so `?days=30` cannot poison the
//     7-day entry and `?days=365` cannot turn one request into a year of reads;
//   * a series that is zero in *every* day is refused (503) rather than published — seven zero days is
//     a reader that cannot see the counters, and the panel must degrade to "no chart", not draw one;
//   * it is anonymous-only (a shared cache entry is only safe on a route that cannot read the caller),
//     and it publishes no per-client counts and no failed-query text;
//   * every day's `total` is the sum of its own classes and the dates ascend without gaps or repeats —
//     the properties a chart's x-axis depends on.
//
// Run: node --test workers/activity-history.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, {
  ACTIVITY_CACHE_CONTROL,
  ACTIVITY_HISTORY_DEFAULT_DAYS,
  ACTIVITY_HISTORY_MAX_DAYS,
  ACTIVITY_HISTORY_MIN_DAYS,
  ACTIVITY_SOURCE,
  readActivitySeries,
  readTrafficBreakdown,
  utcDayKey,
} from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TODAY = utcDayKey(0);
const TOKEN = testToken('activity-history');

const SERIES_KEYS = ['generated_at', 'source', 'window', 'series'];
const DAY_KEYS = ['date', 'total', 'calls'];
const CALL_CLASSES = ['agent', 'crawler', 'mcp', 'pageview'];

/** Minimal D1 stand-in: the counters SELECT only, seeded per (class, day). Cf. activity-route.test.mjs. */
function createCountersD1(seed = {}) {
  const rows = new Map(Object.entries(seed)); // `${scope}|${bucket}|${period}` -> count
  return {
    rows,
    prepare(sql) {
      const stmt = {
        _bound: [],
        bind(...args) { stmt._bound = args; return stmt; },
        async all() {
          if (/SELECT count FROM counters/i.test(sql)) {
            const [scope, bucket, period] = stmt._bound;
            const value = rows.get(`${scope}|${bucket}|${period}`);
            return value === undefined ? { results: [] } : { results: [{ count: value }] };
          }
          return { results: [] };
        },
        async run() { return { success: true }; },
      };
      return stmt;
    },
  };
}

/**
 * Seeded counts for `span` days ending today: `mcp` climbs by 100 a day and the rest are fixed, so a
 * test can assert *which* day a bar is without the numbers being the point.
 */
function seedDays(span) {
  const seed = {};
  for (let i = 0; i < span; i++) {
    const day = utcDayKey(i);
    seed[`traffic|mcp|${day}`] = 1000 + i * 100;
    seed[`traffic|agent|${day}`] = 10;
    seed[`traffic|crawler|${day}`] = 2;
    seed[`traffic|pageview|${day}`] = 4;
  }
  return seed;
}

function createEnv(options = {}) {
  return {
    MCP_TOKEN: TOKEN,
    ...(options.d1 === null ? {} : { MISAKANET_D1: options.d1 || createCountersD1(seedDays(30)) }),
    ...(options.kv === false ? {} : {
      MISAKANET_KV: {
        async get() { return null; },
        async put() { return undefined; },
        async delete() { return undefined; },
      },
    }),
  };
}

function request(path, headers = {}) {
  return new Request(`https://misakanet.org${path}`, { headers });
}

/** `caches.default` is absent under `node --test`; install the two methods the route uses. */
function withFakeCache(run) {
  const store = new Map();
  const before = Object.getOwnPropertyDescriptor(globalThis, 'caches');
  globalThis.caches = {
    default: {
      async match(key) {
        const hit = store.get(key.url);
        return hit ? hit.clone() : undefined;
      },
      async put(key, response) { store.set(key.url, response.clone()); },
    },
  };
  return Promise.resolve().then(run).finally(() => {
    if (before) Object.defineProperty(globalThis, 'caches', before);
    else delete globalThis.caches;
  });
}

// ── the shape the panel and the snapshot writer share ────────────────────────────────────────────

test('the route answers in the series shape the snapshot writer publishes', async () => {
  const response = await worker.fetch(request('/api/activity/history'), createEnv());
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.deepEqual(Object.keys(body).sort(), [...SERIES_KEYS].sort(), JSON.stringify(body));
  assert.equal(body.source, ACTIVITY_SOURCE);
  assert.deepEqual(Object.keys(body.window).sort(), ['days', 'from', 'to']);
});

test('the window is the last N days, oldest first, with no gap and no repeat', async () => {
  const body = await (await worker.fetch(request('/api/activity/history?days=7'), createEnv())).json();
  assert.equal(body.window.days, 7);
  assert.equal(body.series.length, 7);
  assert.equal(body.series[6].date, TODAY, 'the newest day is today');
  assert.equal(body.series[0].date, utcDayKey(6), 'the oldest day is six days back');
  assert.deepEqual(body.window.from, body.series[0].date);
  assert.deepEqual(body.window.to, body.series[6].date);
  for (let i = 0; i < 7; i++) {
    assert.equal(body.series[i].date, utcDayKey(6 - i), `entry ${i} is not the day it claims`);
    assert.deepEqual(Object.keys(body.series[i]).sort(), [...DAY_KEYS].sort());
  }
});

test('every day totals its own classes, and the classes are the four the page labels', async () => {
  const body = await (await worker.fetch(request('/api/activity/history?days=7'), createEnv())).json();
  for (const day of body.series) {
    assert.deepEqual(Object.keys(day.calls).sort(), [...CALL_CLASSES].sort(), JSON.stringify(day));
    assert.equal(day.total, Object.values(day.calls).reduce((a, b) => a + b, 0),
      `${day.date}: a total that disagrees with its parts is what a truncated read looks like`);
    for (const value of Object.values(day.calls)) {
      assert.ok(Number.isInteger(value) && value >= 0, `${day.date}: ${value} is not a count`);
    }
  }
});

test("the trend and today's headline read the same reader and cannot disagree", async () => {
  // The one thing the two routes must never do: the panel puts them on screen together, so a second
  // copy of the read loop would be a second definition of "today's traffic".
  const env = createEnv();
  const body = await (await worker.fetch(request('/api/activity/history?days=2'), env)).json();
  const direct = await readTrafficBreakdown(env, TODAY);
  assert.deepEqual(body.series[1].calls, direct.breakdown);
  assert.equal(body.series[1].total, direct.total);
});

test('generated_at is an ISO-8601 instant without milliseconds', async () => {
  const body = await (await worker.fetch(request('/api/activity/history'), createEnv())).json();
  assert.match(body.generated_at, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
});

// ── the window clamp ─────────────────────────────────────────────────────────────────────────────

test('the default window is the one the panel draws', async () => {
  const body = await (await worker.fetch(request('/api/activity/history'), createEnv())).json();
  assert.equal(body.window.days, ACTIVITY_HISTORY_DEFAULT_DAYS);
  assert.equal(body.series.length, ACTIVITY_HISTORY_DEFAULT_DAYS);
});

test('`days` is clamped, not honoured blindly — a year of reads from one request is not a feature', async () => {
  const tooMany = await (await worker.fetch(request('/api/activity/history?days=365'), createEnv())).json();
  assert.equal(tooMany.window.days, ACTIVITY_HISTORY_MAX_DAYS);
  assert.equal(tooMany.series.length, ACTIVITY_HISTORY_MAX_DAYS);

  const tooFew = await (await worker.fetch(request('/api/activity/history?days=0'), createEnv())).json();
  assert.equal(tooFew.window.days, ACTIVITY_HISTORY_MIN_DAYS);

  const garbage = await (await worker.fetch(request('/api/activity/history?days=all'), createEnv())).json();
  assert.equal(garbage.window.days, ACTIVITY_HISTORY_DEFAULT_DAYS, 'unparseable is the default, not a 500');
});

// ── the TTL ──────────────────────────────────────────────────────────────────────────────────────

test('the response carries the same minutes-scale TTL as /api/activity', async () => {
  const response = await worker.fetch(request('/api/activity/history'), createEnv());
  assert.equal(response.headers.get('Cache-Control') || '', ACTIVITY_CACHE_CONTROL);
});

test('a second request inside the TTL is served from the edge cache, not recomputed', async () => {
  await withFakeCache(async () => {
    const env = createEnv();
    const first = await (await worker.fetch(request('/api/activity/history'), env)).json();
    env.MISAKANET_D1.rows.set(`traffic|mcp|${TODAY}`, 99999);
    const second = await (await worker.fetch(request('/api/activity/history'), env)).json();
    assert.deepEqual(second, first, 'the cached body was not reused');
  });
});

test('the window is part of the cache key — 7-day and 30-day answers do not share an entry', async () => {
  await withFakeCache(async () => {
    const env = createEnv();
    const week = await (await worker.fetch(request('/api/activity/history?days=7'), env)).json();
    const month = await (await worker.fetch(request('/api/activity/history?days=30'), env)).json();
    assert.equal(week.series.length, 7);
    assert.equal(month.series.length, 30);
    const weekAgain = await (await worker.fetch(request('/api/activity/history?days=7'), env)).json();
    assert.deepEqual(weekAgain, week, 'the 30-day answer overwrote the 7-day entry');
  });
});

test('with no cache available the route still answers', async () => {
  assert.equal(typeof globalThis.caches, 'undefined');
  const response = await worker.fetch(request('/api/activity/history'), createEnv());
  assert.equal(response.status, 200);
  assert.equal((await response.json()).series.length, ACTIVITY_HISTORY_DEFAULT_DAYS);
});

// ── what must not be published ───────────────────────────────────────────────────────────────────

test('it is anonymous-only: the maintainer token changes nothing', async () => {
  const anonymous = await (await worker.fetch(request('/api/activity/history'), createEnv())).json();
  const maintainer = await (await worker.fetch(
    request('/api/activity/history', { Authorization: `Bearer ${TOKEN}` }), createEnv())).json();
  assert.deepEqual(maintainer, anonymous, 'the body varies by caller — a shared cache entry is not safe');
});

test('no per-client counts and no failed-query text are published', async () => {
  const text = await (await worker.fetch(request('/api/activity/history'), createEnv())).text();
  for (const field of ['mcpClients', 'knowledge_gaps', 'top_searches', 'withheld']) {
    assert.ok(!text.includes(field), `/api/activity/history published ${field}: ${text}`);
  }
});

// ── degradation ──────────────────────────────────────────────────────────────────────────────────

test('with no counter store at all the route says so instead of inventing a zero series', async () => {
  const response = await worker.fetch(request('/api/activity/history'), createEnv({ d1: null, kv: false }));
  assert.equal(response.status, 503);
  const body = await response.json();
  assert.ok(body.error, JSON.stringify(body));
  assert.equal(body.series, undefined, 'an all-zero series would render as a flat, true-looking week');
});

test('a window where every day reads zero is refused — that is an unreadable store, not a quiet week', async () => {
  const env = createEnv({ d1: createCountersD1({}) });
  const response = await worker.fetch(request('/api/activity/history'), env);
  assert.equal(response.status, 503);
  const body = await response.json();
  assert.equal(body.code, 'counters_unreadable', JSON.stringify(body));
  assert.equal(body.series, undefined, 'the panel must show no chart, so there must be nothing to draw');
});

test('one non-zero day is enough — a day with no rows is a real zero and is kept', async () => {
  // Only today has counts; the other six days are absent rows. Dropping them would redraw the x-axis
  // and hide the quiet stretch rather than report it.
  const onlyToday = {};
  for (const cls of ['mcp', 'agent', 'crawler', 'pageview']) onlyToday[`traffic|${cls}|${TODAY}`] = 5;
  const body = await (await worker.fetch(
    request('/api/activity/history?days=7'), createEnv({ d1: createCountersD1(onlyToday) }))).json();
  assert.equal(body.series.length, 7);
  assert.equal(body.series[6].total, 20);
  assert.deepEqual(body.series.slice(0, 6).map(d => d.total), [0, 0, 0, 0, 0, 0]);
});

test('readActivitySeries is the reader the route uses, so the file writer can assert against it', async () => {
  const env = createEnv();
  const direct = await readActivitySeries(env, 3);
  assert.deepEqual(direct.map(d => d.date), [utcDayKey(2), utcDayKey(1), utcDayKey(0)]);
  assert.equal(direct[2].total, 1000 + 10 + 2 + 4);
});
