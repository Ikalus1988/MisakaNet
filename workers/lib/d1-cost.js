/**
 * What each D1 statement actually costs — read from `D1Meta.rows_read`, in the one place every
 * query goes through.
 *
 * WHY (2026-11-24)
 * ----------------
 * The same class of bug has been fixed twice: 2026-10-21 (a prefix enumeration at 68,892 rows per
 * call) and 2026-11-24 (a three-column `OR` join at **19,561,754,663 rows in a month**, 10.4M per
 * call — 90% of every row the account read). The second one was invisible for a month: correct
 * answers, ordinary latency, no error. Its only witness was a vendor dashboard.
 *
 * The daily report (`scripts/d1_cost_report.py`) now reads Cloudflare's per-query dataset, which
 * answers "which statement, yesterday". This module answers "which statement, in this isolate, right
 * now" — the same number, without waiting for the analytics pipeline, because D1 returns
 * `rows_read`/`rows_written` in every result's `meta`.
 *
 * It is deliberately a **wrapper around the binding**, not a rule in the callers: the worker has 70
 * `prepare(` sites, and a meter that requires touching all of them is a meter that will be skipped.
 * `meterD1()` is applied once, in `d1Binding()`/`opsD1()`, so a statement cannot bypass it by being
 * written somewhere new.
 *
 * What it cannot see, stated so nobody trusts it further than it goes:
 *   * rows read by a `first()`/`raw()` call — D1 does not return `meta` for those;
 *   * anything outside this isolate (a fresh isolate starts empty; the cron flush is what makes the
 *     numbers outlive one);
 *   * `EXPLAIN`/`SELECT 1` probes, which cost one row each and are noise.
 */

/** Per-isolate totals, keyed by the statement's hash. */
const COST = new Map();

/** A statement this rare is usually a one-off script rather than a hot path; keep the map bounded. */
const MAX_STATEMENTS = 200;

/** Below this, a statement's cost is rounding error and is not worth a counter row. */
export const FLUSH_MIN_ROWS = 5_000;

/** The cron writes at most this many statement rows per run, by rows read, to stay cheap itself. */
export const FLUSH_TOP_N = 25;

/** FNV-1a over the statement with whitespace collapsed — stable across reformatting, cheap to compute. */
export function statementKey(sql) {
  const normalised = String(sql || "").replace(/\s+/g, " ").trim();
  let hash = 0x811c9dc5;
  for (let i = 0; i < normalised.length; i += 1) {
    hash ^= normalised.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function head(sql) {
  return String(sql || "").replace(/\s+/g, " ").trim().slice(0, 120);
}

function record(sql, meta) {
  const key = statementKey(sql);
  let entry = COST.get(key);
  if (!entry) {
    if (COST.size >= MAX_STATEMENTS) return;   // bounded on purpose: this runs on every query
    entry = { key, head: head(sql), calls: 0, rows: 0, written: 0 };
    COST.set(key, entry);
  }
  entry.calls += 1;
  if (meta && typeof meta === "object") {
    entry.rows += Number(meta.rows_read) || 0;
    entry.written += Number(meta.rows_written) || 0;
  }
  return entry;
}

/** Wrap one prepared statement's terminal methods so every result is counted. */
function meterStatement(stmt, sql) {
  if (!stmt || typeof stmt !== "object") return stmt;
  for (const method of ["run", "all", "first", "raw"]) {
    if (typeof stmt[method] !== "function" || stmt[method].__metered) continue;
    const original = stmt[method].bind(stmt);
    const wrapped = async (...args) => {
      const result = await original(...args);
      record(sql, result && result.meta);
      return result;
    };
    wrapped.__metered = true;
    stmt[method] = wrapped;
  }
  if (typeof stmt.bind === "function" && !stmt.bind.__metered) {
    const bind = stmt.bind.bind(stmt);
    const wrappedBind = (...args) => meterStatement(bind(...args), sql);
    wrappedBind.__metered = true;
    stmt.bind = wrappedBind;
  }
  return stmt;
}

const METERED = new WeakMap();

/**
 * The same binding, with its statements metered. Memoised per binding so two accessors that return
 * the same object do not wrap it twice; a binding that cannot be wrapped is returned untouched, and
 * every failure here is swallowed — a meter must never be able to break a query.
 */
export function meterD1(db) {
  if (!db || typeof db !== "object" || typeof db.prepare !== "function") return db;
  if (METERED.has(db)) return METERED.get(db);
  try {
    const prepare = db.prepare.bind(db);
    const wrapper = Object.create(db);
    wrapper.prepare = (sql) => meterStatement(prepare(sql), sql);
    METERED.set(db, wrapper);
    return wrapper;
  } catch (error) {
    return db;
  }
}

/** What this isolate has seen so far, biggest first. */
export function costSnapshot(limit = 20) {
  return [...COST.values()]
    .map((entry) => ({ ...entry, rows_per_call: entry.calls ? entry.rows / entry.calls : 0 }))
    .sort((a, b) => b.rows - a.rows)
    .slice(0, limit);
}

/** Only for tests and for the flush's own bookkeeping. */
export function resetCost() {
  COST.clear();
}

/**
 * Persist this isolate's numbers into `counters` and start over.
 *
 * Two rows per statement (`:calls`, `:rows`) rather than one blob: `bumpCounter` is an atomic
 * increment, so several isolates flushing the same statement add up instead of overwriting each
 * other — which is the whole reason to persist rather than keep a per-isolate map.
 *
 * `bump` is injected (the worker passes `bumpCounter`) so this module stays dependency-free and
 * testable.
 */
export async function flushQueryCost(bump, today, { minRows = FLUSH_MIN_ROWS, topN = FLUSH_TOP_N } = {}) {
  const rows = costSnapshot(topN).filter((entry) => entry.rows >= minRows);
  if (!rows.length) return { flushed: 0, statements: 0 };
  let flushed = 0;
  for (const entry of rows) {
    try {
      await bump("query_cost", `${entry.key}:calls`, today, entry.calls);
      await bump("query_cost", `${entry.key}:rows`, today, entry.rows);
      flushed += 2;
    } catch (error) {
      // Best effort: a counter write that fails must not fail the cron, and the next flush retries.
      break;
    }
  }
  resetCost();
  return { flushed, statements: rows.length };
}
