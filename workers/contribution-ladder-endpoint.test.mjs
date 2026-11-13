// GET /api/leaderboard/ladder — the sidebar's contribution ladder, driven through the real worker.
//
// The endpoint's only job is to turn `contributions` rows into a ranked board without inventing
// anything: the score comes from `lib/contribution-ladder.js`, automation identities never rank,
// and the response says out loud that lesson attribution does not exist yet (`coverage`) rather
// than printing a zero that reads as "nobody used anything".
//
// Run: node --test workers/contribution-ladder-endpoint.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';

import worker from './register-proxy-sw.js';

function fakeOps(rows) {
  const statements = [];
  return {
    _statements: statements,
    prepare(sql) {
      const stmt = {
        _bound: [],
        bind(...args) { stmt._bound = args; return stmt; },
        async all() {
          statements.push({ sql, bound: stmt._bound });
          if (sql.includes('FROM contributions')) return { results: rows };
          return { results: [] };
        },
        async run() { return { success: true }; },
      };
      return stmt;
    },
  };
}

function envWith(rows) {
  const ops = fakeOps(rows);
  return { env: { MISAKANET_OPS_D1: ops }, ops };
}

async function ladder(env, query = '') {
  const res = await worker.fetch(new Request(`https://misakanet.org/api/leaderboard/ladder${query}`), env);
  const body = await res.json();
  return { status: res.status, body };
}

test('an empty table is an empty board, not an error', async () => {
  const { env } = envWith([]);
  const { status, body } = await ladder(env);
  assert.equal(status, 200);
  assert.deepEqual(body.top, []);
  assert.equal(body.me, null);
  assert.equal(body.total, 0);
  assert.equal(body.window, 'week');
  assert.equal(body.coverage.lesson_authors, 0);
});

test('rows are scored by the ladder module and ranked', async () => {
  const { env } = envWith([
    { node_id: 'MisakaA', kind: 'lesson', n: 3, last: '2026-11-11T00:00:00Z' },
    { node_id: 'MisakaA', kind: 'question', n: 2, last: '2026-11-11T00:00:00Z' },
    { node_id: 'MisakaB', kind: 'lesson', n: 1, last: '2026-11-10T00:00:00Z' },
  ]);
  const { body } = await ladder(env);
  assert.equal(body.total, 2);
  assert.equal(body.top[0].node, 'MisakaA');
  // 3 lessons ×1.0 + 2 questions ×0.5 = 4.0
  assert.equal(body.top[0].score, 4);
  assert.equal(body.top[1].score, 1);
  assert.deepEqual(body.top.map((r) => r.rank), [1, 2]);
});

test('the automation identities never reach the board', async () => {
  const { env } = envWith([
    { node_id: 'misakanet-doctor', kind: 'lesson', n: 9, last: '2026-11-11T00:00:00Z' },
    { node_id: 'github-actions[bot]', kind: 'lesson', n: 9, last: '2026-11-11T00:00:00Z' },
    { node_id: 'MisakaReal', kind: 'lesson', n: 1, last: '2026-11-11T00:00:00Z' },
  ]);
  const { body } = await ladder(env);
  assert.deepEqual(body.top.map((r) => r.node), ['MisakaReal']);
  assert.equal(body.total, 1);
});

test('the caller asks for a node and gets that row even outside the top ten', async () => {
  const rows = [{ node_id: 'Mine', kind: 'question', n: 1, last: '2026-11-11T00:00:00Z' }];
  for (let i = 0; i < 12; i++) {
    rows.push({ node_id: `Big${String(i).padStart(2, '0')}`, kind: 'lesson', n: 10, last: '2026-11-11T00:00:00Z' });
  }
  const { env } = envWith(rows);
  const { body } = await ladder(env, '?node=Mine');
  assert.equal(body.me.node, 'Mine');
  assert.equal(body.me.rank, 13);
  assert.equal(body.top.length, 10);
  assert.ok(!body.top.some((r) => r.node === 'Mine'));
});

test('the window is cut in SQL, and all-time binds no cut', async () => {
  const { env, ops } = envWith([]);
  await ladder(env, '?window=week');
  const weekly = ops._statements.find((s) => s.sql.includes('FROM contributions'));
  assert.ok(weekly.sql.includes('created_at >='));
  assert.equal(weekly.bound.length, 1);

  const all = envWith([]);
  await ladder(all.env, '?window=all');
  const allTime = all.ops._statements.find((s) => s.sql.includes('FROM contributions'));
  assert.ok(!allTime.sql.includes('created_at >='));
  assert.equal(allTime.bound.length, 0);
});

test('an unknown window falls back to a week rather than failing', async () => {
  const { env } = envWith([]);
  const { status, body } = await ladder(env, '?window=decade');
  assert.equal(status, 200);
  assert.equal(body.window, 'week');
});

test('a broken store answers 503 without echoing the D1 error', async () => {
  // CodeQL js/stack-trace-exposure #258: the D1 message names tables and SQL, so it goes to Workers
  // Logs and the caller gets a stable code. The first version of this handler returned `detail`.
  const d1 = {
    prepare() {
      return {
        bind() { return this; },
        async all() { throw new Error("D1_ERROR: no such table: contributions (SQL: SELECT node_id...)"); },
        async run() { throw new Error("D1_ERROR: no such table: contributions"); },
      };
    },
  };
  const res = await worker.fetch(new Request("https://misakanet.org/api/leaderboard/ladder"), { MISAKANET_OPS_D1: d1 });
  const body = await res.json();
  assert.equal(res.status, 503);
  assert.equal(body.code, "storage_unavailable");
  assert.equal(body.detail, undefined);
  assert.ok(!JSON.stringify(body).includes("no such table"), "the D1 message must not reach the caller");
});

test('a GitHub handle is the display name, and the pseudonym stays on the row', async () => {
  // The agreed design: two identity methods on one board — a GitHub name when the contributor has
  // one, the node pseudonym otherwise. The node id is never dropped: it is what `?node=` matches.
  const { env } = envWith([
    { node_id: "MisakaX", kind: "lesson", login: "octocat", n: 2, last: "2026-11-11T00:00:00Z" },
    { node_id: "MisakaY", kind: "question", login: null, n: 1, last: "2026-11-11T00:00:00Z" },
  ]);
  const { body } = await ladder(env);
  const github = body.top.find((row) => row.node === "MisakaX");
  const pseudonym = body.top.find((row) => row.node === "MisakaY");
  assert.equal(github.login, "octocat");
  assert.equal(github.name, "octocat");
  assert.equal(github.identity, "both");
  assert.equal(pseudonym.login, "");
  assert.equal(pseudonym.name, "MisakaY");
  assert.equal(pseudonym.identity, "node");
});
