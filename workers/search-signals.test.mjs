// Search hit-rate signals (#1779).
//
// Before this, a completed search left a trace only when it *missed* (the gap
// counter + the unsolved failure map), so the hit rate had no denominator. The
// search handler now writes one `search_signals` row per completed search —
// hits included — and `GET /api/search-signals/stats` serves the read-only
// solved/created_at stream that scripts/search_hit_rate.py aggregates.
//
// These tests drive the real HTTP search path with a D1 stub (the same approach
// as workers/intent-instrument.test.mjs and workers/d1-lesson-service.test.mjs)
// and assert both directions, plus the two properties that matter in production:
// recording is one insert per search, and a broken store cannot break a search.
//
// Run: node --test workers/search-signals.test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('search-signals');
const WORKER_SOURCE = readFileSync(new URL('./register-proxy-sw.js', import.meta.url), 'utf8');

// D1-shaped rows (sqlite stores tags as a JSON string) so the test exercises the
// projection the worker really serves, not the GitHub fallback shape.
const LESSONS = [
  {
    id: 'pip-timeout-mirror',
    title: 'pip install timeout',
    domain: 'python',
    status: 'published',
    tags: '["pip","network"]',
    path: 'lessons/core/pip-timeout-mirror.md',
    summary: 'pip install times out on slow networks.',
    problem: 'pip install times out behind a corporate proxy.',
    solution: 'Raise --default-timeout or use a mirror',
    updated: '2026-09-15T00:00:00Z',
    created: '2026-09-01T00:00:00Z',
  },
];

function createEnv(opts = {}) {
  const store = new Map([
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: opts.lessons || LESSONS })],
  ]);
  const counters = new Map();
  const signals = [];   // bound args of every INSERT INTO search_signals
  const ddl = [];       // CREATE TABLE statements the worker issued
  const statsBinds = [];
  const d1 = {
    _signals: signals,
    _ddl: ddl,
    _statsBinds: statsBinds,
    _counters: counters,
    prepare(sql) {
      const stmt = {
        _bound: [],
        bind(...args) { stmt._bound = args; return stmt; },
        async all() {
          if (sql.includes('INSERT INTO counters')) {
            const key = `${stmt._bound[0]}|${stmt._bound[1]}|${stmt._bound[2]}`;
            const next = (counters.get(key) || 0) + Number(stmt._bound[3] || 1);
            counters.set(key, next);
            return { results: [{ count: next }] };
          }
          if (sql.includes('FROM search_signals')) {
            if (sql.includes('GROUP BY')) {
              if (opts.groupsThrow) throw new Error('D1_ERROR: no such column: domain');
              return { results: opts.signalGroups || [] };
            }
            statsBinds.push(stmt._bound);
            if (opts.statsThrows) throw new Error('D1_ERROR: no such table: search_signals');
            return { results: opts.signalRows || [] };
          }
          if (sql.includes('FROM questions')) return { results: [] };
          if (sql.includes('FROM lessons')) return { results: opts.lessons || LESSONS };
          return { results: [] };
        },
        async run() {
          if (sql.trim().startsWith('CREATE TABLE IF NOT EXISTS search_signals')) {
            ddl.push(sql);
            return { success: true };
          }
          if (sql.trim().startsWith('INSERT INTO search_signals')) {
            if (opts.insertThrows) throw new Error('D1_ERROR: no such table: search_signals');
            const b = stmt._bound || [];
            // Bound arguments are in INSERT order, not "old columns then new ones": the first
            // version of this line appended the new fields, so `query_hash` read the domain and the
            // assertion said `6 !== 32` (2026-09-19). Keep this list in the same order as the
            // statement's column list.
            signals.push({ solved: b[0], query: b[1], query_hash: b[2], top_id: b[3],
              result_count: b[4], domain: b[5], client_hint: b[6], agent: b[7], version: b[8],
              os: b[9], latency_ms: b[10] });
            return { success: true };
          }
          return { success: true };
        },
      };
      return stmt;
    },
  };
  const env = {
    MCP_TOKEN: TOKEN,
    MCP_VERSION: 'search-signals-test',
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
  if (!opts.noD1) env.MISAKANET_D1 = d1;
  if (opts.searchSignals !== undefined) env.MISAKANET_SEARCH_SIGNALS = opts.searchSignals;
  return env;
}

function searchRequest(query, args = {}) {
  return new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '198.51.100.' + (Math.floor(Math.random() * 200) + 1),
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query, ...args } },
    }),
  });
}

