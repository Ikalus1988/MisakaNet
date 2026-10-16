// The first-call funnel, counted from this worker's own counters (backlog P0#3).
//
// `docs/analytics/first-call-funnel.md` declared four metrics and named an implementation that had
// moved away with `hub/`. The metrics were never the hard part; the *shape* was. Two of them —
// `first_search` and a per-visitor `drop_off` — cannot be computed here at all, because both need to
// connect one request to one caller and this worker's contract with the client half is "no
// credential, no account, no client_id" (`docs/maintainer/client-half-acceptance.md`, D3). So the
// shipped funnel is five day-level integer counts, and the two individual-level questions are
// answered as read-time ratios of those counts (`GET /api/funnel`) or not at all.
//
// These tests pin, in order:
//
//   * each event's *trigger* and its *boundary* — a request counted exactly once, and the paths that
//     must not count (a renewed registration, a failed one, a refused burst, a used pairing code);
//   * the privacy claim as an executable assertion: every `counters` bind on the funnel scope is a
//     literal from `FUNNEL_EVENTS` plus a UTC day, and no caller-supplied value — address, query,
//     `client_id`, token — appears anywhere near it. The one scope that *does* carry a caller's words
//     is `gap` (that is its existing, documented purpose); the assertion below is what keeps the
//     funnel from becoming a second one;
//   * the read half: the route's shape, its derived ratios, `null` on a zero denominator, the
//     all-zero refusal, the `days` clamp, and the KV fallback being *read* and not just written.
//
// Run: node --test workers/funnel-events.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, {
  ACTIVITY_HISTORY_DEFAULT_DAYS,
  ACTIVITY_HISTORY_MAX_DAYS,
  ACTIVITY_HISTORY_MIN_DAYS,
  ACTIVITY_TTL_SECONDS,
  FUNNEL_EVENTS,
  flushTraffic,
  readFunnelDay,
  readFunnelSeries,
} from './register-proxy-sw.js';

const day = () => new Date().toISOString().slice(0, 10);
const LESSONS = [
  { id: 'pip-timeout-mirror', title: 'pip install timeout', domain: 'python', tags: ['pip'],
    path: 'lessons/core/pip-timeout-mirror.md', summary: 'pip install times out behind a proxy' },
];

// ── Doubles ──────────────────────────────────────────────────────────────────────────────────────

/**
 * A D1 stand-in for the statements this feature's paths issue: the `counters` upsert in each of the
 * three shapes the worker writes (generic, `node`, `kvwrite`), the two counter reads, and `kv_store`.
 *
 * `counterBinds` records every `counters` upsert's bound arguments in `[scope, bucket, period, …]`
 * form. That is the seam the privacy test asserts on: a leak is a bind argument, so the check has to
 * look at what actually reached `prepare().bind()` rather than at the constants in the file.
 */
