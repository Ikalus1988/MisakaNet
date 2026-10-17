// `/api/health` must watch the path a search takes (2026-10-17).
//
// Measured: the endpoint answered `status: ok` for a whole day while `/api/lessons` returned 502 and
// every `misakanet_search` handed the caller `D1_ERROR: … exceeded D1's free tier daily row read
// limit`. It watched KV writes and never the read path. The same defect class as #1822 — "a dead
// subsystem can hide when nothing depends on it" — one layer over.
//
// Run: node --test workers/health-lessons-read.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import {
  d1ErrorKind, healthWithLessons, lastLessonsReadOf, loadLessons, probeLessonsRead,
  resetLessonsReadState,
} from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('health-lessons');

const QUOTA = new Error(
  "D1_ERROR: Your account has exceeded D1's free tier daily row read limit. Upgrade to a paid plan or "
  + 'wait until tomorrow (midnight UTC) to continue.',
);

function d1That(handler, seen = []) {
  const stmt = {
    bind() { return stmt; },
    all: handler,
    run: handler,
    first: handler,
    raw: handler,
  };
  return {
    prepare(text) { seen.push(String(text)); return stmt; },
    exec: handler,
    batch: handler,
  };
}

const SNAPSHOT = [{ id: 'a', title: 'A', domain: 'python', status: 'published', tags: ['pip'], path: 'lessons/core/a.md' }];

function withSnapshotFetch(fn) {
  const real = globalThis.fetch;
  globalThis.fetch = async () => ({
    ok: true,
    status: 200,
    json: async () => ({ content: Buffer.from(JSON.stringify(SNAPSHOT)).toString('base64'), encoding: 'base64' }),
  });
  return fn().finally(() => { globalThis.fetch = real; });
}

test('the probe reports a quota refusal instead of throwing', async () => {
  const read = await probeLessonsRead({ MISAKANET_D1: d1That(async () => { throw QUOTA; }) });
  assert.equal(read.ok, false);
  assert.equal(read.error_kind, 'quota');
});

test('the probe is one row, and says ok when D1 answers', async () => {
  let sql = '';
  const env = { MISAKANET_D1: d1That(async () => ({ results: [{ ok: 1 }] })) };
  const original = env.MISAKANET_D1.prepare;
  env.MISAKANET_D1.prepare = (text) => { sql = text; return original(); };
  assert.deepEqual(await probeLessonsRead(env), { ok: true, source: 'd1' });
  assert.match(sql, /LIMIT 1/, 'a health probe must not read the corpus');
});

test('no D1 binding is "unknown", not a failure', async () => {
  assert.deepEqual(await probeLessonsRead({}), { ok: null, source: 'no-d1' });
});

test('the classifier separates the three responses the operator has', () => {
  assert.equal(d1ErrorKind(QUOTA), 'quota');
  assert.equal(d1ErrorKind(new Error('no such table: lessons')), 'binding');
  assert.equal(d1ErrorKind(new Error('network timeout')), 'transport');
  assert.equal(d1ErrorKind(new Error('something else')), 'error');
});

test('a failing read turns the endpoint degraded, beside a healthy KV', () => {
  const composed = healthWithLessons({ status: 'ok' }, { ok: false, error_kind: 'quota' });
  assert.equal(composed.status, 'degraded');
  assert.match(composed.reason, /lessons read failing: quota/);
});

test('a healthy read leaves the endpoint alone, and a KV failure is not overwritten', () => {
  assert.deepEqual(healthWithLessons({ status: 'ok' }, { ok: true, source: 'd1' }), { status: 'ok', reason: '' });
  const both = healthWithLessons({ status: 'degraded', reason: 'kv writes failing: 5/5' }, { ok: false, error_kind: 'quota' });
  assert.equal(both.status, 'degraded');
  assert.match(both.reason, /kv writes failing: 5\/5/);
  assert.match(both.reason, /lessons read failing: quota/);
});

test('after a refusal, the next read does not ask D1 again (cooldown)', () =>
  withSnapshotFetch(async () => {
    resetLessonsReadState();
    const sql = [];
    const env = { MISAKANET_D1: d1That(async () => { throw QUOTA; }, sql), REGISTER_TOKEN: TOKEN };
    await loadLessons(env);
    assert.equal(lastLessonsReadOf().error_kind, 'quota');
    // Count only the corpus read: the cache layer's own `kv_store` lookups go through the same stub
    // and would otherwise be counted as "a retry".
    sql.length = 0;
    const second = await loadLessons(env);
    assert.deepEqual(second.map((l) => l.id), ['a'], 'the snapshot still answers during the cooldown');
    const retried = sql.filter((text) => /FROM lessons/i.test(text));
    assert.deepEqual(retried, [], 'D1 must not be retried while the quota is known to be exhausted');
    assert.equal(lastLessonsReadOf().source, 'snapshot-cooldown');
    resetLessonsReadState();
  }));
