// Unit tests for the public reputation leaderboard (Issue #908).
import assert from 'node:assert/strict';
import test from 'node:test';

import worker, {
  buildReputationLeaderboard,
  handleReputationLeaderboard,
} from './register-proxy-sw.js';

const NOW = Date.parse('2026-08-13T12:00:00Z');
const SOURCE = {
  _last_updated: '2026-08-13T11:00:00Z',
  contributors: {
    alice: {
      total_points: 15,
      last_activity: '2026-08-12T12:00:00Z',
      history: [
        { timestamp: '2026-07-01T12:00:00Z', points: 10 },
        { timestamp: '2026-08-12T12:00:00Z', points: 5 },
      ],
    },
    bob: {
      total_points: 20,
      last_activity: '2026-08-13T10:00:00Z',
      history: [{ timestamp: '2026-08-13T10:00:00Z', points: 20 }],
    },
    carol: {
      total_points: 3,
      last_activity: '2026-08-01T10:00:00Z',
      history: [{ timestamp: '2026-08-01T10:00:00Z', points: 3 }],
    },
  },
};

test('all-time ranks by the ledger total and adds stable ranks', () => {
  const rows = buildReputationLeaderboard(SOURCE, 'all-time', NOW);
  assert.deepEqual(rows.map((row) => row.login), ['bob', 'alice', 'carol']);
  assert.deepEqual(rows.map((row) => row.rank), [1, 2, 3]);
  assert.equal(rows[1].points, 15);
  assert.equal(rows[1].totalPoints, 15);
});

test('monthly and weekly filters use timestamped history', () => {
  const monthly = buildReputationLeaderboard(SOURCE, 'monthly', NOW);
  assert.deepEqual(monthly.map((row) => row.login), ['bob', 'alice', 'carol']);
  assert.deepEqual(monthly.map((row) => row.points), [20, 5, 3]);

  const weekly = buildReputationLeaderboard(SOURCE, 'weekly', NOW);
  assert.deepEqual(weekly.map((row) => row.login), ['bob', 'alice']);
  assert.deepEqual(weekly.map((row) => row.points), [20, 5]);
});

test('handler validates periods and exposes the canonical source contract', async () => {
  const invalid = await handleReputationLeaderboard(
    new Request('https://misakanet.org/api/insights/reputation-leaderboard?period=yearly'),
    { REPUTATION_DATA: SOURCE },
  );
  assert.equal(invalid.status, 400);

  const response = await handleReputationLeaderboard(
    new Request('https://misakanet.org/api/insights/reputation-leaderboard?period=weekly'),
    { REPUTATION_DATA: SOURCE },
  );
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.period, 'weekly');
  assert.equal(body.meta.pointsSource, 'data/contributor-points.json');
  assert.equal(body.meta.cashValue, false);
  assert.ok(body.leaderboard.every((row) => row.rank <= 20));
});

test('public worker route works without REGISTER_TOKEN', async () => {
  const response = await worker.fetch(
    new Request('https://misakanet.org/api/insights/reputation-leaderboard'),
    { REPUTATION_DATA: SOURCE },
  );
  assert.equal(response.status, 200);
});
