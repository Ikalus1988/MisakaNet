// The D1 meter: every statement's cost, read from `D1Meta.rows_read`, at the one place queries pass.
//
// Two incidents made this necessary — 2026-10-21 (68,892 rows per call) and 2026-11-24 (10.4M rows per
// call, 90% of the account's monthly reads). Both looked fine from inside the code: correct answers,
// ordinary latency, no error. The number that would have shown it was in the result object the whole
// time.
//
// Run: node --test workers/d1-cost-meter.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import {
  costSnapshot,
  flushQueryCost,
  meterD1,
  resetCost,
  statementKey,
} from './lib/d1-cost.js';

/** A D1 binding double whose results carry the same `meta` shape D1 returns. */
function fakeBinding({ rowsPerCall = 0, throwOnPrepare = false } = {}) {
  const calls = [];
  const db = {
    prepare(sql) {
      if (throwOnPrepare) throw new Error("prepare refused");
      calls.push(sql);
      let bound = 0;
      const stmt = {
        async all() {
          return { results: [], meta: { rows_read: rowsPerCall + bound, rows_written: 0 } };
        },
        async run() {
          return { success: true, meta: { rows_read: rowsPerCall + bound, rows_written: 2 } };
        },
        async first() {
          return null; // D1 returns no `meta` here — the meter counts the call, not the rows
        },
        async raw() {
          return [];
        },
        bind(...args) {
          bound = args.length;
          return stmt;
        },
      };
      return stmt;
    },
  };
  return { db, prepared: calls };
}

test('the key is stable across whitespace and different across statements', () => {
  assert.equal(statementKey("SELECT  a,\n  b FROM t"), statementKey("SELECT a, b FROM t"));
  assert.notEqual(statementKey("SELECT a FROM t"), statementKey("SELECT b FROM t"));
  assert.match(statementKey("SELECT 1"), /^[0-9a-f]{8}$/);
});

test('rows read are accumulated per statement', async () => {
  resetCost();
  const { db } = fakeBinding({ rowsPerCall: 1000 });
  const metered = meterD1(db);
  await metered.prepare("SELECT a FROM t").all();
  await metered.prepare("SELECT a FROM t").all();
  await metered.prepare("SELECT b FROM u").run();

  const snapshot = costSnapshot();
  const first = snapshot.find((row) => row.head === "SELECT a FROM t");
  assert.equal(first.calls, 2);
  assert.equal(first.rows, 2000);
  assert.equal(first.rows_per_call, 1000);
  const second = snapshot.find((row) => row.head === "SELECT b FROM u");
  assert.equal(second.rows, 1000);
  assert.equal(second.written, 2, "a run() result carries rows_written too");
});

test('bind() keeps the meter attached', async () => {
  resetCost();
  const { db } = fakeBinding({ rowsPerCall: 10 });
  const metered = meterD1(db);
  await metered.prepare("SELECT a FROM t WHERE id = ?").bind(7).all();
  const [row] = costSnapshot();
  assert.equal(row.calls, 1);
  assert.equal(row.rows, 11, "the fake adds one row per bind; one bind was passed");
});

test('a call with no meta counts the call and no rows', async () => {
  resetCost();
  const { db } = fakeBinding();
  const metered = meterD1(db);
  await metered.prepare("SELECT one").first();
  const [row] = costSnapshot();
  assert.equal(row.calls, 1);
  assert.equal(row.rows, 0, "first() returns no meta — this is the documented blind spot");
});

test('the same binding is metered once', () => {
  const { db } = fakeBinding();
  assert.equal(meterD1(db), meterD1(db));
  assert.equal(meterD1(null), null);
  assert.equal(meterD1("not a binding"), "not a binding");
});

test('a binding that cannot be wrapped comes back untouched instead of breaking queries', async () => {
  const hostile = {
    prepare() { throw new Error("no"); },
  };
  const metered = meterD1(hostile);
  assert.equal(typeof metered.prepare, "function");
  assert.throws(() => metered.prepare("SELECT 1"), /no/,
    "the meter must not swallow the binding's own errors");
});

test('the flush writes two counters per statement, only above the floor, then resets', async () => {
  resetCost();
  const written = [];
  const bump = async (scope, bucket, period, delta) => { written.push({ scope, bucket, period, delta }); };
  const { db } = fakeBinding({ rowsPerCall: 50_000 });
  const metered = meterD1(db);
  await metered.prepare("SELECT big FROM t").all();
  await metered.prepare("SELECT small FROM u").bind(1).all();   // 50,001 — still above the floor

  const result = await flushQueryCost(bump, "2026-11-24");
  assert.equal(result.statements, 2);
  assert.deepEqual(written.map((row) => row.bucket).sort(), [
    `${statementKey("SELECT big FROM t")}:calls`, `${statementKey("SELECT big FROM t")}:rows`,
    `${statementKey("SELECT small FROM u")}:calls`, `${statementKey("SELECT small FROM u")}:rows`,
  ].sort());
  assert.ok(written.every((row) => row.scope === "query_cost" && row.period === "2026-11-24"));
  assert.equal(costSnapshot().length, 0, "the flush starts the isolate over");
});

test('a cheap statement is not flushed at all', async () => {
  resetCost();
  const written = [];
  const { db } = fakeBinding({ rowsPerCall: 3 });
  await meterD1(db).prepare("SELECT tiny FROM t").all();
  const result = await flushQueryCost(async (...args) => { written.push(args); }, "2026-11-24");
  assert.equal(result.flushed, 0);
  assert.equal(written.length, 0);
});

test('a failed counter write does not throw out of the cron', async () => {
  resetCost();
  const { db } = fakeBinding({ rowsPerCall: 50_000 });
  await meterD1(db).prepare("SELECT big FROM t").all();
  const result = await flushQueryCost(async () => { throw new Error("D1 down"); }, "2026-11-24");
  assert.equal(result.flushed, 0);
  assert.equal(result.statements, 1, "it still reports what it tried");
});
