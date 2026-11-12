// The sidebar's contribution ladder: the arithmetic, the three windows, and the two rules that
// keep it from being a scoreboard for our own machinery.
//
// ── Why this is a separate module ──────────────────────────────────────────────
//
// There is already a contributor board (`workers/lib/contributor-leaderboard.js`), and it is not
// this one. That board ranks **commit authors** by recency × PR size — it answers "who has been
// writing code". This one ranks **contributors to the corpus** by four things a reader can see in
// the panel: lessons hit, lessons contributed, questions asked, questions answered. They share a
// storage shape (state in D1, computed by the cron) and nothing else, so the arithmetic lives here
// and stays a pure function over plain rows — testable without a database.
//
// ── The definition that had to be written down ─────────────────────────────────
//
// "Hit" is two different observations and the product asked for both:
//
//   * **used** — someone else retrieved a lesson you contributed (the reuse signal, and the only
//     one that cannot be manufactured by the contributor);
//   * **self** — your own search came back with a lesson (a consumption signal).
//
// Both count toward the score, because the owner asked for both. They are kept in separate fields
// and the UI shows them apart, and `self` is capped per day: it is the one term a contributor can
// inflate by writing a loop, and an uncapped loop is how a ladder stops meaning anything. The cap
// is a rate, so it scales with the window (`selfCap(days)`).
//
// ── What is deliberately not here ─────────────────────────────────────────────
//
// No I/O, no clock (`days` is passed in), no formatting. The cron, the endpoint and the panel each
// get a plain object back, so the three cannot disagree about a score.

/** Weights, in one place. A change here is a change to every published number. */
export const WEIGHTS = Object.freeze({ hit: 0.2, lesson: 1.0, question: 0.5, solved: 1.0 });

/** Self-hits counted per day. Above this, a loop buys nothing. */
export const SELF_HIT_CAP_PER_DAY = 20;

/** The windows the panel offers, in days. `all` is a sentinel, not a number. */
export const WINDOWS = Object.freeze({ week: 7, month: 30, all: null });

/** Rows in the published panel: the top N plus the reader's own row. */
export const TOP_N = 10;

function count(value) {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? n : 0;
}

function round2(value) {
  return Math.round(value * 100) / 100;
}

/** The self-hit allowance for a window. `null` (all-time) has no allowance worth counting. */
export function selfCap(days) {
  if (days === null || days === undefined) return Infinity;
  return SELF_HIT_CAP_PER_DAY * Math.max(1, Number(days) || 0);
}

/**
 * The score of one contributor row, and the parts a UI needs to explain it.
 *
 * `days` is the window length (`null` for all-time). The cap is applied to the *counted* self term
 * only; the displayed total still says how many self hits happened, and `selfCapped` says how many
 * of them were thrown away — a board that silently drops part of a number is the failure mode this
 * repository keeps finding.
 */
export function scoreEntry(entry, { days = WINDOWS.week } = {}) {
  const used = count(entry && entry.used);
  const self = count(entry && entry.self);
  const lessons = count(entry && entry.lessons);
  const questions = count(entry && entry.questions);
  const solved = count(entry && entry.solved);

  const allowedSelf = Math.min(self, selfCap(days));
  const score = round2(
    (used + allowedSelf) * WEIGHTS.hit
    + lessons * WEIGHTS.lesson
    + questions * WEIGHTS.question
    + solved * WEIGHTS.solved,
  );

  return {
    score,
    hits: used + self,
    hitsCounted: used + allowedSelf,
    selfCapped: self - allowedSelf,
    used,
    self,
    lessons,
    questions,
    solved,
  };
}

/** How many identity marks a row carries: `node`, `github`, or both. */
export function identityOf(entry) {
  const hasNode = Boolean(entry && entry.node);
  const hasLogin = Boolean(entry && entry.login);
  if (hasNode && hasLogin) return "both";
  if (hasLogin) return "github";
  return "node";
}

/**
 * Rank rows for one window and pick out the reader's own row.
 *
 * `rows` carry the raw counters (`used`, `self`, `lessons`, `questions`, `solved`) and a window
 * timestamp (`lastActive`, ISO). Rows with no activity in the window are dropped rather than shown
 * as zeroes; rows owned by this repository's machinery are dropped by the caller (they know their
 * identity list) — this function only ranks what it is given.
 *
 * `self` matches on `node` first, then `login`, because a bound contributor can appear under
 * either. The returned `me` is `null` when the reader has no row in the window — "not on the board
 * yet" and "rank 0" are different sentences and the panel says the first.
 */
export function rankRows(rows, { days = WINDOWS.week, top = TOP_N, node = null, login = null, since = null } = {}) {
  const list = Array.isArray(rows) ? rows : [];
  const cutoff = since === null ? null : Date.parse(since);

  const scored = [];
  for (const row of list) {
    if (!row) continue;
    if (cutoff !== null && Number.isFinite(cutoff)) {
      const at = Date.parse(row.lastActive || "");
      if (!Number.isFinite(at) || at < cutoff) continue;
    }
    const parts = scoreEntry(row, { days });
    if (parts.score <= 0) continue;
    scored.push({
      ...row,
      ...parts,
      identity: identityOf(row),
      name: String(row.name || row.login || row.node || "unknown"),
    });
  }

  scored.sort((a, b) => (b.score - a.score) || a.name.localeCompare(b.name));

  const ranked = scored.map((row, index) => ({ ...row, rank: index + 1 }));
  const topRows = ranked.slice(0, Math.max(1, top));

  let me = null;
  if (node || login) {
    me = ranked.find((row) => (node && row.node === node) || (login && row.login === login)) || null;
  }

  return {
    top: topRows,
    me,
    total: ranked.length,
    window: { days, since },
  };
}

/**
 * The all-time / month / week cut as a `since` timestamp, from an explicit `now`.
 *
 * Kept next to the ranking on purpose: the endpoint, the cron and the tests must agree on what
 * "this week" means, and the only way to guarantee that is to compute it in one place.
 */
export function windowSince(name, now) {
  const days = WINDOWS[name];
  if (days === null || days === undefined) {
    return { days: null, since: null };
  }
  const end = now instanceof Date ? now : new Date(now);
  const since = new Date(end.getTime() - days * 86_400_000).toISOString();
  return { days, since };
}
