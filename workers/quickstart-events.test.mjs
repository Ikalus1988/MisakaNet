// Quickstart step events (#1897): what gets REPORTED as an event, and where it is stored.
//
// Three properties from the issue, pinned here: the events are queryable server-side; the write
// is D1-only (the env below counts every KV put and requires the list to stay empty — a source
// grep cannot see a fallback that a later edit adds); and the payload is a closed-set literal
// plus a UTC day, never IP text or query text. The frontend's silent-degradation half is pinned
// in tests/test_quickstart_events.py.
//
// Run: node --test workers/quickstart-events.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, {
  QS_EVENTS,
  QS_VIEW_STEP,
  QS_COPY_STEPS,
  QS_LINK_STEPS,
  bumpQsEvent,
  readQsEventDay,
} from './register-proxy-sw.js';

const day = () => new Date().toISOString().slice(0, 10);

/** D1 stand-in for the qs counters upsert and the scope='qs' day read. `counterBinds` is the
 *  privacy seam: a leak is a bind argument, so the check looks at what reached `.bind()`. */
function createD1() {
  const rows = new Map();
  const counterBinds = [];
  return {
    rows,
    counterBinds,
    prepare(sql) {
      const stmt = {
        _args: [],
        bind(...args) { stmt._args = args; return stmt; },
        async all() { return stmt._exec(); },
        async run() { stmt._exec(); return { success: true }; },
        _exec() {
          const args = stmt._args;
          if (/INSERT INTO counters/i.test(sql)) {
            if (/VALUES \('qs'/.test(sql)) {
              counterBinds.push(['qs', String(args[0]), String(args[1]), 1]);
              const key = `qs|${args[0]}|${args[1]}`;
              rows.set(key, (rows.get(key) || 0) + 1);
            } else {
              counterBinds.push(args.map(String));
            }
            return { results: [] };
          }
          if (/SELECT bucket, count FROM counters WHERE scope = 'qs'/i.test(sql)) {
            const period = String(args[0]);
            const results = [];
            for (const [key, count] of rows) {
              const [scope, bucket, p] = key.split('|');
              if (scope === 'qs' && p === period) results.push({ bucket, count });
            }
            return { results };
          }
          return { results: [] };
        },
      };
      return stmt;
    },
  };
}

/** KV counts every put — "no new KV write path" means this list stays empty. */
function createEnv({ d1 = null } = {}) {
  const store = new Map();
  const kvPuts = [];
  const env = {
    kvPuts,
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) { kvPuts.push(key); store.set(key, value); },
      async delete(key) { store.delete(key); },
      async list() { return { keys: [], list_complete: true }; },
    },
  };
  if (d1) env.MISAKANET_D1 = d1;
  return env;
}

