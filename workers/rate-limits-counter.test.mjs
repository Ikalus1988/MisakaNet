// The per-address limits and the per-source intake ledger (#2075).
//
// What moved, and why this file exists rather than a paragraph in a PR:
//
// 1. `rate:feedback:<ip>`, `rate:intake:<ip>` and `rate:connect:<ip>` were a `storeGet` + compare +
//    `storePut` on a value whose TTL *was* the window. Two concurrent requests from one address
//    could both read `4` and both write `5` — the limit undercounted exactly when it was under load.
//    They now go through `consumeQuota`, the same atomic D1 counter `rate:read` and `signal_rate`
//    already use (issue #2075's own "harmless lower bound" line: `rate:*:ip` → `bumpCounter`).
// 2. `intake_source_count:<source>` took `source` from the caller — the endpoint is open, no Bearer —
//    and only truncated it to 40 characters. That caps the length of a key and does nothing at all to
//    the number of keys. It is now bucketed to a finite whitelist.
//
// The properties worth pinning: the increment is atomic (a burst does not lose counts), the windows
// bucket the way the comments claim (and are colon-free, so the KV fallback key is unambiguous), the
// limits fire at the same boundary they always did (ten pass, the eleventh is refused), and the
// whole family leaves **no `kv_store` key** — which is what takes it off the free tier's
// distinct-keys allowance structurally rather than by being small.
//
// Run: node --test workers/rate-limits-counter.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, {
  consumeQuota, legacyCounterKey, intakeSourceBucket, INTAKE_SOURCE_WHITELIST,
  rateWindowMinute, rateWindowHour, rateWindowTenMinutes,
} from './register-proxy-sw.js';
import { withKvStore } from './_test-kv-store.mjs';
import { testToken } from './_test-token.mjs';

/** A D1 stand-in that implements the `counters` upsert, so the quota path is the real one. */
function createCountersD1() {
  const counters = new Map();
  return {
    counters,
    prepare(sql) {
      const stmt = {
        _sql: String(sql),
        _bound: [],
        bind(...args) { stmt._bound = args; return stmt; },
        async all() {
          if (/INSERT INTO counters/i.test(stmt._sql)) {
            const [scope, bucket, period, delta] = stmt._bound;
            const key = `${scope}|${bucket}|${period}`;
            const next = (counters.get(key) || 0) + Number(delta);
            counters.set(key, next);
            return { results: [{ count: next }] };
          }
          return { results: [] };
        },
        async run() { return { success: true, meta: { changes: 0 } }; },
      };
      return stmt;
    },
  };
}

function envWithCounters() {
  return {
    MCP_TOKEN: testToken('rate-limits-counter'),
    MISAKANET_D1: withKvStore(createCountersD1()),
  };
}

// ── windows ─────────────────────────────────────────────────────────────────

test('the windows bucket the way their names say, and contain no colon', () => {
  const at = (iso) => new Date(iso);

  assert.equal(rateWindowMinute(at('2026-10-02T02:46:28.363Z')), 'min-2026-10-02T02-46');
  assert.equal(rateWindowMinute(at('2026-10-02T02:46:59.999Z')), 'min-2026-10-02T02-46',
    'the whole minute is one window');
  assert.equal(rateWindowMinute(at('2026-10-02T02:47:00.000Z')), 'min-2026-10-02T02-47');

  assert.equal(rateWindowHour(at('2026-10-02T02:46:28.363Z')), 'hour-2026-10-02T02');
  assert.equal(rateWindowHour(at('2026-10-02T02:00:00.000Z')), 'hour-2026-10-02T02');
  assert.equal(rateWindowHour(at('2026-10-02T02:59:59.999Z')), 'hour-2026-10-02T02');
  assert.equal(rateWindowHour(at('2026-10-02T03:00:00.000Z')), 'hour-2026-10-02T03');

  assert.equal(rateWindowTenMinutes(at('2026-10-02T02:46:28.363Z')), 'tenmin-2026-10-02T02-40');
  assert.equal(rateWindowTenMinutes(at('2026-10-02T02:39:59.000Z')), 'tenmin-2026-10-02T02-30');
  assert.equal(rateWindowTenMinutes(at('2026-10-02T02:00:00.000Z')), 'tenmin-2026-10-02T02-00');
  assert.equal(rateWindowTenMinutes(at('2026-10-02T02:09:59.999Z')), 'tenmin-2026-10-02T02-00',
    'ten-minute buckets, not six-minute ones');

  // Colon-free, the same reason `readBurstPeriod` is: the KV fallback builds
  // `rate:<name>:<bucket>:<period>`, and a colon in the period makes the key ambiguous to anything
  // that parses it back (`counters-d1.test.mjs` caught exactly that once already).
  for (const w of [rateWindowMinute(), rateWindowHour(), rateWindowTenMinutes()]) {
    assert.ok(!w.includes(':'), `window keys must be colon-free, got ${w}`);
    assert.ok(w.length <= 32, `bumpCounter truncates the period to 32 chars, got ${w.length}`);
  }
});

