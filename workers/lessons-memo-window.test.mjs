// The isolate corpus memo has two windows, and the second one is the point.
//
// 2026-11-28: `MISAKANET_LESSONS_MEMO_MS` went 30 s → 5 min, because 45% of searches took the cold
// path re-reading a 5.36 MB KV value that changes **once a day** (`lesson_sync_log`: one row per day).
// The old 30 s was justified by "below the durable cache's 300 s TTL" — a number that had since been
// raised to 3,600 s, so the constraint no longer applied.
//
// Raising it exposed a second question the config does not answer: `rememberLessons` is also called on
// the **degraded** paths (the data-branch snapshot, a failed D1 read, a D1 read that came back empty).
// Caching a degradation for five minutes is the opposite of what a degradation path is for — it keeps
// serving the snapshot long after D1 recovered. So a degraded read is remembered for 30 s, whatever
// the configured window says.
//
// These tests pin both windows and the fact that they differ, because "one config value" is exactly the
// kind of thing a later edit collapses back into one.
import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

const WORKER = readFileSync(new URL('./register-proxy-sw.js', import.meta.url), 'utf8');
const TOML = readFileSync(new URL('./wrangler.toml', import.meta.url), 'utf8');

test('the configured corpus memo window is at least a minute', () => {
  const match = /MISAKANET_LESSONS_MEMO_MS\s*=\s*"(\d+)"/.exec(TOML);
  assert.ok(match, 'wrangler.toml must set MISAKANET_LESSONS_MEMO_MS');
  const ms = Number(match[1]);
  assert.ok(ms >= 60_000,
    `the corpus memo window is ${ms} ms. The corpus changes once a day (lesson_sync_log) and the KV `
    + 'copy it sits in front of has a 3,600 s TTL, so a window shorter than a minute only buys repeated '
    + '5.36 MB reads — measured 2026-11-27: 45% of searches were cold at p50 1,798 ms.');
  assert.ok(ms <= 3_600_000,
    `the corpus memo window is ${ms} ms — longer than the KV copy's own TTL, which would let the memo `
    + 'serve data the cache itself would have expired');
});

test('a degraded corpus read is remembered for less than a healthy one', () => {
  assert.match(WORKER, /const DEGRADED_MEMO_MS = 30_000;/,
    'the degraded window must be a named constant, not a bare number at a call site');
  const configured = Number(/MISAKANET_LESSONS_MEMO_MS\s*=\s*"(\d+)"/.exec(TOML)[1]);
  assert.ok(configured > 30_000,
    'this test is only meaningful while the healthy window is longer than the degraded one');

  // The three degraded call sites must each say so. A count is used rather than a regex per site
  // because the sites are distinguishable only by their argument list.
  const degraded = WORKER.match(/rememberLessons\([^;]*?,\s*false\)/g) || [];
  assert.equal(degraded.length, 3,
    `expected three degraded call sites (snapshot-cooldown, D1 error, D1-empty), found ${degraded.length}. `
    + 'A degraded read cached for the full window keeps serving the snapshot after D1 recovered.');
});

test('the read path honours the per-entry window, not only the configured one', () => {
  assert.match(WORKER, /memo\.window \|\| memoWindow/,
    'the hit check must read the window stored on the entry; otherwise the degraded window is written '
    + 'and never consulted, which looks correct in the writer and does nothing');
});

test('a disabled window still disables the memo entirely', () => {
  // `0` has to mean off, including for degraded reads: `Math.min(0, 30000)` is 0, so the guard in
  // `rememberLessons` must test the result rather than the configured value.
  assert.match(WORKER, /const window = healthy \? lessonsMemoTtlMs\(env\) : Math\.min\(lessonsMemoTtlMs\(env\), DEGRADED_MEMO_MS\);/,
    'the degraded window must be the minimum of the configured value and DEGRADED_MEMO_MS, so 0 stays 0');
  assert.match(WORKER, /if \(window > 0 && Array\.isArray\(rows\)/,
    'the memo must not be written when the effective window is 0');
});
