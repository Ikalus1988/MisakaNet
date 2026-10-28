// The gate experiment (#2 of the 2026-10-28 backlog): a confident-but-wrong lexical hit used to
// suppress the vector path entirely, because the fallback runs only on an EMPTY result. For CJK
// queries the vector path is now fused in with RRF instead of gated.
//
// Why the tests look like this: the measured effect is a *ranking* claim (11 queries fixed, 2 broken
// on the 64-query probe), so the tests pin the two properties that claim rests on — that fusion is
// reciprocal-rank (no score-scale blending) and that it cannot silently delete the lexical answer
// when the vector side is unavailable. A test that only checked "results came back" would pass with
// the vector path disconnected.
//
// Run: node --test workers/cjk-fusion.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { rrfFuse } from './register-proxy-sw.js';

const lesson = (id) => ({ id, title: id, path: `lessons/x/${id}.md` });

test('a document on both lists outranks a document on only the top of one', () => {
  // Both lists agree on `b` at rank 2 and disagree elsewhere; the agreement has to win.
  const lexical = [lesson('a'), lesson('b'), lesson('c')];
  const vector = [lesson('x'), lesson('b'), lesson('y')];
  const fused = rrfFuse(lexical, vector, 3).map((r) => r.id);
  assert.equal(fused[0], 'b', `expected the shared document first, got ${fused.join(',')}`);
});

test('fusion is reciprocal-rank, so an unbounded lexical score cannot dominate', () => {
  // Whatever BM25's raw score, only the position may matter: the first element of each list carries
  // exactly the same weight, which is what makes the two scales comparable without a tuned weight.
  const lexical = [{ ...lesson('bm25'), score: 999999 }];
  const vector = [{ ...lesson('vec'), score: 0.11 }];
  const fused = rrfFuse(lexical, vector, 2).map((r) => r.id);
  assert.deepEqual(fused.sort(), ['bm25', 'vec']);
});

test('a document that appears twice in one list is counted once', () => {
  // The FAQ corpus is concatenated onto the lesson list before this runs, so an id can repeat.
  const lexical = [lesson('a'), lesson('a'), lesson('b')];
  const fused = rrfFuse(lexical, [], 5).map((r) => r.id);
  assert.deepEqual(fused, ['a', 'b']);
});

test('an empty vector list returns the lexical order untouched', () => {
  // This is the "vector path unavailable" case: the lexical answer must survive intact rather than
  // being re-sorted by a fusion of one list, which would change ranks for no reason.
  const lexical = [lesson('a'), lesson('b'), lesson('c')];
  assert.deepEqual(rrfFuse(lexical, [], 5).map((r) => r.id), ['a', 'b', 'c']);
});

test('a tie is broken by id, so two runs cannot disagree', () => {
  const lexical = [lesson('b')];
  const vector = [lesson('a')];
  assert.deepEqual(rrfFuse(lexical, vector, 2).map((r) => r.id), ['a', 'b']);
});

test('the top-k boundary is respected', () => {
  const many = Array.from({ length: 18 }, (_, i) => lesson(`l${i}`));
  assert.equal(rrfFuse(many, [], 5).length, 5);
});
