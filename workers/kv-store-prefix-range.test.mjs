// The prefix list must not read the whole `kv_store` table (2026-10-20).
//
// D1 Free allows 5,000,000 rows read/day. Measured on production that day with
// `wrangler d1 insights misakanet-db --time-period 6h --sort-by reads`:
//
//   17,800,700 rows  SELECT key FROM kv_store WHERE key LIKE ?1 ESCAPE '\' …   (259 calls)
//                     ── 87% of the account's row-read spend, for a listing whose answer is six keys.
//
// `kv_store` has a TEXT PRIMARY KEY on `key`, and D1's SQLite still has no usable plan for
// `key LIKE 'prefix%'` — that query read 68,892 rows, and the same rows reached with a range
// read 6. So the assertion here is on the query's *shape*, not on the answer: the LIKE form
// lists exactly the right keys and still bills the whole table.
//
// Run: node --test workers/kv-store-prefix-range.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { storeList, storePut } from './register-proxy-sw.js';
import { withKvStore } from './_test-kv-store.mjs';

test('the prefix list asks for a range, not for a LIKE that reads every row of the table', async () => {
  // The failure this pins is invisible in the answer: the LIKE form lists exactly the right keys
  // and reads all 68,892 rows of `kv_store` to do it. So the assertion is on the query's *shape*.
  const d1 = withKvStore();
  const env = { MISAKANET_D1: d1 };
  await storePut(env, 'unsolved:lesson:a', '{}');
  await storeList(env, 'unsolved:lesson:');

  const lists = d1.kvStoreSql.filter((sql) => /SELECT key FROM kv_store/i.test(sql));
  assert.equal(lists.length, 1, `the prefix list ran ${lists.length} times: ${JSON.stringify(lists)}`);
  assert.ok(/key\s*>=\s*\?1\s+AND\s+key\s*<\s*\?2/i.test(lists[0]),
    `the prefix list must use the primary-key range — this one reads the whole table: ${lists[0]}`);
  assert.ok(!/LIKE/i.test(lists[0]),
    `a LIKE prefix has no usable plan on D1 and reads every row: ${lists[0]}`);
});

test('the range covers exactly the prefix — neighbours on either side are not listed', async () => {
  const env = { MISAKANET_D1: withKvStore() };
  await storePut(env, 'unsolved:lesson:a', '{}');
  await storePut(env, 'unsolved:lesson:b', '{}');
  await storePut(env, 'unsolved:family:ci', '{}');     // a different prefix
  await storePut(env, 'unsolved:lessonz:c', '{}');      // shares the prefix's text, is not the prefix
  await storePut(env, 'rate:intake:203.0.113.5', '1', { expirationTtl: 60 });

  const listed = await storeList(env, 'unsolved:lesson:');
  assert.deepEqual(listed.keys.map((k) => k.name).sort(),
    ['unsolved:lesson:a', 'unsolved:lesson:b'],
    'the range must include the prefix and stop before its neighbour');
});

test('an expired key under the prefix is still hidden', async () => {
  // The expiry filter is a separate predicate from the range; a range that replaced it would
  // resurrect keys the durable store is supposed to have dropped.
  const env = { MISAKANET_D1: withKvStore() };
  await storePut(env, 'unsolved:lesson:live', '{}', { expirationTtl: 3600 });
  await storePut(env, 'unsolved:lesson:dead', '{}', { expirationTtl: -60 });

  const listed = await storeList(env, 'unsolved:lesson:');
  assert.deepEqual(listed.keys.map((k) => k.name), ['unsolved:lesson:live']);
});

test('an underscore in a prefix is a literal, not a wildcard', async () => {
  // `_` is a LIKE wildcard, and lesson ids contain it. The LIKE form needed `escapeLike` to keep
  // `unsolved:lesson:foo_bar` from also matching `unsolved:lesson:fooXbar`; the range form has no
  // wildcards, so the same answer has to come out — a list that quietly disagrees with the exact
  // reads is the bug this exists to prevent.
  const env = { MISAKANET_D1: withKvStore() };
  await storePut(env, 'unsolved:lesson:foo_bar', '{}');
  await storePut(env, 'unsolved:lesson:fooXbar', '{}');

  const listed = await storeList(env, 'unsolved:lesson:foo_bar');
  assert.deepEqual(listed.keys.map((k) => k.name), ['unsolved:lesson:foo_bar']);
});