test('the KV fallback key keeps the rate family prefix and carries the window', () => {
  const window = 'min-2026-10-02T02-46';
  assert.equal(legacyCounterKey('rate_feedback', '203.0.113.9', window),
    `rate:feedback:203.0.113.9:${window}`);
  assert.equal(legacyCounterKey('rate_intake', '203.0.113.9', 'hour-2026-10-02T02'),
    'rate:intake:203.0.113.9:hour-2026-10-02T02');
  assert.equal(legacyCounterKey('rate_connect', '203.0.113.9', 'tenmin-2026-10-02T02-40'),
    'rate:connect:203.0.113.9:tenmin-2026-10-02T02-40');
  // Unrelated scopes are untouched — this is a prefix change, not a key-space rewrite.
  assert.equal(legacyCounterKey('rate_read', '203.0.113.9', 'burst-2026-10-02T02-46'),
    'rate:read:203.0.113.9:burst-2026-10-02T02-46');
});

// ── the source ledger's key space is finite ─────────────────────────────────

test('intakeSourceBucket maps the documented sources to themselves and everything else to other', () => {
  for (const s of INTAKE_SOURCE_WHITELIST) {
    assert.equal(intakeSourceBucket(s), s, `"${s}" is a documented source and must keep its name`);
    assert.equal(intakeSourceBucket(`  ${s.toUpperCase()}  `), s, 'matching is trim + lowercase');
  }
  // The point of the change: `source` is caller-reported and the endpoint is open, so before this the
  // ledger's key count was whatever an unauthenticated caller felt like writing. Truncating to 40
  // characters capped the *length* of a key and nothing else.
  assert.equal(intakeSourceBucket('x'.repeat(10_000)), 'other');
  assert.equal(intakeSourceBucket('a-perfectly-plausible-new-client'), 'other');
  assert.equal(intakeSourceBucket('codex; DROP TABLE kv_store'), 'other');
  assert.equal(intakeSourceBucket(''), 'other');
  assert.equal(intakeSourceBucket(null), 'other');
  assert.equal(intakeSourceBucket(undefined), 'other');
  assert.equal(intakeSourceBucket(12345), 'other');

  // And the bound is the whitelist's size, not the caller's vocabulary.
  const seen = new Set();
  for (let i = 0; i < 500; i += 1) seen.add(intakeSourceBucket(`client-${i}`));
  assert.equal(seen.size, 1, '500 distinct caller strings must collapse to one bucket');
});

// ── the limits themselves ───────────────────────────────────────────────────

function feedbackRequest(ip) {
  return new Request('https://misakanet.org/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': ip },
    body: JSON.stringify({ query: 'pip install timeout', lesson_id: 'pip-timeout-mirror',
                           feedback: 'irrelevant' }),
  });
}

function intakeRequest(ip) {
  return new Request('https://misakanet.org/api/intake', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': ip },
    body: JSON.stringify({ type: 'diagnostic', source: 'mcp', message: 'the worker fell over' }),
  });
}

function connectRequest(ip) {
  return new Request('https://misakanet.org/mcp/connect', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': ip },
  });
}

