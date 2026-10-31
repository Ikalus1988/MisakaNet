// `behindBy` must mean "the corpus now minus what the index published" (audit-adjacent, 2026-10-31).
//
// The field used to be `lastRefresh.corpusCount - docCount`. That is 0 in exactly the window a reader
// needs it: the sync has run, the cron has not, so the refresh record still describes yesterday's
// corpus. Measured live: 47 lessons merged at 05:50, index still at 705, `/api/search-index` reported
// `behindBy: 0` while D1 held 749 — a false green on the number the heartbeat prints every day.
import test from 'node:test';
import assert from 'node:assert/strict';

import { behindByValue } from './register-proxy-sw.js';

test('the live corpus wins over the corpus the last refresh saw', () => {
  assert.equal(behindByValue(749, 705, 705), 44,
    'the refresh record still says 705; the table has 749, so the index is 44 behind');
});

test('a caught-up index is zero', () => {
  assert.equal(behindByValue(749, 749, 749), 0);
});

test('the refresh record is the fallback when D1 cannot answer', () => {
  assert.equal(behindByValue(null, 705, 705), 0);
  assert.equal(behindByValue(null, 705, 749), 44);
});

test('no corpus number at all is null, not zero', () => {
  assert.equal(behindByValue(null, 705, null), null);
  assert.equal(behindByValue(undefined, 705, undefined), null);
});

test('a missing docCount is null rather than a negative lie', () => {
  assert.equal(behindByValue(749, null, 705), null);
});
