// Query alias expansion wired into the worker (#1780).
//
// Before this change `bm25Tokenize` erased CJK (`[^a-z0-9]+` → space), so a Chinese
// question arrived at `searchLessonsBM25` with ZERO query terms and the function
// returned `[]` before scoring anything — 11/20 of the offline eval set
// (`scripts/eval_query_aliases.py`). The word list now lives in
// data/query-aliases.json and is read by both this Worker (inlined, see
// QUERY_ALIAS_TABLE) and the local CLI.
//
// What these tests pin, in order:
//   1. the inlined table is still the file (drift guard — the file is the source);
//   2. a Chinese query's expansion really reaches the scorer (the intermediate terms,
//      not just "some hits came back");
//   3. the whole path through the MCP endpoint finds the lesson, and the
//      MISAKANET_QUERY_ALIASES=0 switch restores the old behaviour;
//   4. the expansion can add score but never authority (the relevance floor keeps
//      judging the words the user typed), so plain-English queries are not made worse;
//   5. the JS port and the Python implementation agree query by query.
//
// Run: node --test workers/query-alias-expansion.test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import test from 'node:test';
import worker, {
  QUERY_ALIAS_TABLE,
  QUERY_ALIAS_VERSION,
  QUERY_ALIAS_MAX_EXPANSIONS,
  aliasTokenize,
  bm25Tokenize,
  expandQueryAliases,
  queryAliasEnabled,
  scoringQueryFor,
} from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.join(HERE, '..');
const TOKEN = testToken('query-alias');

const TABLE_FILE = JSON.parse(readFileSync(path.join(REPO, 'data/query-aliases.json'), 'utf8'));

// The query set the design doc and the offline eval use, plus the English fixture
// queries (`data/regression_queries.json`) and the two shapes that used to inject an
// unrelated expansion (`path traversal` matched `pat`, `proxy` matched `pr`).
const CHINESE_QUERIES = [
  '如何切换识图模型', '中文乱码怎么解决', '定时任务不执行', '权限不足无法执行',
  '磁盘空间不足怎么清理', '容器内存不足被杀死', '公司代理导致 SSL 证书校验失败',
  'git TLS 握手失败', 'WSL 内存占用过高', '机器人报警代码',
];
const FIXTURE_QUERIES = JSON.parse(
  readFileSync(path.join(REPO, 'data/regression_queries.json'), 'utf8')).queries.map(q => q.query);
const PARITY_QUERIES = [
  ...CHINESE_QUERIES,
  ...FIXTURE_QUERIES,
  'mcp tool not showing', 'pip timeout', 'gbk error', 'dco fail', 'database locked',
  'path traversal', 'async cache async cache', 'exit code 137', 'dco-signoff missing',
  'powershel', '如何切换识图模型 memory leak', '工具 长什么样',
];

// ── 1. the inlined copy is the file ─────────────────────────────────────────
// A Worker cannot read a file at runtime, so the table travels as a constant. This is
// the test that keeps the constant honest: it re-derives the projection from
// data/query-aliases.json (same rules as scripts/expand_query.py::worker_table) and
// fails the moment the two drift apart.
function projectedTable(file) {
  const aliases = [];
  for (const raw of file.aliases) {
    const kind = file.kinds[raw.kind];
    aliases.push({
      alias: raw.alias, canonical: raw.canonical, kind: raw.kind,
      direction: raw.direction === undefined ? kind.direction : raw.direction,
      weight: raw.weight === undefined ? kind.weight : raw.weight,
      replace: raw.replace === undefined ? kind.replace : raw.replace,
    });
  }
  const kinds = {};
  for (const [name, spec] of Object.entries(file.kinds)) {
    kinds[name] = { direction: spec.direction, weight: spec.weight, replace: spec.replace };
  }
  return { version: file.schema.version, stopwords_zh: file.stopwords.zh, kinds, aliases };
}

test('the worker inlines exactly the projection of data/query-aliases.json', () => {
  assert.deepEqual(QUERY_ALIAS_TABLE, projectedTable(TABLE_FILE));
  assert.equal(QUERY_ALIAS_TABLE.aliases.length, TABLE_FILE.aliases.length);
  assert.ok(QUERY_ALIAS_TABLE.aliases.length >= 60, 'a truncated table would pass a shallow check');
});

