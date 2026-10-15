// The contributor leaderboard: the scoring, the exclusion rule, and the state that used to be git.
//
// Why these tests exist at all is a measurement, not a style preference. The public board this
// project publishes ranked `github-actions[bot]` at **#2** and `misakanet-sync-bot` at **#5** —
// measured 2026-09-25, 23 entries in `data/leaderboard.json`. The exclusion list named dependabot,
// pre-commit-ci and cloudflare, three apps that barely appear here, and missed the two that were
// actually on the board. A list is the wrong shape for this: it only removes the bots somebody
// remembered. `isAutomationLogin` matches by shape (`[bot]`) plus this repository's own identities.
//
// The rule also has to be about *shape* because contributors come from commit authors:
// `author.user.login` falls back to the raw git author name whenever no GitHub account matches, so
// anything a `git config user.name` produced can reach a public board. `misakanet-sync-bot` has no
// `/users/` page at all and still ranked #5.
//
// What this does **not** claim: to tell whether a human is behind an account. GitHub cannot, and
// this project's own `agent_type` is self-declared and unverified.
//
// Run: node --test workers/contributor-leaderboard.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import worker from './register-proxy-sw.js';
import {
  SELF_IDENTITIES, isAutomationLogin, prSizeFactor, recencyBonus,
  boardMoved, shouldNotifyTopChange, scoreBoard,
} from './lib/contributor-leaderboard.js';
import { testToken } from './_test-token.mjs';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..');
const NOW = Date.parse('2026-10-15T00:00:00Z');
const daysAgoISO = (d) => new Date(NOW - d * 86_400_000).toISOString();

// ── the identities that were on the board ───────────────────────────────────────────
test('the project’s own identities are excluded', () => {
  for (const login of [
    'github-actions[bot]',    // the regression: rank #2 on the public board
    'misakanet-sync-bot',     // rank #5, and not a GitHub user at all
    'misakanet-bot',
    'misakanet agent',
    'misakanet-agent',
    'github-actions',
    'actions-user',
    'dependabot[bot]',
    'pre-commit-ci[bot]',
    'cloudflare-workers-and-pages[bot]',
    'GITHUB-ACTIONS[BOT]',    // case must not matter; the scorer lowercases
  ]) {
    assert.equal(isAutomationLogin(login), true, `${login} would appear as a contributor`);
  }
});

test('a contributor account is not excluded', () => {
  // The other direction: a filter that eats real contributors is worse than no filter.
  for (const login of ['zsxh1990', 'huyhoang2k5', '2lll5', 'yashraj4', 'misakanet-fan']) {
    assert.equal(isAutomationLogin(login), false, login);
  }
});

test('any GitHub app is excluded by shape, not by name', () => {
  // `[bot]` is GitHub’s own convention for an App, so a new App needs no list entry.
  for (const name of ['some-new-app[bot]', 'renovate[bot]', 'copilot-swe-agent[bot]']) {
    assert.equal(isAutomationLogin(name), true, name);
  }
});

/** Every `git config user.name "X"` the repository’s workflows set. */
function workflowIdentities() {
  const dir = join(REPO, '.github', 'workflows');
  const names = new Set();
  for (const file of readdirSync(dir).filter((f) => f.endsWith('.yml'))) {
    const text = readFileSync(join(dir, file), 'utf8');
    for (const m of text.matchAll(/user\.name\s+["']([^"']+)["']/g)) names.add(m[1]);
  }
  return names;
}

test('every workflow identity is excluded', () => {
  // A new bot in a workflow must not need a second edit in the scorer. The identities that publish
  // commits are discoverable from the workflows, so the rule is checked against them instead of
  // remembered. This is the gate the original defect lacked.
  const names = workflowIdentities();
  assert.ok(names.size, 'no git identities found in the workflows — the regex or the layout changed');
  const missing = [...names].filter((n) => !isAutomationLogin(n)).sort();
  assert.deepEqual(missing, [], `these workflow identities would appear on the public board: ${missing}`);
});

test('the default sign-off identity is excluded', () => {
  // `scripts/adopt_pr.py` sets the identity most bot commits are authored with.
  const src = readFileSync(join(REPO, 'scripts', 'adopt_pr.py'), 'utf8');
  const match = src.match(/DEFAULT_SIGNOFF_NAME\s*=\s*"([^"]+)"/);
  assert.ok(match, 'the sign-off identity moved');
  assert.equal(isAutomationLogin(match[1]), true, match[1]);
});