function createD1({ failTokenWrites = false } = {}) {
  const rows = new Map();              // "scope|bucket|period" -> count
  const kv = new Map();                // kv_store key -> value
  const counterBinds = [];
  const prepare = (sql) => {
    const stmt = {
      _args: [],
      bind(...args) { stmt._args = args; return stmt; },
      async all() { return stmt._exec(); },
      async run() { stmt._exec(); return { success: true }; },
      _exec() {
        const args = stmt._args;
        if (/INSERT INTO counters/i.test(sql)) {
          let scope, bucket, period, first;
          if (/'node', 'all', 'all-time'/.test(sql)) {
            // `nextNodeCounter`: the first value is the seed, the conflict branch adds one.
            [scope, bucket, period, first] = ['node', 'all', 'all-time', Number(args[0])];
          } else if (/VALUES \('kvwrite'/.test(sql)) {
            // `noteKvWriteFamily`: bound (family, day) — the family, never the key.
            [scope, bucket, period, first] = ['kvwrite', String(args[0]), String(args[1]), 1];
          } else {
            [scope, bucket, period, first] =
              [String(args[0]), String(args[1]), String(args[2]), Number(args[3])];
          }
          counterBinds.push([scope, bucket, period, first]);
          const key = `${scope}|${bucket}|${period}`;
          const existing = rows.get(key);
          rows.set(key, existing === undefined ? first : existing + first);
          return { results: [{ count: rows.get(key) }] };
        }
        if (/SELECT bucket, count FROM counters/i.test(sql)) {
          const out = [];
          for (const [key, count] of rows) {
            const [scope, bucket, period] = key.split('|');
            if (scope === 'funnel' && period === String(args[0])) out.push({ bucket, count });
          }
          return { results: out };
        }
        if (/SELECT count FROM counters/i.test(sql)) {
          const value = rows.get(`${args[0]}|${args[1]}|${args[2]}`);
          return { results: value === undefined ? [] : [{ count: value }] };
        }
        if (/INSERT INTO kv_store/i.test(sql)) {
          if (failTokenWrites && String(args[0]).startsWith('mcp_token:')) {
            throw new Error('D1_ERROR: kv_store write failed');
          }
          kv.set(String(args[0]), String(args[1]));
          return { results: [] };
        }
        if (/SELECT value FROM kv_store/i.test(sql)) {
          const value = kv.get(String(args[0]));
          return { results: value === undefined ? [] : [{ value }] };
        }
        return { results: [] };
      },
    };
    return stmt;
  };
  return { rows, kv, counterBinds, prepare };
}

function createEnv({ d1 = null, failTokenKvWrites = false } = {}) {
  const store = new Map([['proxy:lessons', JSON.stringify({ ts: Date.now(), data: LESSONS })]]);
  const kvWrites = [];
  const env = {
    kvWrites,
    _store: store,
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) {
        // Both halves of the durable store have to refuse for `storePut` to report a failure —
        // it falls back to KV on a D1 error, which is the whole point of that helper.
        if (failTokenKvWrites && key.startsWith('mcp_token:')) {
          throw new Error('KV put() limit exceeded for the day.');
        }
        kvWrites.push(key);
        store.set(key, value);
      },
      async delete(key) { store.delete(key); },
      async list() { return { keys: [], list_complete: true }; },
    },
  };
  if (d1) env.MISAKANET_D1 = d1;
  return env;
}

/** Collects `ctx.waitUntil` work so a fire-and-forget write can be awaited in a test. */
function collector() {
  const pending = [];
  return { pending, ctx: { waitUntil: (promise) => pending.push(promise) } };
}

async function settle(pending) {
  while (pending.length) await Promise.all(pending.splice(0));
}

/**
 * Flush whatever the module-level traffic buffer is holding, and wait for it.
 *
 * The buffer is per isolate — and a test process has one isolate for every test in this file — so a
 * test that asserts a `visit` *delta* has to drain the leftover first. `flushTraffic` is the exported
 * seam for that: the batch otherwise fires at 50 requests or after five minutes, neither of which a
 * test can wait for.
 */
async function drain(env, ctx, pending) {
  flushTraffic(env, ctx);
  await settle(pending);
}

const BROWSER_UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36';

/** A request `classifyRequest` must call `pageview` — not a crawler, not an agent, not `/mcp`. */
function pageview(path = '/start') {
  return new Request(`https://misakanet.org${path}`, { headers: { 'User-Agent': BROWSER_UA } });
}

function toolCall(name, args, ip = '203.0.113.7') {
  return new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'Origin': 'https://misakanet.org',
      'CF-Connecting-IP': ip,
    },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name, arguments: args } }),
  });
}

function connectRequest(ip = '203.0.113.7') {
  return new Request('https://misakanet.org/mcp/connect', {
    method: 'POST',
    headers: { 'CF-Connecting-IP': ip },
  });
}

function pairRequest(code, ip = '203.0.113.7') {
  return new Request('https://misakanet.org/mcp/pair', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': ip },
    body: JSON.stringify({ code }),
  });
}

/** The JSON payload the MCP transport wraps in `result.content[0].text`. */
async function toolResult(response) {
  const body = await response.json();
  return JSON.parse(body.result.content[0].text);
}

const counter = (d1, scope, bucket) => d1.rows.get(`${scope}|${bucket}|${day()}`) || 0;
const funnel = (d1, bucket) => counter(d1, 'funnel', bucket);

// ── The event set ────────────────────────────────────────────────────────────────────────────────

test('the funnel event set is the five literals, and it is the exported constant', () => {
  // Asserted against the export rather than restated: the reader and the five write sites both
  // enumerate this list, and a literal here would keep passing after an event was renamed on one
  // side only — which is the drift this constant exists to make impossible.
  assert.deepEqual([...FUNNEL_EVENTS], ['visit', 'register', 'authorize', 'pair', 'search']);
  for (const refused of ['first_search', 'drop_off', 'error_search']) {
    assert.ok(!FUNNEL_EVENTS.includes(refused),
      `'${refused}' needs an identifier (or is derived at read time) and must not be a bucket`);
  }
});

