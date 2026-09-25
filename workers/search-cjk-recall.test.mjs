// Chinese-language recall, measured — and a floor that makes the next attempt fail loudly.
//
// WHY THIS EXISTS. H-04 in the 2026-09-24 handoff proposed "connect `bm25Tokenize`'s CJK path" as a
// ready-to-land fix. Two things were true and neither was written down anywhere a change author would
// find them before shipping:
//
//   1. The alias table translates a Chinese *query* into English (`如何切换模型` → `switch model`), but
//      the lessons answering those queries are written in Chinese. Recall is therefore capped by the
//      gap between the query's vocabulary and the documents' — and the twenty queries in
//      `scripts/eval_query_aliases.py` are the corpus's own measure of it. Nine of them find their
//      lesson today.
//   2. Making CJK visible to `bm25Tokenize` is not a local edit, and doing it naively is a
//      **regression**: it silently disables the relevance floor's fallback. When the tokenizer can see
//      the query, `originalTerms` is no longer empty, so the floor stops judging the expanded terms
//      and starts judging CJK bigrams while the scorer still scores English — an IDF ratio computed
//      across two disjoint term spaces. Measured on this corpus, expansion ON: **9/20 → 2/20**.
//
// The first fact argues for the change; the second says it is a redesign of the floor, not a patch. So
// this file asserts the number that exists and refuses to let it drop. An improvement passes; a
// regression fails with the measurement above in the message. That is the whole point: the next
// person to try gets told by CI rather than by production.
//
// Run: node --test workers/search-cjk-recall.test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import worker, { buildBM25Index, bm25Tokenize, BM25_INDEX_KEY, expandQueryAliases, scoringQueryFor } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('cjk-recall');

const CORPUS = JSON.parse(readFileSync(new URL('../data/lessons.json', import.meta.url), 'utf8'))
  .map((l) => ({
    id: l.id,
    title: l.title || '',
    domain: l.domain || '',
    tags: l.tags || [],
    path: l.url || '',
    description: (l.summary || '').slice(0, 400),
    indexText: `${l.summary || ''} ${l.preview || ''}`.slice(0, 6000),
  }));

function createEnv() {
  const store = new Map([
    [BM25_INDEX_KEY, JSON.stringify(buildBM25Index(CORPUS))],
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: CORPUS })],
  ]);
  return {
    MCP_TOKEN: TOKEN,
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

const env = createEnv();
let ip = 0;

async function search(query, top = 5) {
  ip += 1;
  const response = await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18', 'Origin': 'https://misakanet.org',
      'CF-Connecting-IP': `198.51.${Math.floor(ip / 200)}.${(ip % 200) + 1}`,
    },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query, top } } }),
  }), env);
  const body = await response.json();
  const payload = JSON.parse(body.result.content[0].text);
  return { ids: (payload.results || []).map((r) => r.id), noMatch: !!payload.no_match };
}

// `scripts/eval_query_aliases.py`'s QUERIES, reduced to (query, the lesson that answers it).
// The expected lesson is that file's `primary`; the alternates it lists are accepted too, because
// "the corpus answers this query" is the property under test, not which of two good lessons ranks
// first.
const ZH_QUERIES = [
  ['如何切换模型', ['model-switch-script-pattern']],
  ['pip 安装超时怎么办', ['pip-install-timeout-ssl']],
  ['pip install 卡住不动', ['lesson-08-pip-https-proxy-clash']],
  ['公司代理导致 SSL 证书校验失败', ['pip-install-proxy-timeout', 'corporate-proxy-curl-timeout']],
  ['磁盘空间不足怎么清理', ['disk-space-cleanup']],
  ['权限不足无法执行', ['permission-denied-fix']],
  ['定时任务不执行', ['cron-job-not-running']],
  ['Python 改了代码不生效', ['python-pycache-stale']],
  ['中文乱码怎么解决', ['python-gbk-encoding-error', 'wsl-pip-gbk-hub-poller-crash', 'aider-windows-unicode-error']],
  ['装了包还是提示模块找不到', ['python-venv-tiktoken-module-not-found', 'import-path-verification-after-refactor']],
  ['飞书机器人收不到消息', ['feishu-gateway-group-policy-silently-drops-messages']],
  ['WSL 内存占用过高', ['wsl2-memory-leak-fix']],
  ['容器内存不足被杀死', ['kubernetes-crashloopbackoff-debugging']],
  ['DCO 签名失败怎么办', ['dco-signoff-force-push-pitfall', 'ci-dco-decouple-pythonpath-fork-pr', 'error-dco-signoff-windows']],
  ['Node.js 连接被重置', ['n8n-nodejs-econnreset-connection-reset-fix']],
  ['git TLS 握手失败', ['git-tls-handshake-failure']],
  ['向量检索召回率低', ['bm25-vector-hybrid-search-weights', 'rag-retrieval-six-layer-silent-degradation']],
  ['机器人报警代码', ['fanuc-alarm-code-reference']],
  ['YAML 内联注释导致类型错误', ['yaml-inline-comment-type-coercion']],
  ['浏览器自动化被拦截', ['browser-automation-csp-bypass']],
];

