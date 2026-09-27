// The tokenizer half of CJK-1 (#2355): character bigrams for CJK, and nothing else.
//
// Why the helper exists, stated as a test: `bm25Tokenize` lowercases and splits on `[^a-z0-9]+`, so CJK
// text tokenises to the **empty set**. That is the root cause of #2250 — a mixed query's Chinese half
// contributes no term statistics, so the Latin half decides the answer (measured: `wsl2 landlock 文件系统沙箱`
// returned an unrelated lesson). It is a tokenisation problem, not a weight problem, which is why four
// weight-tuning designs all regressed English instead.
//
// What this file pins: run boundaries, single-character runs, code-point handling, and — the important one —
// that adding this changes **nothing** about the existing index text or the English floors.
//
// Run: node --test workers/cjk-bigram-tokenizer.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { cjkBigrams, bm25Tokenize, buildBM25Index } from './register-proxy-sw.js';

test('bm25Tokenize sees nothing in CJK text — the premise of the whole issue', () => {
  assert.deepEqual(bm25Tokenize('文件系统沙箱'), [], 'if this ever stops being empty, re-read #2250');
  assert.deepEqual(bm25Tokenize('wsl2 landlock 文件系统沙箱'), ['wsl2', 'landlock'].filter(t => t.length >= 2));
});

test('bigrams are emitted per CJK run, never across a boundary', () => {
  assert.deepEqual(cjkBigrams('文件系统沙箱'), ['文件', '件系', '系统', '统沙', '沙箱']);
  // The space must break the run: `统沙` is a bigram, `x文` is not a term anybody types.
  assert.deepEqual(cjkBigrams('wsl2 landlock 文件系统沙箱'), ['文件', '件系', '系统', '统沙', '沙箱']);
  assert.deepEqual(cjkBigrams('中 文'), ['中', '文'], 'two one-character runs, not one bigram');
});

test('a single-character run emits the character itself', () => {
  // Bigrams alone would make a one-character query unmatchable, and one-character Chinese queries are
  // common enough to matter.
  assert.deepEqual(cjkBigrams('字'), ['字']);
  assert.deepEqual(cjkBigrams('好好学'), ['好好', '好学']);
});

test('Japanese kana and Korean hangul are covered, surrogate pairs count as one character', () => {
  assert.deepEqual(cjkBigrams('ひらがな'), ['ひら', 'らが', 'がな']);
  assert.deepEqual(cjkBigrams('한국어'), ['한국', '국어']);
  // U+20000 is outside the BMP: `run[i] + run[i+1]` on UTF-16 code units would split it in half.
  const astral = '\u{20000}\u{20001}';
  assert.deepEqual(cjkBigrams(astral), [astral], 'a surrogate pair is one character, not two');
});

test('non-CJK text yields nothing, and the input is never mutated', () => {
  assert.deepEqual(cjkBigrams('no cjk here'), []);
  assert.deepEqual(cjkBigrams(''), []);
  assert.deepEqual(cjkBigrams(null), []);
  assert.deepEqual(cjkBigrams('café — naïve'), []);
});

test('adding the tokenizer leaves the existing index text and English floors untouched', () => {
  // The guard: CJK-1 must not change what English search sees. `buildBM25Index` is called with the same
  // fixture on both sides and compared byte-for-byte, so a future edit that quietly mixes bigrams into
  // `index.terms` (or into the doc lengths that normalise every score) fails here rather than in production.
  const lessons = [
    { id: 'en', title: 'pip install timeout', domain: 'python', tags: ['pip'],
      path: 'lessons/core/en.md', summary: 'pip times out behind a proxy.', preview: 'Use a mirror.' },
    { id: 'zh', title: '文件系统沙箱失败', domain: 'ops', tags: [],
      path: 'lessons/contrib/zh.md', summary: '文件系统沙箱在受限环境里失败。',
      preview: '沙箱挂载与文件系统权限有关。' },
  ];
  const index = buildBM25Index(lessons, { textMode: 'rich' });
  const englishTerms = Object.keys(index.terms).filter(t => /^[a-z0-9-]+$/.test(t));
  for (const token of ['pip', 'install', 'timeout', 'proxy', 'mirror']) {
    assert.ok(englishTerms.includes(token), `English token disappeared from the index: ${token}`);
  }
  assert.equal(index.docCount, 2);
  // No CJK bigram may have leaked into the shared namespace.
  for (const bigram of cjkBigrams('文件系统沙箱')) {
    assert.ok(!(bigram in index.terms), `bigram ${bigram} leaked into index.terms — English IDF would move`);
  }
});