const post = (body) => new Request('https://misakanet.org/api/qs-event', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

test('the event set is the three literals, and the step lists are the copy targets and link ids', () => {
  assert.deepEqual([...QS_EVENTS], ['qs_view', 'qs_copy', 'qs_link']);
  assert.equal(QS_VIEW_STEP, 'quickstart');
  // The copy steps are #3494's `data-copy-target` values — do not renumber. Same set as
  // GOLDEN_TEXT in tests/test_quickstart_copy.py.
  assert.deepEqual([...QS_COPY_STEPS], ['qs-a1', 'qs-a2', 'qs-a3q1', 'qs-a3q2', 'qs-b1', 'qs-b2', 'qs-b3']);
  assert.deepEqual([...QS_LINK_STEPS], ['install-guide', 'all-ways-doc', 'start-again', 'troubleshooting']);
});

test('POST /api/qs-event records one counters row per event, readable server-side', async () => {
  const d1 = createD1();
  const env = createEnv({ d1 });
  for (const [event, step] of [
    ['qs_view', 'quickstart'],
    ['qs_copy', 'qs-a1'],
    ['qs_copy', 'qs-a1'],
    ['qs_link', 'start-again'],
  ]) {
    const body = await (await worker.fetch(post({ event, step }), env)).json();
    assert.equal(body.recorded, true, JSON.stringify(body));
    assert.equal(body.backend, 'd1');
  }
  assert.equal(d1.rows.get(`qs|qs_view:quickstart|${day()}`), 1);
  assert.equal(d1.rows.get(`qs|qs_copy:qs-a1|${day()}`), 2);
  assert.equal(d1.rows.get(`qs|qs_link:start-again|${day()}`), 1);
  const dayCounts = await readQsEventDay(env, day());
  assert.equal(dayCounts['qs_view:quickstart'], 1);
  assert.equal(dayCounts['qs_copy:qs-a1'], 2);
  assert.equal(dayCounts['qs_link:start-again'], 1);
});

test('recording costs zero KV writes — no new KV write path (issue #1890)', async () => {
  const env = createEnv({ d1: createD1() });
  await worker.fetch(post({ event: 'qs_copy', step: 'qs-b3' }), env);
  assert.deepEqual(env.kvPuts, []);
});

test('when D1 is absent the event is dropped and no KV write is made', async () => {
  // `bumpCounter`'s KV fallback is the path this issue forbids; without D1 there is nothing
  // to write to, and the honest answer is `recorded: false` — never a KV key.
  const env = createEnv({ d1: null });
  const body = await (await worker.fetch(post({ event: 'qs_view', step: 'quickstart' }), env)).json();
  assert.equal(body.recorded, false);
  assert.deepEqual(env.kvPuts, []);
  assert.equal(await bumpQsEvent(env, 'qs_copy', 'qs-a1'), false);
});

test('unknown events and steps are refused and write nothing', async () => {
  const d1 = createD1();
  const env = createEnv({ d1 });
  for (const body of [
    { event: 'qs_copy', step: '../../etc/passwd' },
    { event: 'qs_copy', step: 'qs-z9' },
    { event: 'qs_view', step: 'qs-a1' },           // a copy step is not a view step
    { event: 'qs_link', step: 'quickstart' },
    { event: 'first_search', step: 'quickstart' },  // the funnel's retired name
    { event: 'qs_copy' },
    { event: 'qs_copy', step: { toString: () => 'qs-a1' } },
  ]) {
    const response = await worker.fetch(post(body), env);
    assert.equal(response.status, 400, JSON.stringify(body));
    assert.equal((await response.json()).recorded, undefined);
  }
  assert.equal(d1.counterBinds.length, 0);
});

test('every qs counters bind is a closed-set literal plus a UTC day — no IP, no query', async () => {
  const d1 = createD1();
  const env = createEnv({ d1 });
  // A request that *carries* an address and free text the way a real browser would. Neither
  // may end up in a bind: the handler must not read them at all.
  const response = await worker.fetch(new Request('https://misakanet.org/api/qs-event', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'CF-Connecting-IP': '203.0.113.9',
      'X-Forwarded-For': '203.0.113.9',
    },
    body: JSON.stringify({ event: 'qs_copy', step: 'qs-a2', query: 'pip install timeout', ip: '203.0.113.9' }),
  }), env);
  assert.equal((await response.json()).recorded, true);

  const qsBinds = d1.counterBinds.filter(([scope]) => scope === 'qs');
  assert.equal(qsBinds.length, 1, JSON.stringify(qsBinds));
  const [scope, bucket, period] = qsBinds[0];
  assert.equal(scope, 'qs');
  assert.match(bucket, /^qs_(view|copy|link):[a-z0-9-]+$/, bucket);
  assert.ok([...QS_COPY_STEPS, ...QS_LINK_STEPS, QS_VIEW_STEP].includes(bucket.split(':')[1]));
  assert.match(period, /^\d{4}-\d{2}-\d{2}$/, period);
  const flat = qsBinds.flat().join(' ');
  for (const forbidden of ['203.0.113.9', 'pip install timeout', 'client_id', 'query']) {
    assert.ok(!flat.includes(forbidden), `"${forbidden}" leaked into a qs bind: ${flat}`);
  }
});

test('GET /api/insights/quickstart-events answers with totals, per-step conversion and a privacy note', async () => {
  const d1 = createD1();
  const env = createEnv({ d1 });
  await worker.fetch(post({ event: 'qs_view', step: 'quickstart' }), env);
  await worker.fetch(post({ event: 'qs_view', step: 'quickstart' }), env);
  await worker.fetch(post({ event: 'qs_copy', step: 'qs-a1' }), env);
  await worker.fetch(post({ event: 'qs_link', step: 'install-guide' }), env);

  const body = await (await worker.fetch(
    new Request('https://misakanet.org/api/insights/quickstart-events?days=1'), env,
  )).json();
  assert.equal(body.success, true);
  assert.equal(body.available, true);
  assert.equal(body.windowDays, 1);
  assert.deepEqual([...body.events], ['qs_view', 'qs_copy', 'qs_link']);
  assert.equal(body.views, 2);
  assert.equal(body.totals['qs_copy:qs-a1'], 1);
  const a1 = body.steps.find((s) => s.step === 'qs-a1' && s.kind === 'copy');
  assert.equal(a1.count, 1);
  assert.equal(a1.perView, 0.5, 'one copy out of two block views');
  const never = body.steps.find((s) => s.step === 'qs-b3' && s.kind === 'copy');
  assert.equal(never.count, 0);
  assert.equal(never.perView, 0);
  assert.equal(body.meta.privacy, 'aggregate-only');
  assert.equal(body.meta.raw_query, false);
  assert.equal(body.meta.ip, false);
  assert.equal(body.meta.clipboard, false);
  assert.equal(body.meta.collected, 'step id + per-day count');
});

test('perView is null on a zero denominator — no block views means no conversion to report', async () => {
  const env = createEnv({ d1: createD1() });
  await worker.fetch(post({ event: 'qs_copy', step: 'qs-b1' }), env);
  const body = await (await worker.fetch(
    new Request('https://misakanet.org/api/insights/quickstart-events?days=1'), env,
  )).json();
  assert.equal(body.views, 0);
  const row = body.steps.find((s) => s.step === 'qs-b1');
  assert.equal(row.count, 1);
  assert.equal(row.perView, null, 'a zero denominator is null, the /api/funnel convention');
});

test('the days window is clamped to 1..30', async () => {
  const env = createEnv({ d1: createD1() });
  for (const [query, expected] of [['?days=0', 1], ['?days=999', 30], ['?days=7', 7], ['', 7]]) {
    const body = await (await worker.fetch(
      new Request(`https://misakanet.org/api/insights/quickstart-events${query}`), env,
    )).json();
    assert.equal(body.windowDays, expected, query);
  }
});
