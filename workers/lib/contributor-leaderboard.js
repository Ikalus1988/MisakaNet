// The contributor ranking, and the rule that keeps this project's own machinery off it.
//
// ── Why this lives here at all (issue #1919, PR #2496) ───────────────────────────
//
// `leaderboard-watch.yml` used to run on **every push to main**, recompute the ranking, compare
// it with a snapshot committed back to main, open an issue when the #1 entry changed, and commit
// the snapshot. Measured 2026-09-20: **1,026 commits — 25% of the repository's 4,033 — carried the
// message `chore: update leaderboard snapshot [skip ci]`**, and the workflow ran 1,549 times.
// The churn was not cosmetic: on 2026-09-20 it moved `main` under the npm publish job's record
// step, which was rejected as a non-fast-forward, so a release shipped and never recorded itself
// (issue #1916 / #1917).
//
// The root cause is a category error. "Did the value change?" is a **state machine** — it needs
// `last_seen_value` + compare + side effect. A git commit is a meaningful, revertible change
// sequence. Using commits to hold a timestamp costs history, races concurrent writers, and turns
// `main` into a fast-moving target that every downstream job pays for.
//
// So the state moved to D1. The worker computes it on its own cron instead, which is the only
// unattended writer available:
//
//   * CI cannot write D1 unattended. The only Cloudflare token is `CF_API_TOKEN`, it lives in the
//     `release` environment, and that environment has a **required reviewer** — every workflow that
//     uses it (`d1-bootstrap`, `apply-d1-schema`, `d1-counters-report`) is `workflow_dispatch`-only
//     for exactly that reason. A daily scheduled run would wait on a human click every morning.
//   * The repo has no `SYNC_TOKEN`, so the `X-Sync-Token` pattern the sibling write endpoint uses
//     (see `POST /api/search-index`) has nothing to compare against and fails closed at 401.
//   * `AI_GATEWAY_TOKEN` is **not** a MisakaNet credential. It authenticates against
//     `gateway.ai.cloudflare.com` in `scripts/benchmark_workers_ai.py`; nothing validates it here.
//     An earlier review note on #2496 assumed otherwise and was wrong.
//
// The worker already runs a cron, holds the D1 binding, and reads and writes through
// `storeGet`/`storePut` (D1 `kv_store`, KV as fallback). That is the whole migration: no new
// table, no new endpoint, no new secret.
//
// ── What was deliberately *not* ported ───────────────────────────────────────────
//
// The Python scorer added a `lessons_contributed` bonus by scanning every lesson file's
// frontmatter for a `source` field. Measured 2026-10-15 over the 519 tracked lessons: **3 carry a
// `source` at all**, and none of the three values is a GitHub login — one is a Chinese sentence, one
// is `incident-2026-09-09`, one is `intake-issue-1196`. The bonus is therefore keyed against
// logins that cannot exist, so it contributed exactly 0 to every score it has ever computed.
// Carrying it forward would mean fetching and parsing 519 documents a day to add a constant zero.
// It is dropped, with this measurement as the reason; if a lesson ever does get a `source` naming
// a login, this is the place to add it back.
//
// ── Scoring, unchanged from `scripts/leaderboard_watch.py` ───────────────────────
//
//     score = (Σ 0.5^(days_ago/30), floored at 10%) * median_pr_size_factor / 2  +  recency
//
// with a +0.5 recency bonus inside 7 days, +0.2 inside 30. The one arithmetic difference from the
// Python is the final rounding: Python's `round()` is banker's rounding, this is half-up. It can
// only move a stored score by 0.01, against a comparison threshold of 0.5.

/**
 * This repository's own automation identities — the git identities its workflows and scripts
 * commit with. GitHub has no account for most of them, so there is no `type` field to consult and
 * no profile page to inspect.
 *
 * `[bot]` is matched by shape instead of by name (see `isAutomationLogin`), so a new App needs no
 * entry here. Measured 2026-09-25: this list named dependabot / pre-commit-ci / cloudflare and
 * missed `github-actions[bot]`, which sat at **rank #2** on the published board, and
 * `misakanet-sync-bot` at rank #5 — no GitHub account at all, yet on a public contributor board.
 */
export const SELF_IDENTITIES = new Set([
  "misakanet-bot",         // scripts/adopt_pr.py DEFAULT_SIGNOFF_NAME; workflows' `git config user.name`
  "misakanet-sync-bot",    // .github/workflows/auto-sync-prs.yml
  "misakanet-agent",       // older tooling identity (no GitHub account)
  "misakanet agent",       //   the same, with a space
  "github-actions",        // the *name* GitHub's own runner commits with, distinct from [bot]
  "actions-user",          // GitHub's legacy actions identity
  "ikalus1988",            // the maintainer: excluded so the board is about contributors
  "sheldonisspark-lab",    // the maintainer's second account
  "claude",                // a coding agent used here
]);

/**
 * True for GitHub Apps and for this repository's own automation identities.
 *
 * Not a judgement about whether a *person* is behind an account — GitHub cannot tell us that, and
 * this project's own `agent_type` is self-declared and unverified. It answers the narrower,
 * checkable question: is this identity the project's own machinery?
 *
 * The rule has to be about *shape* rather than a list of names, because contributors come from
 * commit authors: `author.user.login` falls back to the raw git author name whenever no GitHub
 * account matches, so anything a `git config user.name` produced can reach a public board.
 */
export function isAutomationLogin(login) {
  const name = String(login || "").trim().toLowerCase();
  return name.endsWith("[bot]") || SELF_IDENTITIES.has(name);
}

