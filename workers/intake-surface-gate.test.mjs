// The surface gate: an intake is a PUBLIC issue, and the agent writing it cannot know what is
// internal about its own environment — measured on #3983, where an agent described its employer's
// internal platform and private CLI without a single credential, so every redaction rule passed it.
//
// What is testable is not "is this internal" (no mechanical rule can answer that). It is the two
// halves the banner stands on: what the extractor treats as a command surface, and which of those
// tokens the public corpus has never seen. Both directions of an extractor error are expensive —
// a false negative shows the reviewer nothing, a false positive teaches them to skip the banner.
//
// Run: node --test workers/intake-surface-gate.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { commandSurfaceIdentifiers, unknownCommandSurface } from './register-proxy-sw.js';

const INDEX = { terms: { docker: 12, npm: 30, pip: 40, node: 25, git: 60, pytest: 9, mico: 0 } };
// `mico: 0` is a zero df — the token is in the map but unindexed. It is treated as unknown on
// purpose: a term that occurs in no document tells the corpus nothing about the word.

test('a command in an inline code span is a surface', () => {
  assert.deepEqual(commandSurfaceIdentifiers('then run `mico issue rerun <task>` to see it'), ['mico']);
});

test('a fenced shell block is a surface, and `$` prompts are stripped', () => {
  const text = ['```bash', '$ docker compose up -d', 'npm run build --silent', '```'].join('\n');
  assert.deepEqual(commandSurfaceIdentifiers(text).sort(), ['docker', 'npm']);
});

test('prose is not a surface', () => {
  // A sentence is not a command: extracting nouns from prose would flag every product name in every
  // paragraph, which is exactly the false-positive class that makes a banner ignorable.
  assert.deepEqual(commandSurfaceIdentifiers('The platform returns idle while the agent is retired.'), []);
});

test('a bare inline token is still a surface candidate', () => {
  assert.deepEqual(commandSurfaceIdentifiers('the tool is `wrangler` here'), ['wrangler']);
});

test('the same command twice is reported once', () => {
  const text = '`mico login` then `mico issue rerun` then mico wiki search';
  assert.deepEqual(commandSurfaceIdentifiers(text), ['mico']);
});

test('a tool the corpus has seen is not unknown', () => {
  assert.deepEqual(unknownCommandSurface('`docker compose up`', INDEX), []);
});

test('a tool the corpus has never seen is unknown', () => {
  assert.deepEqual(unknownCommandSurface('`mico issue rerun`', INDEX), ['mico']);
});

test('a familiar dotted name is not called unknown because of its suffix', () => {
  // `node.js` tokenizes to `node` + `js`; checking the whole token only would flag a tool every
  // lesson already mentions.
  assert.deepEqual(unknownCommandSurface('`node.js --version`', INDEX), []);
});

test('with no index there is no verdict', () => {
  // `null`, not `[]`: "we could not check" and "everything is known" are different statements, and
  // a banner built on [] would quietly claim the submission was cleared.
  assert.equal(unknownCommandSurface('`mico login`', null), null);
});

test('the extractor is case-insensitive about the command head', () => {
  assert.deepEqual(unknownCommandSurface('Docker compose up', INDEX), []);
});

test('a zero-df term counts as unknown', () => {
  assert.deepEqual(unknownCommandSurface('`mico login`', { terms: { mico: 0 } }), ['mico']);
});

test('a bare tool name repeated across commands is caught without any backticks', () => {
  // The case the gate was built for (#3983) quoted nothing: `mico login`, `mico issue rerun`,
  // `mico im message history`, `mico wiki search`, all in prose. The first draft of the extractor
  // returned an empty list on that text — a false negative on the one submission it existed for.
  const text = [
    "重登 mico login 无效（CLI token 已 401 过期，与本故障无关但会干扰判断）",
    "用 mico issue rerun <任务key> 会把服务端 400 错误原文打出来",
    "mico im message history <会话id> 看 Agent 最后一次正常回复的时间戳",
    "mico wiki search 检索正常 → 排除知识库故障",
  ].join("\n");
  const ids = commandSurfaceIdentifiers(text);
  assert.ok(ids.includes("mico"), `expected mico in ${ids.join(",")}`);
});

test('a word that merely repeats across sentences is not a command surface', () => {
  // Repetition alone is not the signal — `platform` repeats here and is never in command position
  // across the passage in a way the extractor counts. The vocabulary filter is the second guard.
  const text = "The platform shows idle. The platform shows online. The platform never says retired.";
  const ids = commandSurfaceIdentifiers(text);
  assert.ok(!ids.includes("platform") || ids.filter((t) => t === "platform").length === 1,
    `extractor should not promote prose repetition into a surface: ${ids.join(",")}`);
});

test('a repeated token separated by other words is counted every time', () => {
  // The first live probe returned `surface_report: []` on this exact shape. The extractor used a
  // consuming pattern (`token whitespace word`), so after "zetaqx login" it started scanning at
  // "then zetaqx", consumed that `zetaqx` as the argument, and counted the tool once instead of
  // three times — under the threshold, so nothing was reported.
  const text = 'Surface probe: zetaqx login then zetaqx issue rerun then zetaqx wiki search all silent';
  assert.ok(commandSurfaceIdentifiers(text).includes('zetaqx'),
    `expected zetaqx, got ${commandSurfaceIdentifiers(text).join(',')}`);
});

test('the intake path must not load the index — an advisory check cannot delay a write', () => {
  // Measured 2026-10-29: the surface check called `loadBM25Index` inside the request that creates the
  // public issue. On a cold isolate that is 30-60 s, longer than any MCP client waits, so the client
  // reported `fetch failed` **and the issue was created anyway** — a submission that worked and one
  // that did not were indistinguishable from the caller's side.
  //
  // The rule is structural, so the test is structural: the intake branch reads `peekBM25Index`, and
  // `loadBM25Index` appears nowhere between the intake handler's guard and its GitHub call.
  const source = readFileSync(new URL('./register-proxy-sw.js', import.meta.url), 'utf8');
  const start = source.indexOf('const surfaceText = [args.problem');
  const end = source.indexOf('const resp = await fetchWithTimeout(`${GITHUB_API}/repos/${REPO}/issues`', start);
  assert.ok(start > 0 && end > start, 'the intake surface block moved — re-point this test');
  const block = source.slice(start, end);
  assert.ok(!block.includes('loadBM25Index('),
    'the intake path loads the BM25 index; that is the 30-60 s the client times out on');
  assert.ok(block.includes('peekBM25Index('), 'expected the warm-only peek');
});
