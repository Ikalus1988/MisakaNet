// The contribution ladder's arithmetic — the part that must not drift between the cron, the
// endpoint and the panel.
//
// The two rules worth pinning are the ones a future edit is most likely to undo by accident:
//
//   * "hit" is `used + self`, but `self` is capped per day — a contributor can manufacture
//     self-hits with a loop, and an uncapped term turns the ladder into a measure of who searched
//     most;
//   * the reader's own row is found by node *or* login and is returned even when it is outside the
//     top ten, and `null` (not a zero row) when it is absent — "not on the board yet" and "rank 0"
//     are different sentences.
//
// Run: node --test workers/contribution-ladder.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';

import {
  WEIGHTS, SELF_HIT_CAP_PER_DAY, WINDOWS, TOP_N,
  selfCap, scoreEntry, identityOf, rankRows, windowSince,
} from './lib/contribution-ladder.js';

const NOW = new Date('2026-11-12T00:00:00Z');

function row(overrides = {}) {
  return {
    node: 'n1', login: null, name: 'agent-one',
    used: 0, self: 0, lessons: 0, questions: 0, solved: 0,
    lastActive: '2026-11-11T10:00:00Z',
    ...overrides,
  };
}

// ── the score ───────────────────────────────────────────────────────────────────────
test('the score is the four weighted terms', () => {
  const parts = scoreEntry(row({ used: 380, self: 32, lessons: 9, questions: 3, solved: 6 }));
  const expected = (380 + 32) * 0.2 + 9 * 1 + 3 * 0.5 + 6 * 1;
  assert.equal(parts.score, Math.round(expected * 100) / 100);
  assert.equal(parts.hits, 412);
});

test('weights are the ones the docs promise', () => {
  assert.deepEqual(WEIGHTS, { hit: 0.2, lesson: 1, question: 0.5, solved: 1 });
  assert.equal(TOP_N, 10);
});

test('self-hits are capped per day, and the uncounted part is reported', () => {
  const parts = scoreEntry(row({ used: 10, self: 1000 }), { days: WINDOWS.week });
  assert.equal(parts.hits, 1010, 'the displayed total is still what happened');
  assert.equal(parts.hitsCounted, 10 + SELF_HIT_CAP_PER_DAY * 7, 'the counted total is capped');
  assert.equal(parts.selfCapped, 1000 - SELF_HIT_CAP_PER_DAY * 7);
  assert.equal(parts.score, Math.round(((10 + SELF_HIT_CAP_PER_DAY * 7) * 0.2) * 100) / 100);
});

test('the all-time window has no self-hit allowance worth counting', () => {
  assert.equal(selfCap(WINDOWS.all), Infinity);
  const parts = scoreEntry(row({ self: 5000 }), { days: WINDOWS.all });
  assert.equal(parts.selfCapped, 0);
});

test('a self-hit cap of zero would make the term disappear — the constant is not zero', () => {
  assert.ok(SELF_HIT_CAP_PER_DAY > 0);
});

test('nonsense counters count as zero, never as NaN', () => {
  const parts = scoreEntry(row({ used: null, self: undefined, lessons: -3, questions: 'x', solved: NaN }));
  assert.equal(parts.score, 0);
  assert.equal(parts.hits, 0);
});

// ── identity ───────────────────────────────────────────────────────────────────────
test('a row says which identity marks it carries', () => {
  assert.equal(identityOf(row()), 'node');
  assert.equal(identityOf(row({ node: null, login: 'takomitkm' })), 'github');
  assert.equal(identityOf(row({ node: 'n1', login: 'takomitkm' })), 'both');
});

// ── ranking ────────────────────────────────────────────────────────────────────────
test('ranking orders by score and breaks ties by name', () => {
  const out = rankRows([
    row({ node: 'b', name: 'beta', used: 10 }),
    row({ node: 'a', name: 'alpha', used: 10 }),
    row({ node: 'c', name: 'gamma', used: 30 }),
  ]);
  assert.deepEqual(out.top.map((r) => r.name), ['gamma', 'alpha', 'beta']);
  assert.deepEqual(out.top.map((r) => r.rank), [1, 2, 3]);
});

test('rows with nothing in the window are dropped, not shown as zeroes', () => {
  const out = rankRows([row({ name: 'idle' }), row({ name: 'active', lessons: 1 })]);
  assert.deepEqual(out.top.map((r) => r.name), ['active']);
  assert.equal(out.total, 1);
});

test('the window drops rows whose last activity is older than the cut', () => {
  const out = rankRows([
    row({ name: 'old', lessons: 1, lastActive: '2026-10-01T00:00:00Z' }),
    row({ name: 'new', lessons: 1, lastActive: '2026-11-11T00:00:00Z' }),
  ], { days: WINDOWS.week, since: '2026-11-05T00:00:00Z' });
  assert.deepEqual(out.top.map((r) => r.name), ['new']);
});

test('the top is limited, the total is not', () => {
  const rows = Array.from({ length: 25 }, (_, i) => row({ node: `n${i}`, name: `agent-${String(i).padStart(2, '0')}`, used: 25 - i }));
  const out = rankRows(rows);
  assert.equal(out.top.length, TOP_N);
  assert.equal(out.total, 25);
});

// ── the reader's own row ───────────────────────────────────────────────────────────
test('the reader is found by node even outside the top ten', () => {
  const rows = Array.from({ length: 15 }, (_, i) => row({ node: `n${i}`, name: `a${i}`, used: 100 - i }));
  rows.push(row({ node: 'mine', name: 'me', used: 1 }));
  const out = rankRows(rows, { node: 'mine' });
  assert.equal(out.me.name, 'me');
  assert.equal(out.me.rank, 16);
  assert.ok(!out.top.some((r) => r.name === 'me'), 'not in the top ten');
});

test('a bound contributor is found by login as well as node', () => {
  const rows = [row({ node: 'n1', login: 'takomitkm', name: 'takomitkm', used: 5 })];
  assert.equal(rankRows(rows, { login: 'takomitkm' }).me.name, 'takomitkm');
  assert.equal(rankRows(rows, { node: 'n1' }).me.name, 'takomitkm');
});

test('no row in the window means me is null, not rank zero', () => {
  const out = rankRows([row({ name: 'someone', used: 3 })], { node: 'not-there' });
  assert.equal(out.me, null);
});

// ── windows ────────────────────────────────────────────────────────────────────────
test('the three windows cut at the same place for every caller', () => {
  const week = windowSince('week', NOW);
  assert.equal(week.days, 7);
  assert.equal(week.since, '2026-11-05T00:00:00.000Z');

  const month = windowSince('month', NOW);
  assert.equal(month.days, 30);

  const all = windowSince('all', NOW);
  assert.deepEqual(all, { days: null, since: null });
});

test('an unknown window name is all-time, not a crash', () => {
  assert.deepEqual(windowSince('decade', NOW), { days: null, since: null });
});