// ── visit ────────────────────────────────────────────────────────────────────────────────────────

test('visit counts pageviews once each, and agrees with traffic/pageview for the day', async () => {
  const d1 = createD1();
  const env = createEnv({ d1 });
  const { pending, ctx } = collector();
  await drain(env, ctx, pending);

  const visitBefore = funnel(d1, 'visit');
  const pageviewBefore = counter(d1, 'traffic', 'pageview');
  for (let i = 0; i < 3; i++) await worker.fetch(pageview('/start'), env, ctx);
  await drain(env, ctx, pending);

  // "Repeated visits must not be double-counted" has two readings, and this is both of them: one
  // request adds exactly one unit (not zero, not two), and the funnel is a *count of requests*, so
  // three requests are three — unlike `traffic`, it is not deduplicated per address, because it
  // holds no address to deduplicate on.
  assert.equal(funnel(d1, 'visit') - visitBefore, 3, 'three requests, three units');
  assert.equal(counter(d1, 'traffic', 'pageview') - pageviewBefore,
    funnel(d1, 'visit') - visitBefore,
    'visit rides the traffic batch, so the two rows must describe the same day identically');
});

test('a non-pageview request is not a visit', async () => {
  const d1 = createD1();
  const env = createEnv({ d1 });
  const { pending, ctx } = collector();
  await drain(env, ctx, pending);

  const visitBefore = funnel(d1, 'visit');
  const agentBefore = counter(d1, 'traffic', 'agent');
  // `curl/8.5.0` is agent traffic by `classifyRequest`, and `/api/health` is not a page.
  await worker.fetch(new Request('https://misakanet.org/api/health', {
    headers: { 'User-Agent': 'curl/8.5.0' },
  }), env, ctx);
  await drain(env, ctx, pending);

  assert.equal(funnel(d1, 'visit'), visitBefore, 'only a pageview is the funnel front door');
  // The flush really ran: without this the assertion above would also pass on a broken flush.
  assert.equal(counter(d1, 'traffic', 'agent') - agentBefore, 1,
    'the agent count must move, or the flush did nothing and the line above proves nothing');
});

// ── register ─────────────────────────────────────────────────────────────────────────────────────

test('a completed registration counts once, and a reused client_id does not count again', async () => {
  const d1 = createD1();
  const env = createEnv({ d1 });
  const { pending, ctx } = collector();

  const first = await toolResult(await worker.fetch(toolCall('misakanet_register', { agent_type: 'dsh' }), env, ctx));
  assert.ok(first.node_id, JSON.stringify(first));
  assert.equal(first.reused, undefined, 'no client_id means a new node every call');
  assert.equal(funnel(d1, 'register'), 1, 'one new node, one registration');

  const second = await toolResult(await worker.fetch(toolCall('misakanet_register', { agent_type: 'dsh' }), env, ctx));
  assert.notEqual(second.node_id, first.node_id);
  assert.equal(funnel(d1, 'register'), 2, 'a second node is a second registration');

  // The renewal path returns before the counter, so re-presenting a key cannot inflate the number.
  const a = await toolResult(await worker.fetch(
    toolCall('misakanet_register', { client_id: 'stable-client-0001' }), env, ctx));
  const settled = funnel(d1, 'register');
  const b = await toolResult(await worker.fetch(
    toolCall('misakanet_register', { client_id: 'stable-client-0001' }), env, ctx));
  assert.equal(b.node_id, a.node_id);
  assert.equal(b.reused, true, JSON.stringify(b));
  assert.equal(funnel(d1, 'register'), settled,
    'a token renewal is not a new registration, or a client that polls would look like growth');
  await settle(pending);
});

test('a registration whose token could not be stored is not counted', async () => {
  // Both stores refuse `mcp_token:*`: `storePut` falls back to KV on a D1 error, so failing only one
  // of them would produce a *successful* registration and the test would prove nothing.
  const d1 = createD1({ failTokenWrites: true });
  const env = createEnv({ d1, failTokenKvWrites: true });
  const { pending, ctx } = collector();

  const result = await toolResult(await worker.fetch(toolCall('misakanet_register', {}), env, ctx));
  await settle(pending);

  assert.equal(result.code, 'storage_unavailable', JSON.stringify(result));
  assert.equal(funnel(d1, 'register'), 0,
    'the caller was told to retry: a step that did not complete is not a funnel step');
});