// Measured 2026-09-25 on the corpus in this checkout, expansion enabled (the production default).
// Every one of these queries has a lesson in the corpus that answers it; the ones that are missing
// are the recall shortfall H-04 is about, listed by name in the failure message below rather than
// hidden behind a number. Raising this constant is how an improvement is recorded.
const RECALL_FLOOR = 9;

test('the Chinese eval set recalls at least the measured floor', async () => {
  const found = [];
  const missed = [];
  for (const [query, expected] of ZH_QUERIES) {
    const { ids } = await search(query);
    if (ids.slice(0, 3).some((id) => expected.includes(id))) found.push(query);
    else missed.push(query);
  }
  assert.ok(
    found.length >= RECALL_FLOOR,
    `Chinese recall dropped to ${found.length}/${ZH_QUERIES.length}, below the measured floor of `
    + `${RECALL_FLOOR}. If you made CJK visible to \`bm25Tokenize\`, this is the expected consequence `
    + 'and not a fluke: with the tokenizer able to see the query, `originalTerms` is no longer empty, '
    + 'so the relevance floor judges CJK bigrams while the scorer scores the *expanded English* terms '
    + '— an IDF ratio across two disjoint vocabularies, which rejects documents that answer the '
    + `query. Measured: 9/20 → 2/20. Still missing: ${missed.join(' | ')}`,
  );
});

test('every Chinese query reaches the scorer with at least one term', async () => {
  // The zero-term path (`if (queryTerms.length === 0) return []`) was #1780's symptom. It is worth
  // pinning separately from recall, because it is the one failure that returns *nothing at all*, and
  // because it is the case a CJK-aware tokenizer is usually proposed to fix. It is already fixed by
  // the alias expansion — so anyone reaching for the tokenizer to solve it is solving a solved
  // problem, and this test is what says so.
  const zeroTerm = [];
  for (const [query] of ZH_QUERIES) {
    const report = expandQueryAliases(query, env);
    const scored = scoringQueryFor(query, env);
    if (bm25Tokenize(scored).length === 0) {
      zeroTerm.push(`${query} (expanded: "${report.expanded}")`);
    }
  }
  assert.deepEqual(zeroTerm, [],
    `these queries reach searchLessonsBM25 with zero terms and can only ever return []: ${zeroTerm.join(', ')}`);
});

test('the tokenizer still cannot see CJK, and the reason is recorded', () => {
  // Not a wish — a statement of the current coupling, so that removing it is a deliberate act with a
  // failing neighbour test rather than a quiet side effect. `docs/maintainer/query-alias-design-*.md`
  // reaches the same conclusion: the CJK hole is a *query-side* bug with a query-side fix.
  assert.deepEqual(bm25Tokenize('如何切换识图模型'), [],
    'bm25Tokenize began emitting CJK tokens — the relevance floor\'s fallback depends on it not doing '
    + 'that (see the recall test above), so this change needs the floor re-derived, not just a green '
    + 'tokenizer test');
  assert.deepEqual(bm25Tokenize('git TLS 握手失败'), ['git', 'tls'],
    'latin tokens must survive unchanged: CJK visible or not, the latin path is what every existing '
    + 'calibration was measured on');
});

test('production does sync the index — the premise a ranking fix is judged against', () => {
  // A comment in `register-proxy-sw.js` said the opposite for months ("the BM25 index that production
  // never syncs"), and it was load-bearing: it was quoted as the reason a rank-level fix was not safe
  // to attempt. The statement is false and has been since 2026-09-12 10:49, so the fact is pinned here
  // rather than left in prose that nobody re-reads. Both halves are required — a cron that does not
  // call the rebuild, or a rebuild the cron cannot reach, is the same silence as no cron at all.
  const toml = readFileSync(new URL('./wrangler.toml', import.meta.url), 'utf8');
  const crons = /crons\s*=\s*\[\s*"([^"]+)"/.exec(toml);
  assert.ok(crons, 'workers/wrangler.toml declares no cron, so nothing rebuilds the index');
  const workerSrc = readFileSync(new URL('./register-proxy-sw.js', import.meta.url), 'utf8');
  assert.match(workerSrc, /ctx\.waitUntil\(refreshSearchIndex\(env\)/,
    `the ${crons[1]} cron does not refresh the search index — if that is deliberate, the note at the `
    + 'relevance floor must be updated, because that is the note a ranking change is judged against');
});