/** Log-scaled PR size factor. 1-line fix → ~1.0, 100-line → ~3.0, 1000-line → ~4.0. */
export function prSizeFactor(additions, deletions) {
  const total = Math.max(1, (Number(additions) || 0) + (Number(deletions) || 0));
  return Math.log10(total) + 1;
}

/** Separate recency bonus: recent activity gets an extra boost. */
export function recencyBonus(daysAgo) {
  if (daysAgo <= 7) return 0.5;
  if (daysAgo <= 30) return 0.2;
  return 0;
}

/**
 * Whether the *visible* board changed: the ranking order, or any score by more than `threshold`.
 *
 * Deliberately not "did the top entry change". A board can be wrong in every other row — a bot in
 * second place, a contributor dropped — while #1 is untouched, and with the older predicate that
 * correction was computed and then thrown away (measured 2026-09-25).
 *
 * This predicate answers "is the stored state still current?", which is now the only question the
 * state is for. The issue-notification criterion stayed narrower on purpose: it asks whether *#1*
 * changed hands, because that is the event worth a maintainer's attention.
 */
export function boardMoved(previous, current, threshold = 0.5) {
  if (!Array.isArray(previous) || !Array.isArray(current)) return true;
  // NUL-joined, not "": ["ab","c"] and ["a","bc"] concatenate to the same string.
  const order = previous.map((r) => String(r && r.login)).join("\u0000");
  if (order !== current.map((r) => String(r && r.login)).join("\u0000")) return true;
  for (let i = 0; i < previous.length; i++) {
    const before = Number(previous[i] && previous[i].score) || 0;
    const after = Number(current[i] && current[i].score) || 0;
    if (Math.abs(before - after) > threshold) return true;
  }
  return false;
}

/**
 * Whether a notification issue is due — the #1 entry changing hands.
 *
 * This reproduces `contrib_changed` from the Python scorer exactly, **including its `and`**:
 *
 *     previous is None or (login changed and abs(score delta) > 0.5)
 *
 * The conjunction looks wrong, and on its own terms it is — comparing the scores of two *different*
 * people is not meaningful, so a real change of #1 between two near-equal scores stays silent. It is
 * kept because this change moves where the state lives, and a storage migration that also quietly
 * widens the notification criterion would make any later regression untraceable to this diff. It has
 * fired twice in the repository's history, so nothing observable is lost today. Fixing the predicate
 * is its own change, with its own measurement.
 *
 * First run (no stored state) counts as due, so the board gets recorded and the next run has
 * something to compare against.
 */
export function shouldNotifyTopChange(previous, current, threshold = 0.5) {
  if (!Array.isArray(previous) || previous.length === 0) return true;
  if (!Array.isArray(current) || current.length === 0) return false;
  const before = previous[0] || {};
  const after = current[0] || {};
  if (String(before.login) === String(after.login)) return false;
  return Math.abs((Number(before.score) || 0) - (Number(after.score) || 0)) > threshold;
}

const MS_PER_DAY = 86_400_000;

/** Whole days between an ISO timestamp and `now`, floored. An unparseable date is a year old. */
export function daysAgo(isoTimestamp, now) {
  const then = Date.parse(String(isoTimestamp || ""));
  if (!Number.isFinite(then)) return 365;
  return Math.floor((now - then) / MS_PER_DAY);
}

/**
 * Score the board from already-fetched inputs. Pure: no clock, no network, no store.
 *
 * @param commitNodes  GraphQL `history.nodes` from the default branch, in history order.
 * @param mergedPrs    REST closed PRs that carry `merged_at`.
 * @param now          epoch ms, injected so the result is reproducible in a test.
 * @returns `[{login, score}]`, descending.
 */
export function scoreBoard(commitNodes, mergedPrs, now) {
  const commitDays = new Map();
  for (const node of commitNodes || []) {
    if (!node) continue;
    const author = node.author || {};
    const login = String((author.user && author.user.login) || author.name || "unknown").toLowerCase();
    if (!node.committedDate) continue;
    if (!commitDays.has(login)) commitDays.set(login, []);
    commitDays.get(login).push(daysAgo(node.committedDate, now));
  }

  const prSizes = new Map();
  for (const pr of mergedPrs || []) {
    if (!pr || !pr.merged_at) continue;
    const login = String((pr.user && pr.user.login) || "unknown").toLowerCase();
    if (!prSizes.has(login)) prSizes.set(login, []);
    prSizes.get(login).push(prSizeFactor(pr.additions, pr.deletions));
  }

  const scored = [];
  for (const [login, ages] of commitDays) {
    let commitScore = 0;
    for (const d of ages) commitScore += Math.max(0.1, Math.pow(0.5, d / 30));

    const sizes = prSizes.get(login);
    let sizeMultiplier = 0.5; // no PR data → small default
    if (sizes && sizes.length) {
      sizes.sort((a, b) => a - b);
      const median = sizes[Math.floor(sizes.length / 2)];
      sizeMultiplier = median / 2.0;
    }

    const total = commitScore * sizeMultiplier + recencyBonus(Math.min(...ages));
    scored.push({ login, score: total });
  }

  // Excluded by rule, not by a list somebody has to remember to update.
  const kept = scored.filter((row) => !isAutomationLogin(row.login));
  // Stable sort: equal scores keep first-appearance order, as the Python dict ordering did.
  kept.sort((a, b) => b.score - a.score);
  return kept.map((row) => ({ login: row.login, score: Math.round(row.score * 100) / 100 }));
}