// ctx collects waitUntil promises so the (fire-and-forget) signal write can be awaited.
function collectCtx() {
  const pending = [];
  return { ctx: { waitUntil: (p) => pending.push(p) }, pending };
}

async function search(query, args, env) {
  const { ctx, pending } = collectCtx();
  const resp = await worker.fetch(searchRequest(query, args), env, ctx);
  assert.equal(resp.status, 200);
  const body = await resp.json();
  assert.equal(body.error, undefined, `unexpected MCP error: ${JSON.stringify(body.error)}`);
  // The write is handed to waitUntil, so awaiting the response is not enough.
  await Promise.all(pending);
  return JSON.parse(body.result.content[0].text);
}

test('a hit records one row with solved=1, the top id and the result count', async () => {
  const env = createEnv();
  const result = await search('pip install timeout', { domain: 'python' }, env);
  assert.ok(result.results.length >= 1, 'the test query must hit, so the assert is about a hit');
  assert.equal(result.results[0].id, 'pip-timeout-mirror');

  const rows = env.MISAKANET_D1._signals;
  assert.equal(rows.length, 1, 'exactly one signal row per completed search');
  assert.equal(rows[0].solved, 1);
  assert.equal(rows[0].query, 'pip install timeout', 'short queries are stored as written');
  assert.match(rows[0].query_hash || '', /^[0-9a-f]{8}$/,
    'and always with a salted dedup key (2026-09-18 query policy)');
  assert.notEqual(rows[0].query_hash, 'pip install timeout', 'the key is not the query itself');
  assert.equal(rows[0].client_hint, null, 'no client_id was sent, so there is no hint to store');
  assert.ok(!('client_hint' in rows[0]) || rows[0].client_hint === null || typeof rows[0].client_hint === 'string',
    'the client hint is optional and pseudonymous');
  assert.equal(rows[0].top_id, 'pip-timeout-mirror');
  assert.equal(rows[0].result_count, result.results.length);
  assert.equal(rows[0].domain, 'python');
});

test('a miss records one row with solved=0, no top id and a zero count', async () => {
  const env = createEnv();
  const result = await search('zzz-no-such-topic-anywhere-999', {}, env);
  assert.equal(result.no_match, true);

  const rows = env.MISAKANET_D1._signals;
  assert.equal(rows.length, 1);
  assert.equal(rows[0].solved, 0);
  assert.equal(rows[0].query, 'zzz-no-such-topic-anywhere-999');
  assert.equal(rows[0].top_id, null);
  assert.equal(rows[0].result_count, 0);
  assert.equal(rows[0].domain, '');
});

test('hit and miss write the same columns, and the miss path keeps its gap record', async () => {
  const hitEnv = createEnv();
  const missEnv = createEnv();
  await search('pip install timeout', {}, hitEnv);
  await search('zzz-no-such-topic-anywhere-999', {}, missEnv);

  const hitRow = hitEnv.MISAKANET_D1._signals[0];
  const missRow = missEnv.MISAKANET_D1._signals[0];
  assert.deepEqual(Object.keys(hitRow).sort(), Object.keys(missRow).sort());
  assert.notEqual(hitRow.solved, missRow.solved, 'the two branches must be distinguishable');
  // The miss path's own behaviour is untouched: logSearchGap still bumps the gap
  // counter (the D1 path of #1649), and a hit still bumps none.
  const isGap = (key) => key.startsWith('gap|');
  assert.deepEqual([...missEnv.MISAKANET_D1._counters.keys()].filter(isGap),
    [`gap|zzz-no-such-topic-anywhere-999|${new Date().toISOString().slice(0, 10)}`]);
  assert.deepEqual([...hitEnv.MISAKANET_D1._counters.keys()].filter(isGap), []);
});

test('the kill switch disables recording without changing the search answer', async () => {
  const env = createEnv({ searchSignals: '0' });
  const result = await search('pip install timeout', {}, env);
  assert.ok(result.results.length >= 1, 'the search itself is unaffected');
  assert.deepEqual(env.MISAKANET_D1._signals, [], 'MISAKANET_SEARCH_SIGNALS=0 records nothing');
});

test('a failing signal write cannot break the search', async () => {
  const env = createEnv({ insertThrows: true });
  const hit = await search('pip install timeout', {}, env);
  assert.equal(hit.results[0].id, 'pip-timeout-mirror');
  const miss = await search('zzz-no-such-topic-anywhere-999', {}, env);
  assert.equal(miss.no_match, true);
  assert.deepEqual(env.MISAKANET_D1._signals, []);
});