test('the scorer applies the rule rather than a literal list', () => {
  // The rule is worthless if the scoring path filters with its own set.
  const src = readFileSync(join(REPO, 'workers', 'lib', 'contributor-leaderboard.js'), 'utf8');
  assert.match(src, /!isAutomationLogin\(/, 'the scored rows are no longer filtered by the rule');
  assert.doesNotMatch(src, /EXCLUDE_LOGINS/, 'the hardcoded list is back');
});

test('the scored board carries no automation identity', () => {
  const board = scoreBoard([
    { author: { user: { login: 'zsxh1990' } }, committedDate: daysAgoISO(1) },
    { author: { user: { login: 'github-actions[bot]' } }, committedDate: daysAgoISO(1) },
    // `name` lives *inside* `author` in the GraphQL shape: it is the raw git author name, which is
    // what GraphQL returns when no GitHub account matches the commit.
    { author: { user: null, name: 'misakanet-sync-bot' }, committedDate: daysAgoISO(2) },
    { author: { user: null, name: 'misakanet agent' }, committedDate: daysAgoISO(2) },
    { author: { user: { login: 'ikalus1988' } }, committedDate: daysAgoISO(2) },
  ], [], NOW);
  assert.deepEqual(board.map((r) => r.login), ['zsxh1990']);
});

test('a commit with neither a login nor a git name scores as "unknown"', () => {
  // Pinned because it looks like a bug and is not: the Python fell back to the literal string
  // `unknown` too, and an author object can come back null. Excluding it would be a change in
  // scoring scope, not a port, so it is recorded rather than quietly fixed.
  const board = scoreBoard([
    { author: null, committedDate: daysAgoISO(1) },
    { author: {}, committedDate: daysAgoISO(1) },
  ], [], NOW);
  assert.deepEqual(board.map((r) => r.login), ['unknown']);
});

// ── scoring ────────────────────────────────────────────────────────────────────────
test('the recency decay is a 30-day half-life with a 10% floor', () => {
  const board = scoreBoard(
    [{ author: { user: { login: 'solo' } }, committedDate: daysAgoISO(0) }],
    [], NOW,
  );
  // One commit, no PR data → sizeMultiplier 0.5, recency +0.5: (1.0 * 0.5) + 0.5 = 1.0
  assert.equal(board[0].score, 1);

  // An old commit decays toward, but never below, 10% of its value.
  const old = scoreBoard(
    [{ author: { user: { login: 'solo' } }, committedDate: daysAgoISO(3650) }],
    [], NOW,
  );
  const decay = (old[0].score - 0) / 0.5; // strip the 0.5 recency bonus (3650 days → none)
  assert.ok(decay >= 0.1, `the floor is gone: ${decay}`);
});

test('the median PR size multiplies the commit score', () => {
  const commit = [{ author: { user: { login: 'a' } }, committedDate: daysAgoISO(0) }];
  const noPrs = scoreBoard(commit, [], NOW)[0].score;
  const withPrs = scoreBoard(commit, [
    { user: { login: 'a' }, merged_at: daysAgoISO(1), additions: 99, deletions: 1 },
  ], NOW)[0].score;
  // log10(100)+1 = 3, /2 = 1.5 vs the 0.5 default → 1.5*1.0 + 0.5 = 2.0, against 0.5*1.0 + 0.5 = 1.0.
  assert.equal(withPrs, 2);
  assert.ok(withPrs > noPrs);
});

test('an unparseable commit date scores as a year old, not as skipped', () => {
  const board = scoreBoard([
    { author: { user: { login: 'a' } }, committedDate: 'not-a-date' },
    { author: { user: { login: 'b' } } }, // no date at all: skipped, as in the Python
  ], [], NOW);
  assert.deepEqual(board.map((r) => r.login), ['a']);
  assert.ok(board[0].score > 0);
});

test('recency bonus steps at 7 and 30 days', () => {
  assert.equal(recencyBonus(0), 0.5);
  assert.equal(recencyBonus(7), 0.5);
  assert.equal(recencyBonus(8), 0.2);
  assert.equal(recencyBonus(30), 0.2);
  assert.equal(recencyBonus(31), 0);
  assert.equal(prSizeFactor(1, 0).toFixed(3), '1.000');
});

// ── the two predicates, which answer different questions ───────────────────────────
test('boardMoved ignores the join separator', () => {
  // A plain `.join('')` comparison would call these two boards identical.
  assert.equal(boardMoved(
    [{ login: 'ab', score: 1 }, { login: 'c', score: 2 }],
    [{ login: 'a', score: 1 }, { login: 'bc', score: 2 }],
  ), true);
});

test('boardMoved is about any visible row, not only the top', () => {
  const base = [{ login: 'a', score: 10 }, { login: 'b', score: 5 }];
  assert.equal(boardMoved(base, [{ login: 'a', score: 10 }, { login: 'b', score: 5 }]), false);
  // A dropped contributor with an untouched #1: the older predicate threw this away (2026-09-25).
  assert.equal(boardMoved(base, [{ login: 'a', score: 10 }]), true);
  assert.equal(boardMoved(base, [{ login: 'a', score: 10 }, { login: 'b', score: 9 }]), true);
  assert.equal(boardMoved(base, [{ login: 'a', score: 10 }, { login: 'b', score: 5.4 }]), false);
});

test('the notification predicate keeps its conjunction, quirk included', () => {
  // Reproduces the Python’s `login changed and score moved by more than 0.5`. A change of #1
  // between two near-equal scores stays silent — that is the shipped behaviour, preserved on
  // purpose so a storage migration cannot be blamed for a later change in notification scope.
  assert.equal(shouldNotifyTopChange(null, [{ login: 'a', score: 1 }]), true, 'first run records the board');
  assert.equal(shouldNotifyTopChange([{ login: 'a', score: 10 }], [{ login: 'b', score: 12 }]), true);
  assert.equal(shouldNotifyTopChange([{ login: 'a', score: 10 }], [{ login: 'b', score: 10.3 }]), false);
  assert.equal(shouldNotifyTopChange([{ login: 'a', score: 10 }], [{ login: 'a', score: 30 }]), false);
});

// ── the cadence, which is the reason the churn stopped ─────────────────────────────
test('the ranking runs on a daily cron, not on every tick', () => {
  const toml = readFileSync(join(REPO, 'workers', 'wrangler.toml'), 'utf8');
  const line = toml.match(/^crons\s*=\s*(\[[^\]]*\])/m);
  assert.ok(line, 'workers/wrangler.toml has no crons array — the trigger moved?');
  const crons = [...line[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]);
  assert.ok(crons.includes('17 3 * * *'), `the daily leaderboard cron is gone: ${JSON.stringify(crons)}`);

  // And the job is gated on that exact expression, not merely present: the worker still ticks
  // every 15 minutes, and a 2,000-commit walk must not run 96 times a day.
  const src = readFileSync(join(REPO, 'workers', 'register-proxy-sw.js'), 'utf8');
  assert.match(src, /controller\.cron === LEADERBOARD_CRON/,
    'the leaderboard refresh is no longer gated on its own cron expression');
});