test('the worker revision constant tracks the table file', () => {
  // The word list has its own revision precisely so that it does NOT have to move
  // INDEX_TEXT_VERSION (see the comment on that constant).
  assert.equal(QUERY_ALIAS_VERSION, TABLE_FILE.schema.version);
  assert.equal(QUERY_ALIAS_VERSION, QUERY_ALIAS_TABLE.version);
});

// ── 2. the expansion reaches the scorer ─────────────────────────────────────
test('a Chinese query is invisible to bm25Tokenize and visible after expansion', () => {
  // The bug, stated as an assertion: the production tokenizer drops every CJK
  // character, so this is the exact query string that used to reach
  // searchLessonsBM25 and return [] one line later.
  assert.deepEqual(bm25Tokenize('如何切换识图模型'), []);

  const report = expandQueryAliases('如何切换识图模型', {});
  assert.equal(report.changed, true, JSON.stringify(report));
  assert.deepEqual(report.added_terms.map(t => t.term).sort(), ['model', 'switch', 'vision']);

  // …and the *intermediate* string that actually goes to the scorer carries terms:
  const scoringQuery = scoringQueryFor('如何切换识图模型', {});
  const terms = bm25Tokenize(scoringQuery);
  assert.deepEqual(terms.sort(), ['model', 'switch', 'vision']);
  assert.equal(report.expanded, scoringQuery);
});

test('every Chinese query in the eval set reaches the scorer with terms', () => {
  for (const query of CHINESE_QUERIES) {
    const scoringQuery = scoringQueryFor(query, {});
    const terms = bm25Tokenize(scoringQuery);
    assert.ok(terms.length > 0, `${query}: expansion produced no scorer terms (${scoringQuery})`);
  }
});

test('a query that already tokenizes keeps its own terms (no term is dropped)', () => {
  // `replace` only ever drops text the target tokenizer cannot index (CJK, typos), so a
  // Latin fixture query must keep every term it started with.
  for (const query of FIXTURE_QUERIES) {
    const before = bm25Tokenize(query);
    const after = bm25Tokenize(scoringQueryFor(query, {}));
    for (const term of before) {
      assert.ok(after.includes(term), `${query}: lost term ${term} (${JSON.stringify(after)})`);
    }
  }
});

test('a hyphenated query keeps its compound token', () => {
  // bm25Tokenize extracts `dcosignoff` from "dco-signoff"; an unconditional rewrite of
  // the query would lose it, which is why scoringQueryFor returns the original string
  // whenever the expansion changes nothing.
  assert.ok(bm25Tokenize('dco-signoff missing').includes('dcosignoff'));
  assert.equal(scoringQueryFor('dco-signoff missing', {}), 'dco-signoff missing');
  assert.ok(bm25Tokenize(scoringQueryFor('dco-signoff missing', {})).includes('dcosignoff'));
});

test('the expansion no longer matches inside a longer word', () => {
  // Found while wiring this issue: raw substring matching made `pat` match `path`,
  // `pr` match `proxy`/`process` and `sse` match `assets`, so `path traversal` came
  // back as `path traversal personal access token`.
  for (const query of ['path traversal', 'patch the config', 'assets pipeline', 'storage backend']) {
    assert.equal(expandQueryAliases(query, {}).changed, false, query);
    assert.equal(scoringQueryFor(query, {}), query);
  }
  // CJK has no word boundaries and must keep substring matching.
  assert.equal(expandQueryAliases('如何切换识图模型', {}).expanded, 'vision switch model');
});