// ── authorize / pair (the human door) ────────────────────────────────────────────────────────────

test('each issued pairing code counts once, and a rate-limited request does not', async () => {
  const d1 = createD1();
  const env = createEnv({ d1 });
  const { pending, ctx } = collector();
  const ip = '203.0.113.91';

  // Read until refused rather than exactly `limit` times: the window is a wall-clock 10 minutes, so a
  // run that starts near a boundary legitimately gets more than three through. The invariant under
  // test is "refusals do not count", not "the limit is exactly three".
  let issued = 0;
  let refused = 0;
  for (let i = 1; i <= 12; i++) {
    const response = await worker.fetch(connectRequest(ip), env, ctx);
    await settle(pending);
    if (response.status === 429) { refused += 1; break; }
    assert.equal(response.status, 200, `connect ${i} answered ${response.status}`);
    assert.ok((await response.json()).code, 'a 200 must carry a code');
    issued += 1;
  }

  assert.equal(refused, 1, `the 3/10min limiter must refuse within 12 attempts (issued ${issued})`);
  assert.ok(issued >= 1);
  assert.equal(funnel(d1, 'authorize'), issued,
    'a refused request never reached the funnel; counting it would make the door look wider');
});

test('a completed pair counts once; an unknown or already-used code does not', async () => {
  const d1 = createD1();
  const env = createEnv({ d1 });
  const { pending, ctx } = collector();
  const ip = '203.0.113.92';

  const { code } = await (await worker.fetch(connectRequest(ip), env, ctx)).json();
  await settle(pending);
  const before = funnel(d1, 'pair');

  const ok = await worker.fetch(pairRequest(code, ip), env, ctx);
  assert.equal(ok.status, 200, `pair answered ${ok.status}`);
  assert.ok((await ok.json()).token, 'a completed pair hands out a token');
  await settle(pending);
  assert.equal(funnel(d1, 'pair') - before, 1, 'one code, one pair');

  const again = await worker.fetch(pairRequest(code, ip), env, ctx);
  assert.equal(again.status, 409, 'a used code is not reusable');
  await settle(pending);
  assert.equal(funnel(d1, 'pair') - before, 1, 'the 409 is an attempt, not a second completion');

  const unknown = await worker.fetch(pairRequest('ZZZZZZ', ip), env, ctx);
  assert.equal(unknown.status, 404);
  await settle(pending);
  assert.equal(funnel(d1, 'pair') - before, 1, 'the 404 is an attempt, not a completion');
});

// ── search ───────────────────────────────────────────────────────────────────────────────────────

test('an answered search counts once, hit or miss; a burst-refused search counts not at all', async () => {
  const d1 = createD1();
  const env = createEnv({ d1 });
  const { pending, ctx } = collector();
  const ip = '203.0.113.93';
  await drain(env, ctx, pending);

  const before = funnel(d1, 'search');
  await worker.fetch(toolCall('misakanet_search', { query: 'pip install timeout', top: 1 }, ip), env, ctx);
  await settle(pending);
  assert.equal(funnel(d1, 'search') - before, 1, 'a hit is one search');
  // A miss is one search too. `funnel.error_search` is a *different* question (did it find
  // anything), answered elsewhere; it must not turn one call into two funnel units.
  await worker.fetch(toolCall('misakanet_search', { query: 'zzz-canary-nothing-matches-zzz', top: 1 }, ip), env, ctx);
  await settle(pending);
  assert.equal(funnel(d1, 'search') - before, 2, 'a no-match search completed, so it is one search');

  // The anonymous burst limit (same window as the reads above) refuses eventually; the refusal
  // returns before the counter, which is what this loop is here to prove.
  let answered = 0;
  let refused = null;
  for (let i = 1; i <= 60; i++) {
    const result = await toolResult(await worker.fetch(
      toolCall('misakanet_search', { query: 'pip install timeout', top: 1 }, ip), env, ctx));
    await settle(pending);
    if (result.error) { refused = result; break; }
    answered += 1;
  }
  assert.ok(refused, 'the anonymous burst limit must refuse within 60 searches');
  assert.match(String(refused.error), /Too many requests|Reads are unlimited/);
  assert.equal(funnel(d1, 'search') - before, 2 + answered,
    `the refusal must not be counted: counted ${funnel(d1, 'search') - before}, answered ${2 + answered}`);
});