// ── the state, and the absence of a write endpoint ─────────────────────────────────
/** A D1 stand-in implementing exactly the `kv_store` reads and writes `storeGet`/`storePut` use. */
function createKvStoreD1() {
  const rows = new Map();
  const writes = [];
  return {
    rows,
    writes,
    prepare(sql) {
      const stmt = {
        _args: [],
        bind(...args) { stmt._args = args; return stmt; },
        async run() {
          if (/^\s*CREATE/i.test(sql)) return { success: true };
          const [key, value, expires] = stmt._args;
          rows.set(String(key), { key: String(key), value: String(value), expires_at: expires ?? null });
          writes.push(String(key));
          return { success: true };
        },
        async all() {
          if (/SELECT value FROM kv_store/i.test(sql)) {
            const row = rows.get(String(stmt._args[0]));
            return { results: row ? [row] : [] };
          }
          return { results: [] };
        },
        async first() { return null; },
      };
      return stmt;
    },
  };
}

function testEnv(d1) {
  return { MISAKANET_D1: d1, REGISTER_TOKEN: testToken('leaderboard') };
}

test('GET /api/leaderboard/state serves the stored board', async () => {
  const d1 = createKvStoreD1();
  d1.rows.set('contributor_leaderboard', {
    key: 'contributor_leaderboard',
    value: JSON.stringify({ board: [{ login: 'zsxh1990', score: 3.05 }], bench: null, updated_at: '2026-10-15T00:00:00.000Z' }),
    expires_at: null,
  });
  const res = await worker.fetch(
    new Request('https://misakanet.org/api/leaderboard/state'), testEnv(d1), { waitUntil() {} },
  );
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.available, true);
  assert.deepEqual(body.board, [{ login: 'zsxh1990', score: 3.05 }]);
  assert.equal(body.updated_at, '2026-10-15T00:00:00.000Z');
});

test('GET /api/leaderboard/state answers honestly before the first run', async () => {
  const d1 = createKvStoreD1();
  const res = await worker.fetch(
    new Request('https://misakanet.org/api/leaderboard/state'), testEnv(d1), { waitUntil() {} },
  );
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.available, false);
  assert.equal(body.board, null);
});

test('there is no HTTP write path to the leaderboard state', async () => {
  // PR #2496 proposed `POST /api/leaderboard/state` here with no credential check, on the worker
  // that serves the public site. It was rejected in review. The state is written by the worker's
  // own cron through `storePut`, so this asserts the absence of a write surface rather than
  // the presence of a check: POST must not reach the store at all.
  for (const method of ['POST', 'PUT', 'PATCH', 'DELETE']) {
    const d1 = createKvStoreD1();
    const res = await worker.fetch(
      new Request('https://misakanet.org/api/leaderboard/state', {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: method === 'GET' ? undefined : JSON.stringify({ key: 'leaderboard', value: '{"hacked":true}' }),
      }),
      testEnv(d1),
      { waitUntil() {} },
    );
    assert.notEqual(res.status, 200, `${method} reached a handler`);
    assert.ok(!d1.writes.includes('contributor_leaderboard'), `${method} wrote the leaderboard state`);
  }
});