test('a search without a D1 binding still answers (nothing to record)', async () => {
  const env = createEnv({ noD1: true });
  const result = await search('pip install timeout', {}, env);
  assert.ok(result.results.length >= 1);
});

test('the stats endpoint serves solved flags and timestamps only', async () => {
  const env = createEnv({
    signalRows: [
      { solved: 1, created_at: '2026-09-16 10:00:00' },
      { solved: 0, created_at: '2026-09-16 10:05:00' },
    ],
  });
  const resp = await worker.fetch(
    new Request('https://misakanet.org/api/search-signals/stats?days=30'), env);
  assert.equal(resp.status, 200);
  const body = await resp.json();
  assert.equal(body.days, 30);
  assert.equal(body.truncated, false);
  assert.equal(body.source, 'd1:search_signals');
  assert.deepEqual(body.rows, [
    { solved: 1, created_at: '2026-09-16 10:00:00' },
    { solved: 0, created_at: '2026-09-16 10:05:00' },
  ]);
  assert.equal(body.rows[0].query, undefined, 'no query text leaves the worker here');
  assert.equal(body.rows[0].top_id, undefined, 'no lesson ids either');
  // The window is applied in SQL, not in the script.
  assert.equal(env.MISAKANET_D1._statsBinds[0][0], '-30 days');
});

test('the stats endpoint answers an empty window before anything was recorded', async () => {
  const env = createEnv({ statsThrows: true });
  const resp = await worker.fetch(
    new Request('https://misakanet.org/api/search-signals/stats'), env);
  assert.equal(resp.status, 200, 'a missing table is "no samples yet", not a server error');
  const body = await resp.json();
  assert.deepEqual(body.rows, []);
  assert.equal(body.days, 7, 'the default window is 7 days');
  assert.equal(body.truncated, false);
});

test('the stats endpoint needs the D1 binding', async () => {
  const resp = await worker.fetch(
    new Request('https://misakanet.org/api/search-signals/stats'), createEnv({ noD1: true }));
  assert.equal(resp.status, 503);
});

// ── the row shape must not drift from the table the worker creates ───────────
// There is no `workers/d1/schema.sql` entry for this table (the worker creates it
// on first write — see the comment in register-proxy-sw.js), so this test is the
// place that keeps the CREATE TABLE and the INSERT column list in agreement.
test('every column the insert names is declared in the worker-created table', () => {
  const ddl = WORKER_SOURCE.match(/CREATE TABLE IF NOT EXISTS search_signals\s*\(([\s\S]*?)\n\s*\)/);
  assert.ok(ddl, 'the worker must create the search_signals table');
  const columns = new Set(
    ddl[1].split('\n')
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith('--'))
      .map((line) => line.split(/\s+/)[0]),
  );
  // Fields added after the first release arrive as guarded `ALTER TABLE … ADD COLUMN` statements
  // (2026-09-18), so they are part of the table's declaration for this guard's purpose. Reading only
  // CREATE would let the insert name columns the table never gets.
  for (const alter of WORKER_SOURCE.matchAll(/ALTER TABLE search_signals ADD COLUMN (\w+)/g)) {
    columns.add(alter[1]);
  }
  const insert = WORKER_SOURCE.match(/INSERT INTO search_signals\s*\(([^)]*)\)/);
  assert.ok(insert, 'the worker must insert into search_signals');
  for (const column of insert[1].split(',').map((c) => c.trim())) {
    assert.ok(columns.has(column), `search_signals.${column} is inserted but not declared`);
  }
  assert.ok(columns.has('solved'), 'solved is the field the hit rate reads');
  assert.ok(columns.has('created_at'), 'the window filter needs created_at');
});