// ── the privacy claim, as an assertion over the bytes that reached storage ───────────────────────

test('no funnel write carries anything the caller sent', async () => {
  const d1 = createD1();
  const env = createEnv({ d1 });
  const { pending, ctx } = collector();
  const IP = '203.0.113.77';
  const CLIENT_ID = 'canary-client-zzz-0001';
  const QUERY = 'canary-query-zzz-0001';

  // Drive all five events once.
  await worker.fetch(pageview('/start'), env, ctx);
  await drain(env, ctx, pending);
  await worker.fetch(toolCall('misakanet_register', { client_id: CLIENT_ID }, IP), env, ctx);
  await settle(pending);
  await worker.fetch(toolCall('misakanet_search', { query: QUERY, top: 1 }, IP), env, ctx);
  await settle(pending);
  const { code } = await (await worker.fetch(connectRequest(IP), env, ctx)).json();
  await settle(pending);
  await worker.fetch(pairRequest(code, IP), env, ctx);
  await settle(pending);

  const funnelBinds = d1.counterBinds.filter(([scope]) => scope === 'funnel');
  assert.deepEqual(
    [...new Set(funnelBinds.map(([, bucket]) => bucket))].sort(),
    [...FUNNEL_EVENTS].sort(),
    'every event must be written through a literal bucket from the exported set');

  for (const [scope, bucket, period, delta] of funnelBinds) {
    assert.equal(scope, 'funnel');
    assert.ok(FUNNEL_EVENTS.includes(bucket), `'${bucket}' is not a funnel event`);
    assert.match(period, /^\d{4}-\d{2}-\d{2}$/, 'the period is a UTC day, never a caller value');
    assert.equal(delta, 1, 'one unit per event');
    for (const value of [bucket, period, delta]) {
      const text = String(value);
      for (const [what, secret] of [['address', IP], ['client_id', CLIENT_ID], ['query', QUERY], ['token prefix', 'mcp_']]) {
        assert.ok(!text.includes(secret), `a funnel ${what} reached storage: ${text}`);
      }
    }
  }

  // The contrast that makes the assertion meaningful: the *gap* scope does carry the query (that is
  // what it is for, and it is not new), so a test that only looked for the string would pass on a
  // worker that had stopped writing gaps at all.
  assert.ok(d1.counterBinds.some(([scope, bucket]) => scope === 'gap' && bucket === QUERY),
    'the no-match path must still record its gap, or the funnel assertion above proves nothing');
});

// ── the KV fallback is written and read ──────────────────────────────────────────────────────────

test('without D1 the same events land on the counters: KV keys', async () => {
  const env = createEnv();   // KV only: the deployment the fallback exists for
  const { pending, ctx } = collector();

  await worker.fetch(pageview('/start'), env, ctx);
  await drain(env, ctx, pending);
  await worker.fetch(toolCall('misakanet_register', {}), env, ctx);
  await settle(pending);
  await worker.fetch(toolCall('misakanet_search', { query: 'pip install timeout', top: 1 }), env, ctx);
  await settle(pending);

  for (const [event, value] of [['visit', '1'], ['register', '1'], ['search', '1']]) {
    const key = `counters:funnel:${event}:${day()}`;
    assert.ok(env.kvWrites.includes(key), `missing ${key} in ${env.kvWrites.join(', ')}`);
    assert.equal(env._store.get(key), value, `${key} must hold the count`);
  }
});

test('readFunnelDay merges D1 with the KV fallback instead of stopping at the first answer', async () => {
  const d1 = createD1();
  const env = createEnv({ d1 });
  const today = day();
  // A split day: D1 refused part of it and `bumpCounter` sent that delta to KV, which is exactly the
  // outage shape the fallback exists for. A reader that returned on the successful D1 query would
  // report 5 and silently lose 2 — the number would be wrong in the direction nobody checks.
  d1.rows.set(`funnel|visit|${today}`, 5);
  await env.MISAKANET_KV.put(`counters:funnel:visit:${today}`, '2');
  await env.MISAKANET_KV.put(`counters:funnel:search:${today}`, '3');

  assert.deepEqual(await readFunnelDay(env, today), {
    visit: 7, register: 0, authorize: 0, pair: 0, search: 3,
  });
});

// ── the read route ───────────────────────────────────────────────────────────────────────────────