test('each limit holds at its own boundary: 10/min, 10/hour, 3/10min', async () => {
  const env = envWithCounters();

  const feedback = [];
  for (let i = 0; i < 11; i += 1) feedback.push((await worker.fetch(feedbackRequest('203.0.113.20'), env)).status);
  assert.ok(feedback.slice(0, 10).every((c) => c === 200), `${JSON.stringify(feedback)}`);
  assert.equal(feedback[10], 429, 'the eleventh feedback is over the ten-per-minute limit');

  const intake = [];
  for (let i = 0; i < 11; i += 1) intake.push((await worker.fetch(intakeRequest('203.0.113.21'), env)).status);
  assert.ok(intake.slice(0, 10).every((c) => c === 200), `${JSON.stringify(intake)}`);
  assert.equal(intake[10], 429, 'the eleventh intake is over the ten-per-hour limit');

  const connect = [];
  for (let i = 0; i < 4; i += 1) connect.push((await worker.fetch(connectRequest('203.0.113.22'), env)).status);
  assert.ok(connect.slice(0, 3).every((c) => c === 200), `${JSON.stringify(connect)}`);
  assert.equal(connect[3], 429, 'the fourth pairing code is over the three-per-ten-minutes limit');

  // The limit is per address, not global: a second address in the same window has its own budget.
  assert.equal((await worker.fetch(feedbackRequest('203.0.113.23'), env)).status, 200);
});

test('the increment is atomic, so a burst cannot spend the same unit twice', async () => {
  const env = envWithCounters();
  // Eleven at once, no await between them: the old read-modify-write could let several of these read
  // the same starting value and all write +1, which is how a limit of 10 admitted 15.
  const responses = await Promise.all(
    Array.from({ length: 11 }, () => worker.fetch(feedbackRequest('203.0.113.30'), env)),
  );
  const ok = responses.filter((r) => r.status === 200).length;
  const refused = responses.filter((r) => r.status === 429).length;

  assert.equal(ok + refused, 11, `every call is answered, got ${ok} ok + ${refused} refused`);
  assert.equal(ok, 10, `exactly the limit passes under concurrency, got ${ok}`);
  assert.equal(refused, 1, `exactly one is refused, got ${refused}`);

  const rows = [...env.MISAKANET_D1.counters.entries()]
    .filter(([k]) => k.startsWith('rate_feedback|203.0.113.30|'));
  assert.equal(rows.length, 1, 'one window row for the address');
  assert.equal(rows[0][1], 11, 'no increment was lost — eleven calls cost eleven increments');
});

test('the rate family leaves no kv_store key at all (#2075)', async () => {
  const env = envWithCounters();
  for (let i = 0; i < 11; i += 1) await worker.fetch(feedbackRequest('203.0.113.40'), env);
  for (let i = 0; i < 11; i += 1) await worker.fetch(intakeRequest('203.0.113.41'), env);
  for (let i = 0; i < 4; i += 1) await worker.fetch(connectRequest('203.0.113.42'), env);

  // This is the structural claim behind the migration: a same-key rewrite is free, but the free tier
  // charges for each *distinct key written per day*, and these limits were one new key per address
  // per window. In the counters table they are rows, and the KV fallback only exists for a
  // deployment with no D1 binding.
  const rateKeys = [...env.MISAKANET_D1.kvStore.keys()].filter((k) => k.startsWith('rate:'));
  assert.deepEqual(rateKeys, [], `no rate:* key may land in kv_store, got ${JSON.stringify(rateKeys)}`);
  assert.ok(env.MISAKANET_D1.counters.size >= 3,
    `the limits did run — the counters rows are where they live: ${JSON.stringify([...env.MISAKANET_D1.counters.keys()])}`);
});

test('consumeQuota fails open when the counter cannot be written', async () => {
  // A counter problem must not block the endpoint: the quota helper returns null (proceed) when the
  // increment comes back null, which is what happens with neither D1 nor KV bound.
  const refusal = await consumeQuota({}, {
    scope: 'rate_feedback', bucket: '203.0.113.50', period: rateWindowMinute(), limit: 1,
    message: 'Rate limited.',
  });
  assert.equal(refusal, null, 'no storage means no limit, not a lockout');
});
