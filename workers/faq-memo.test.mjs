// The FAQ half of search reads every answered question; that read must not repeat per request.
//
// Measured 2026-11-27, after the read-burst memo landed: a warm search still prepared three D1
// statements, one of them this unconditional `SELECT … FROM questions WHERE status='answered'`
// (117 rows, ~240 KB of answers) — on every search, including the ones that match nothing. The phase
// instrumentation does not cover it, so it appeared only as "unaccounted" time.
//
// These tests pin the two halves that matter: the read happens once per isolate window (so the
// optimisation is real), and it still happens at all (so a cache cannot silently answer "no FAQ"
// forever).
import assert from 'node:assert/strict';
import test, { beforeEach } from 'node:test';
import worker, { resetFaqMemo } from './register-proxy-sw.js';

const FAQ_ROW = {
  issue_number: 1362,
  problem: 'docker exit code 137 out of memory container crash',
  answer: 'Increase the container memory limit, or shrink the heap.',
  issue_url: 'https://github.com/Ikalus1988/MisakaNet/issues/1362',
  answered_at: '2026-10-01T00:00:00Z',
};

function countingEnv(questionRows = [FAQ_ROW]) {
  const statements = [];
  const prepare = (sql) => {
    const result = () => {
      statements.push(sql);
      if (/FROM questions/i.test(sql)) return { results: questionRows };
      if (/FROM kv_store/i.test(sql)) return { results: [] };
      if (/INSERT INTO counters/i.test(sql)) return { results: [{ count: 1 }] };
      return { results: [] };
    };
    const stmt = { bind: () => stmt, all: async () => result(), run: async () => result(),
                   first: async () => result() };
    return stmt;
  };
  return {
    statements,
    env: {
      MISAKANET_D1: { prepare, batch: async () => [] },
      MISAKANET_OPS_D1: { prepare, batch: async () => [] },
      EVENTS: { writeDataPoint: () => {} },
      MISAKANET_KV: null,
      MISAKANET_LESSONS_MEMO_MS: '30000',
    },
  };
}

function searchRequest() {
  return new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': '198.51.100.31' },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query: 'docker exit code 137', top: 3 } },
    }),
  });
}

const faqReads = (statements) => statements.filter((sql) => /FROM questions/i.test(sql)).length;

beforeEach(() => { resetFaqMemo(); });

test('the answered-question table is read once per isolate, not once per search', async () => {
  const { statements, env } = countingEnv();
  await worker.fetch(searchRequest(), env);
  await worker.fetch(searchRequest(), env);
  await worker.fetch(searchRequest(), env);
  assert.equal(faqReads(statements), 1,
    `the FAQ table was read ${faqReads(statements)} times for three searches — the memo is not `
    + 'absorbing repeats, which is the whole point of it');
});

test('the first search in an isolate still reads it, so an empty memo is not "no FAQ"', async () => {
  const { statements, env } = countingEnv();
  resetFaqMemo();
  await worker.fetch(searchRequest(), env);
  assert.equal(faqReads(statements), 1,
    'a cold isolate must read the table once; a cache that never reads would answer "no FAQ" forever');
});

test('a refresh sees a newly answered question inside a fresh isolate', async () => {
  // The window is per isolate, and a new one starts empty. This is the property that bounds the
  // staleness: an answer becomes matchable at most one window after it is written.
  const first = countingEnv([]);
  await worker.fetch(searchRequest(), first.env);
  assert.equal(faqReads(first.statements), 1);

  resetFaqMemo();
  const second = countingEnv([FAQ_ROW]);
  await worker.fetch(searchRequest(), second.env);
  assert.ok(faqReads(second.statements) >= 1,
    'a fresh isolate must see the answer that was written after the previous isolate read');
});