test('GET /api/funnel reports the day and derives both ratios at read time', async () => {
  const d1 = createD1();
  const env = createEnv({ d1 });
  const today = day();
  d1.rows.set(`funnel|visit|${today}`, 13);
  d1.rows.set(`funnel|register|${today}`, 4);
  d1.rows.set(`funnel|pair|${today}`, 3);
  d1.rows.set(`funnel|search|${today}`, 121);

  const response = await worker.fetch(new Request('https://misakanet.org/api/funnel?days=7'), env);
  assert.equal(response.status, 200);
  // A shared TTL is only safe because no field here varies by caller; asserted against the constant
  // the neighbouring activity route uses, so a "short TTL" drifting to a day fails here first.
  assert.equal(response.headers.get('cache-control'),
    `public, max-age=${ACTIVITY_TTL_SECONDS}, s-maxage=${ACTIVITY_TTL_SECONDS}`);
  assert.equal(response.headers.get('x-robots-tag'), 'noindex');

  const body = await response.json();
  assert.equal(body.source, 'counters/funnel');
  assert.equal(body.days, 7);
  assert.equal(body.series.length, 7, 'oldest first, one entry per day of the window');
  assert.deepEqual(body.withheld, [], 'nothing here could carry another party, so nothing is withheld');
  assert.match(body.note, /not\s+conversion rates|day-level proxies/);

  const last = body.series[body.series.length - 1];
  assert.equal(last.date, today);
  assert.deepEqual(
    { visit: last.visit, register: last.register, authorize: last.authorize, pair: last.pair, search: last.search },
    { visit: 13, register: 4, authorize: 0, pair: 3, search: 121 });
  // 121 searches / 4 registrations. A ratio, named for its denominator so it is not read as a rate.
  assert.equal(last.activation_per_register, 30.25);
  // 1 - (register + pair) / visit = 1 - 7/13. Both doors count as completions: a person who pairs
  // never calls `misakanet_register`, so counting only that one would overstate drop-off.
  assert.equal(last.drop_off_rate, 0.4615);

  // A day with no rows is kept and reported as zeros, with `null` — not 0 — where the denominator is
  // zero. "A counter that cannot be read and one that is genuinely empty are two answers."
  const first = body.series[0];
  assert.equal(first.visit, 0);
  assert.equal(first.drop_off_rate, null);
  assert.equal(first.activation_per_register, null);
});

test('an all-zero window is refused as unreadable rather than drawn as a quiet week', async () => {
  const env = createEnv({ d1: createD1() });
  const response = await worker.fetch(new Request('https://misakanet.org/api/funnel'), env);
  assert.equal(response.status, 503);
  const body = await response.json();
  assert.equal(body.code, 'counters_unreadable');
});

test('days is clamped to the activity window, defaulted, and part of the cache key', async () => {
  const d1 = createD1();
  const env = createEnv({ d1 });
  d1.rows.set(`funnel|visit|${day()}`, 1);

  const daysOf = async (query) => {
    const url = `https://misakanet.org/api/funnel${query}`;
    const response = await worker.fetch(new Request(url), env);
    assert.equal(response.status, 200, `${url} answered ${response.status}`);
    return (await response.json()).days;
  };

  assert.equal(await daysOf(''), ACTIVITY_HISTORY_DEFAULT_DAYS, 'no argument is the default window');
  assert.equal(await daysOf('?days=1'), ACTIVITY_HISTORY_MIN_DAYS, 'a one-day trend is not a trend');
  assert.equal(await daysOf('?days=365'), ACTIVITY_HISTORY_MAX_DAYS, 'a year of reads is not one request');
  assert.equal(await daysOf('?days=not-a-number'), ACTIVITY_HISTORY_DEFAULT_DAYS);
  assert.equal(await daysOf('?days=14'), 14, 'a window inside the clamp is honoured');
});

test('readFunnelSeries returns one entry per day, oldest first, zeros included', async () => {
  const d1 = createD1();
  const env = createEnv({ d1 });
  const series = await readFunnelSeries(env, 3);
  assert.equal(series.length, 3);
  assert.deepEqual(series.map(s => s.date), [2, 1, 0].map(i =>
    new Date(Date.now() - i * 86400000).toISOString().slice(0, 10)));
  for (const entry of series) {
    assert.deepEqual(Object.keys(entry).sort(),
      ['authorize', 'date', 'pair', 'register', 'search', 'visit']);
  }
});