test('the read endpoint returns solved and created_at, which the aggregator needs', () => {
  // `[^`]` keeps the match inside one template literal — a `[\s\S]*?` here would
  // start at the first SELECT in the file and swallow whole statements.
  const select = WORKER_SOURCE.match(/SELECT([^`]*?)FROM search_signals/);
  assert.ok(select, 'the stats endpoint must select from search_signals');
  const columns = select[1].split(',').map((c) => c.trim().toLowerCase());
  assert.ok(columns.includes('solved'));
  assert.ok(columns.includes('created_at'));
  assert.ok(!columns.includes('query'), 'the open endpoint must not serve query text');
});

test('a long query is truncated to 80 characters and hashed', async () => {
  // The policy: enough to see what people ask and to dedupe it, without keeping a whole prompt.
  const env = createEnv();
  const long = 'x'.repeat(300);
  await search(long, {}, env);
  const row = env.MISAKANET_D1._signals[0];
  assert.equal(row.query.length, 80, 'the stored query is the first 80 characters');
  assert.match(row.query_hash, /^[0-9a-f]{8}$/, 'and it is fingerprinted for dedupe');
});

test('a client_id becomes a pseudonymous hint, never the raw value', async () => {
  const env = createEnv();
  await search('pip install timeout', { client_id: 'agent-alpha-1' }, env);
  const row = env.MISAKANET_D1._signals[0];
  assert.match(row.client_hint || '', /^[0-9a-f]{8}$/, 'the hint is a salted dedup key');
  assert.notEqual(row.client_hint, 'agent-alpha-1',
    'the row store must not hold the identifier as sent');
});


// ── the breakdown added for the ROADMAP's milestone ② (a table for release notes) ──────────

test('the breakdown merges days and topics into count-only tables', async () => {
  const env = createEnv({
    signalRows: [{ solved: 1, created_at: '2026-09-16 10:00:00' }],
    signalGroups: [
      { day: '2026-09-16', domain: 'devops', hits: 1, total: 4 },
      { day: '2026-09-16', domain: 'llm', hits: 3, total: 3 },
      { day: '2026-09-15', domain: 'devops', hits: 0, total: 2 },
    ],
  });
  const resp = await worker.fetch(
    new Request('https://misakanet.org/api/search-signals/stats?days=30'), env);
  const body = await resp.json();

  const day = body.breakdown.by_day.find((r) => r.key === '2026-09-16');
  assert.equal(day.hits, 4, 'the day sums both topics');
  assert.equal(day.total, 7);
  assert.equal(day.miss, 3, 'miss is derived, not asked of the database');
  assert.equal(day.hit_rate, 4 / 7);

  const devops = body.breakdown.by_domain.find((r) => r.key === 'devops');
  assert.equal(devops.total, 6, 'the topic sums both days');
  assert.equal(devops.hits, 1);
  assert.equal(devops.hit_rate, 1 / 6);
});

test('the breakdown counts legacy rows as misses, like the report does', async () => {
  // The SQL is `SUM(CASE WHEN solved = 1 ...)`, so a NULL solved contributes nothing to
  // `hits` while still counting in `total` — the same conservative rule as the script.
  const env = createEnv({
    signalGroups: [{ day: '2026-09-16', domain: 'devops', hits: 0, total: 3 }],
  });
  const body = await (await worker.fetch(
    new Request('https://misakanet.org/api/search-signals/stats'), env)).json();
  assert.equal(body.breakdown.by_day[0].miss, 3);
  assert.equal(body.breakdown.by_day[0].hit_rate, 0);
});

test('the breakdown adds no per-request detail to the response', async () => {
  const env = createEnv({
    signalRows: [{ solved: 1, created_at: '2026-09-16 10:00:00' }],
    signalGroups: [{ day: '2026-09-16', domain: 'devops', hits: 1, total: 2 }],
  });
  const body = await (await worker.fetch(
    new Request('https://misakanet.org/api/search-signals/stats'), env)).json();
  const wire = JSON.stringify(body);
  for (const forbidden of ['query', 'top_id', 'topId', 'query_hash']) {
    assert.ok(!wire.includes(forbidden),
      `the breakdown must stay count-only — "${forbidden}" appeared in the response`);
  }
  assert.ok(wire.includes('by_day') && wire.includes('by_domain'));
});

test('a deployment without the aggregate column still serves the rows', async () => {
  // Deploy order: the script ships first and the worker follows, so the endpoint must keep
  // answering while the old worker is still live (or when the column is missing).
  const env = createEnv({
    signalRows: [{ solved: 1, created_at: '2026-09-16 10:00:00' }],
    groupsThrow: true,
  });
  const resp = await worker.fetch(
    new Request('https://misakanet.org/api/search-signals/stats'), env);
  assert.equal(resp.status, 200);
  const body = await resp.json();
  assert.equal(body.rows.length, 1);
  assert.deepEqual(body.breakdown, { by_day: [], by_domain: [] });
});
