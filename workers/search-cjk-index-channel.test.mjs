// The CJK side of the index — written, stored, and deliberately not read yet (issue #2355).
//
// WHY THIS FILE EXISTS. `bm25Tokenize` drops CJK entirely (`[^a-z0-9]+` → space), so a Chinese question
// reached the scorer with **zero** terms and returned `[]`, and a Chinese *lesson* contributed no term
// statistics to the index at all. Measured on production MCP (2026-09-27):
//
//   `macOS Chrome headless PDF 写完了但进程不退`  → the right lesson (the Latin half carried it)
//   `wsl2 landlock 文件系统沙箱`                  → an **unrelated** lesson (`chrome-relay-…`), because
//                                                   the two Latin tokens decided the answer
//
// The tokenizer half landed in #2361 (`cjkBigrams()`); this is the index channel that consumes it. Rank
// fusion is #2356 and the confidently-wrong case stays pinned in #2358 — **nothing here changes what a
// query returns**, which is the point: the write side can be reviewed and merged on its own.
//
// The three risks the design named, and the check for each:
//
//   1. **English dilution.** `avgDocLen` normalises every document's BM25 score (`b = 0.75`), so a
//      bigram stream mixed into the shared text would move every English score even though no English
//      token changed. The channel is a separate map with its own lengths, and the test below proves the
//      English half is byte-identical to a build without the channel.
//   2. **Index growth.** The row is gzip+base64 in one store row and D1 caps a row at 2 MB — the ceiling
//      that froze search on 2026-09-26. The last test measures the real corpus and fails if the stored
//      size approaches that ceiling (the design's answer then is a row of its own, not a thinner
//      channel).
//   3. **A stale build served as if it had the channel.** `INDEX_TEXT_VERSION` 3 → 4, and the index
//      records it, so `refreshSearchIndex`'s `textChanged` rebuilds instead of serving an English-only
//      index to a CJK query.
//
// Run: node --test workers/search-cjk-index-channel.test.mjs
import assert from 'node:assert/strict';
import { cpSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { bm25Tokenize, buildBM25Index, cjkBigrams, encodeIndexForStorage, matchTokens } from './register-proxy-sw.js';

const WORKER = new URL('./register-proxy-sw.js', import.meta.url);
const SOURCE = readFileSync(WORKER, 'utf8');
const ANCHOR = /function cjkBigrams\(text\) \{/;
assert.ok(ANCHOR.test(SOURCE), 'cjkBigrams() is gone or renamed — the channel is built on it');

// A fixture with one CJK-only lesson, one mixed lesson and one English-only lesson, so "did a bigram
// leak into the English map" and "does the CJK map know which document a query belongs to" are both
// answerable without the real corpus.
const CORPUS = [
  {
    id: "cjk-only-lesson",
    title: "磁盘空间不足怎么清理",
    domain: "ops",
    tags: ["磁盘"],
    description: "写入文件时报 No space left on device，需要清理缓存与临时文件。",
    indexText: "磁盘空间不足怎么清理 写入文件或构建向量库时报 No space left on device ENOSPC。清理缓存目录与临时文件后恢复。",
  },
  {
    id: "mixed-lesson",
    title: "pip install 超时：公司代理导致的 SSL 失败",
    domain: "python",
    tags: ["pip", "proxy"],
    description: "pip install 在公司代理后超时，需要设置 HTTPS_PROXY 并使用内部镜像。",
    indexText: "pip install timeout behind corporate proxy, fix by setting HTTPS_PROXY and an internal mirror. 公司代理导致 pip 安装超时。",
  },
  {
    id: "english-lesson",
    title: "Playwright snap chromium missing libnss3",
    domain: "testing",
    tags: ["playwright"],
    description: "Chromium fails to launch in a sandbox because libnss3 is missing.",
    indexText: "Playwright snap chromium missing libnss3 libnspr4 in a sandbox: install the packages.",
  },
];

const INDEX = buildBM25Index(CORPUS);

function scratchWorkerThatIgnoresCjk() {
  const dir = mkdtempSync(path.join(tmpdir(), 'cjk-channel-'));
  cpSync(new URL('./lib', import.meta.url), path.join(dir, 'lib'), { recursive: true });
  const file = path.join(dir, 'worker-without-cjk.js');
  // A build *as it was before this change*: the real tokenizer is still there (renamed, so nothing
  // calls it) and `cjkBigrams` returns nothing, which is exactly what an empty channel looks like.
  // Renaming rather than replacing the body keeps the patched file valid JavaScript — the first
  // version of this produced `SyntaxError: Unexpected token 'import'` from a half-replaced function.
  const patched = SOURCE
    .replace(ANCHOR, 'function cjkBigramsOriginal(text) {')
    .replace('const CJK_CHAR = new RegExp', 'function cjkBigrams() { return []; }\nconst CJK_CHAR = new RegExp');
  writeFileSync(file, patched);
  return file;
}

test('the channel is a versioned, separate map', () => {
  assert.equal(INDEX.textVersion, 4, 'INDEX_TEXT_VERSION must move with the indexed text (#2355)');
  assert.ok(INDEX.cjk, 'the index has no cjk channel at all');
  assert.equal(INDEX.cjk.version, 1);
  assert.equal(INDEX.cjk.docCount, CORPUS.length);
  assert.equal(INDEX.cjk.docLen.length, CORPUS.length, 'one length per document, in document order');
  assert.equal(INDEX.cjk.docLen[2], 0, 'an English-only lesson has no bigrams');
});

test('a CJK-only query reaches the channel', () => {
  // The write-side acceptance: the query has no Latin token at all, so this is the case that used to
  // reach the scorer with zero terms.
  const query = "磁盘空间不足";
  const grams = cjkBigrams(query);
  assert.ok(grams.length > 0, 'the tokenizer produced no bigrams for a CJK-only query');
  const missing = grams.filter((gram) => !INDEX.cjk.terms[gram]);
  assert.deepEqual(missing, [], `these query bigrams are not in the channel: ${missing}`);

  // …and the postings point at the lesson, which is what #2356 will rank on.
  const hit = INDEX.cjk.terms[grams[0]];
  assert.ok(hit.docs.some((entry) => entry.doc === 0),
    `a bigram of the query does not point at the lesson that contains it: ${JSON.stringify(hit)}`);
  assert.equal(hit.df, 1, 'only the one lesson carries this bigram');
});

test('the English index is byte-identical with and without the channel', () => {
  // The acceptance criterion that makes this a channel and not a change: the calibration table must print
  // the same numbers, and the cheapest honest form of that is "the same bytes".
  const english = (index) => JSON.stringify({
    avgDocLen: index.avgDocLen,
    docCount: index.docCount,
    terms: index.terms,
    docs: index.docs,
  });
  return import(scratchWorkerThatIgnoresCjk()).then((mod) => {
    const without = mod.buildBM25Index(CORPUS);
    assert.equal(english(without), english(INDEX),
      'the CJK channel moved the English posting list or avgDocLen — that is the dilution the design '
      + 'forbids (avgDocLen normalises every BM25 score, b = 0.75)');
    assert.equal(without.cjk.docCount, CORPUS.length);
    assert.deepEqual(Object.keys(without.cjk.terms), [], 'the control build is not actually CJK-free');
  });
});

test('no bigram leaked into the English term map', () => {
  const cjkInTerms = Object.keys(INDEX.terms).filter((term) => /[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af]/u.test(term));
  assert.deepEqual(cjkInTerms, [], `CJK terms reached index.terms: ${cjkInTerms.slice(0, 5)}`);
  // And the two maps are disjoint by construction: a bigram key must not exist on the English side.
  const overlap = Object.keys(INDEX.cjk.terms).filter((gram) => gram in INDEX.terms);
  assert.deepEqual(overlap, [], `these keys exist in both maps: ${overlap.slice(0, 5)}`);
  // The premise of the channel, stated as a test: the *indexer's* tokenizer erases CJK, so no Chinese
  // term can ever reach `index.terms`. (`matchTokens`, the matcher's tokenizer, does keep whole CJK runs
  // — that asymmetry is why `indexShapeProblem` has to exclude them from its body-only sample; nothing
  // here depends on it.)
  assert.deepEqual(bm25Tokenize("磁盘空间"), [],
    'bm25Tokenize began emitting CJK — the channel is then a duplicate of the English path, not an addition');
  assert.ok(matchTokens("磁盘空间").some((token) => /[\u4e00-\u9fff]/u.test(token)),
    'matchTokens stopped keeping CJK runs — the matcher and the shape guard both assume it does');
});

test('the stored index stays under the row ceiling on the real corpus', () => {
  // The 2 MB D1 row ceiling is what froze search on 2026-09-26; the stored size is gzip+base64 of the
  // whole index, so this is the number the PR body has to carry and the number a future change has to
  // watch. `plainBytes` is printed too: it is what the isolate holds in memory.
  const corpus = JSON.parse(readFileSync(new URL('../data/lessons.json', import.meta.url), 'utf8'))
    .map((l) => ({
      id: l.id, title: l.title || '', domain: l.domain || '', tags: l.tags || [], path: l.url || '',
      description: (l.summary || '').slice(0, 400),
      indexText: `${l.summary || ''} ${l.preview || ''}`.slice(0, 6000),
    }));
  const index = buildBM25Index(corpus);
  const plain = JSON.stringify(index);
  const cjkOnly = JSON.stringify({ ...index, cjk: undefined });
  return encodeIndexForStorage(plain).then((stored) => {
    const cjkTerms = Object.keys(index.cjk.terms).length;
    console.log(`  corpus ${index.docCount} docs · english terms ${Object.keys(index.terms).length} · `
      + `cjk bigrams ${cjkTerms} · cjk avgDocLen ${index.cjk.avgDocLen}`);
    console.log(`  plainBytes ${plain.length} (without the channel ${cjkOnly.length}) · storedBytes ${stored.length}`);
    assert.ok(cjkTerms > 1000, `only ${cjkTerms} bigrams were indexed — the channel is not carrying the corpus`);
    assert.ok(stored.length < 2_000_000,
      `the stored index is ${stored.length} bytes, at or over the 2 MB D1 row ceiling. The design's answer is `
      + 'to give index.cjk a row of its own, not to thin the channel out');
  });
});