// ── 3. the switch ───────────────────────────────────────────────────────────
test('expansion is on by default and off only for explicit falsy values', () => {
  assert.equal(queryAliasEnabled({}), true);
  assert.equal(queryAliasEnabled({ MISAKANET_QUERY_ALIASES: '' }), true);
  assert.equal(queryAliasEnabled({ MISAKANET_QUERY_ALIASES: '1' }), true);
  assert.equal(queryAliasEnabled({ MISAKANET_QUERY_ALIASES: 'ON' }), true);
  for (const value of ['0', 'false', 'FALSE', ' off ', 'no']) {
    assert.equal(queryAliasEnabled({ MISAKANET_QUERY_ALIASES: value }), false, value);
  }
  const off = expandQueryAliases('如何切换识图模型', { MISAKANET_QUERY_ALIASES: '0' });
  assert.equal(off.enabled, false);
  assert.equal(off.expanded, '如何切换识图模型');
  assert.equal(scoringQueryFor('如何切换识图模型', { MISAKANET_QUERY_ALIASES: '0' }), '如何切换识图模型');
});

// ── 4. end to end through the MCP endpoint ──────────────────────────────────
// Synthetic corpus: the lesson is written in English (as the real corpus is — the
// Worker's index has no CJK tokens at all), the question is Chinese.
const LESSONS = [
  { id: 'vision-switch', title: 'How to switch the vision model', domain: 'ai', path: 'lessons/core/vision-switch.md',
    description: 'switch model', summary: 'Switch the vision model in the config', preview: 'Set VISION_MODEL and switch the model.' },
  { id: 'cron-check', title: 'Cron job not running', domain: 'ops', path: 'lessons/core/cron-check.md',
    description: 'cron', summary: 'Check the scheduler', preview: 'cron systemd scheduler checklist' },
  { id: 'filler-1', title: 'hook api error one', domain: 'ops', path: 'lessons/contrib/filler-1.md',
    description: 'hook', summary: 'api', preview: 'hook api' },
  { id: 'filler-2', title: 'hook api error two', domain: 'ops', path: 'lessons/contrib/filler-2.md',
    description: 'hook', summary: 'api', preview: 'hook api' },
];

function buildIndex() {
  const terms = new Map();
  const docs = [];
  const add = (term, doc, tf = 1) => {
    if (!terms.has(term)) terms.set(term, { idf: 3, docs: [] });
    terms.get(term).docs.push({ doc, tf, len: 20 });
  };
  LESSONS.forEach((lesson, i) => {
    docs.push({ id: lesson.id, title: lesson.title, domain: lesson.domain, path: lesson.path });
    for (const term of bm25Tokenize(`${lesson.title} ${lesson.summary} ${lesson.preview}`)) add(term, i);
  });
  const termObject = {};
  for (const [term, data] of terms) termObject[term] = data;
  return { version: 1, docCount: docs.length, avgDocLen: 20, terms: termObject, docs };
}

function createEnv(extra = {}) {
  const index = buildIndex();
  const store = new Map([
    ['worker_search_index', JSON.stringify(index)],
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: LESSONS.map(l => ({ ...l, status: 'published', tags: [] })) })],
  ]);
  return {
    MCP_TOKEN: TOKEN,
    MCP_VERSION: 'query-alias-test',
    ...extra,
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) { store.set(key, value); },
      async delete(key) { store.delete(key); },
    },
  };
}

async function search(query, env = createEnv(), args = {}) {
  const resp = await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '198.51.100.' + (Math.floor(Math.random() * 200) + 1),
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query, ...args } },
    }),
  }), env);
  assert.equal(resp.status, 200);
  const body = await resp.json();
  assert.equal(body.error, undefined, JSON.stringify(body.error));
  return JSON.parse(body.result.content[0].text);
}

test('a Chinese question now finds the English lesson, through the real endpoint', async () => {
  const result = await search('如何切换识图模型');
  assert.equal(result.source, 'worker-bm25', 'the production path must be the one under test');
  assert.equal(result.no_match, undefined, JSON.stringify(result));
  assert.equal(result.results[0].id, 'vision-switch');
});

test('MISAKANET_QUERY_ALIASES=0 restores the old behaviour without a code change', async () => {
  const off = await search('如何切换识图模型', createEnv({ MISAKANET_QUERY_ALIASES: '0' }));
  assert.equal(off.no_match, true, JSON.stringify(off.results));
  assert.deepEqual(off.results, []);
  // The switch is a query-path switch, not a memory of the previous request.
  const on = await search('如何切换识图模型');
  assert.equal(on.results[0].id, 'vision-switch');
});

test('another Chinese question reaches its own lesson', async () => {
  const result = await search('定时任务不执行');
  assert.equal(result.no_match, undefined, JSON.stringify(result));
  assert.equal(result.results[0].id, 'cron-check');
});

test('the expansion may add score but never authority (the floor still judges the user words)', async () => {
  // `pip install timeout` is an English query: expansion adds nothing today (there is
  // no alias for those words), so the guard is asserted on a query whose expansion is
  // real — `proxy` reaches the migrated #532 co-occurrence layer. The floor must keep
  // judging "proxy"/"zzz…", so the admitted document set is the one the switch-off run
  // admits, whatever the added terms score elsewhere.
  const query = 'proxy zzzunknownterm';
  const on = await search(query, createEnv(), { top: 10 });
  const off = await search(query, createEnv({ MISAKANET_QUERY_ALIASES: '0' }), { top: 10 });
  assert.deepEqual(
    (on.results || []).map(r => r.id).sort(),
    (off.results || []).map(r => r.id).sort(),
    `switch flipped the admitted set: on=${JSON.stringify(on.results)} off=${JSON.stringify(off.results)}`);
});

test('an unseen English query still returns no_match (the floor is not filled by expansion)', async () => {
  const result = await search('zzz-econnrefused-on-corporate-proxy-404');
  assert.equal(result.no_match, true, JSON.stringify(result.results));
  assert.deepEqual(result.results, []);
});

// ── 5. parity with the Python implementation ────────────────────────────────
// The Worker runs a port of scripts/expand_query.py::expand. A port that drifts is
// worse than no port: the local CLI would answer from a different word list than
// production. These queries are compared value by value.
function pythonExpansion(query) {
  const res = spawnSync('python3', [path.join(REPO, 'scripts', 'expand_query.py'), '--json', '-q', query],
                        { cwd: REPO, encoding: 'utf8' });
  if (res.error && res.error.code === 'ENOENT') return null;      // no interpreter here
  assert.equal(res.status, 0, res.stderr);
  return JSON.parse(res.stdout);
}

test('the JS port and the Python implementation expand identically', (t) => {
  const probe = pythonExpansion('如何切换识图模型');
  if (probe === null) {
    t.skip('python3 is not available in this environment — parity not verified');
    return;
  }
  for (const query of PARITY_QUERIES) {
    const py = pythonExpansion(query);
    const js = expandQueryAliases(query, {});
    assert.equal(js.expanded, py.expanded, `${query}: expanded differs`);
    assert.equal(js.changed, py.changed, `${query}: changed differs`);
    assert.deepEqual(js.added_terms.map(a => a.term), py.added_terms.map(a => a.term),
                     `${query}: added terms differ`);
    assert.deepEqual(js.matched.map(m => [m.alias, m.canonical, m.kind]),
                     py.matched.map(m => [m.alias, m.canonical, m.kind]), `${query}: matches differ`);
    assert.deepEqual(js.dropped_terms, py.dropped_terms, `${query}: dropped terms differ`);
    assert.deepEqual(js.stopwords_removed, py.stopwords_removed, `${query}: stopwords differ`);
    assert.equal(js.related_fallback, py.related_fallback, `${query}: fallback layer differs`);
  }
});

test('the JS and Python tokenizers agree on the alias tokenization', (t) => {
  const query = '如何切换识图模型 dco-signoff tools/list 内存泄漏';
  const res = spawnSync('python3', ['-c',
    'import sys, json; sys.path.insert(0, "scripts"); import expand_query as e;'
    + 'print(json.dumps(e.tokenize(sys.argv[1]), ensure_ascii=False))', query],
    { cwd: REPO, encoding: 'utf8' });
  if (res.error && res.error.code === 'ENOENT') {
    t.skip('python3 is not available in this environment — tokenizer parity not verified');
    return;
  }
  assert.equal(res.status, 0, res.stderr);
  assert.deepEqual(aliasTokenize(query), JSON.parse(res.stdout));
});
