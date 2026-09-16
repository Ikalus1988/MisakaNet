// PRD ④ tests: D1 lesson service — worker prefers D1 when bound, falls back
// to GitHub (KV cache) when not. Verifies search, /api/lessons, get_lesson.
// Run: node --test workers/d1-lesson-service.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('d1');

// D1 stub: prepare(sql).bind(...).all() filters the in-memory rows for the
// query shapes used by the worker: full scan, WHERE path=, WHERE id=,
// structured filters, analytics GROUP BY, and INSERT (run()). Applies
// LIMIT n from the SQL tail.
function createD1(rows) {
  return {
    _usage: [],
    _lastInsert: null,
    prepare(sql) {
      const limitMatch = sql.match(/LIMIT\s+(\d+)/i);
      const limit = limitMatch ? Number(limitMatch[1]) : Infinity;
      let matcher;
      if (sql.trim().startsWith('INSERT INTO lesson_usage')) {
        matcher = () => [];
      } else if (sql.includes('GROUP BY')) {
        // Analytics: aggregate the _usage rows by the grouped column.
        const groupCol = sql.includes('GROUP BY query') ? 'query'
          : sql.includes('GROUP BY lesson_id') ? 'lesson_id'
          : sql.includes('GROUP BY day') ? 'day'
          : sql.includes('GROUP BY date(created_at)') ? 'day'
          : 'query';
        matcher = () => {
          const map = {};
          for (const u of this._usage) {
            const key = groupCol === 'day' ? (u.created_at || '').slice(0, 10) : (u[groupCol] ?? '');
            map[key] = (map[key] || 0) + 1;
          }
          return Object.entries(map).map(([k, n]) => ({ [groupCol === 'day' ? 'day' : groupCol]: k, n }));
        };
      } else if (sql.includes('WHERE path = ?')) {
        matcher = (bound) => rows.filter((r) => r.path === bound[0]);
      } else if (sql.includes('WHERE id = ?')) {
        matcher = (bound) => rows.filter((r) => r.id === bound[0]);
      } else if (sql.includes('WHERE')) {
        // Generic: parse "col = ?N" / "col LIKE ?N" pairs from the WHERE clause.
        const conds = [];
        const re = /(\w+)\s*(=|LIKE)\s*\?(\d+)/g;
        let m;
        while ((m = re.exec(sql)) !== null) conds.push(m.slice(1));
        matcher = (bound) => rows.filter((r) => conds.every(([col, op, idx]) => {
          const val = bound[Number(idx) - 1];
          if (op === '=') return r[col] === val;
          if (op === 'LIKE') {
            const pat = val.replace(/^%|%$/g, '').replace(/^"|"$/g, '');
            return (r[col] || '').includes(pat);
          }
          return false;
        }));
      } else {
        matcher = () => rows;
      }
      const stmt = {
        bind(...args) {
          stmt._bound = args;
          return stmt;
        },
        async all() {
          const out = matcher(stmt._bound || []);
          return { results: out.slice(0, limit) };
        },
        async run() {
          // INSERT INTO lesson_usage — record for analytics aggregation.
          if (sql.trim().startsWith('INSERT INTO lesson_usage')) {
            const b = stmt._bound || [];
            this._d1 && this._d1._usage.push({
              event: b[0], query: b[1], lesson_id: b[2], domain: b[3],
              ip: b[4], user_agent: b[5], created_at: new Date().toISOString(),
            });
          }
          return { success: true };
        },
      };
      stmt._d1 = this;
      return stmt;
    },
  };
}

function createKV(seed = {}) {
  const store = new Map(Object.entries(seed));
  return {
    async get(key, type) {
      if (!store.has(key)) return null;
      const raw = store.get(key);
      return type === 'json' ? JSON.parse(raw) : raw;
    },
    async put(key, value) {
      store.set(key, value);
    },
    _store: store,
  };
}

const D1_ROWS = [
  {
    id: 'd1-pip-mirror',
    title: 'pip install timeout (from D1)',
    domain: 'python',
    status: 'published',
    tags: '["pip","network"]',
    path: 'lessons/core/d1-pip-mirror.md',
    summary: 'Use a mirror for pip timeouts.',
    problem: 'pip install times out.',
    updated: '2026-08-28T00:00:00Z',
    created: '2026-06-01T00:00:00Z',
  },
  {
    id: 'd1-dco',
    title: 'DCO sign-off (from D1)',
    domain: 'git',
    status: 'published',
    tags: '["github","dco"]',
    path: 'lessons/core/d1-dco.md',
    summary: 'GitHub requires sign-off.',
    problem: 'DCO check failed.',
    updated: '2026-08-27T00:00:00Z',
    created: '2026-06-02T00:00:00Z',
  },
];

function mcpSearch(query, env) {
  return worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '203.0.113.7',
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query } },
    }),
  }), env);
}

async function resultText(response) {
  const body = await response.json();
  return JSON.parse(body.result.content[0].text);
}

test('misakanet_search uses D1 rows when MISAKANET_D1 is bound', async () => {
  const env = {
    MCP_TOKEN: TOKEN,
    MISAKANET_D1: createD1(D1_ROWS),
    MISAKANET_KV: createKV(),
  };
  const resp = await mcpSearch('pip install timeout', env);
  assert.equal(resp.status, 200);
  const result = await resultText(resp);
  assert.ok(result.results.length >= 1);
  assert.equal(result.results[0].id, 'd1-pip-mirror');
  assert.match(result.results[0].title, /from D1/);
});

test('/api/lessons returns D1 rows when bound, with no REGISTER_TOKEN needed', async () => {
  const env = { MISAKANET_D1: createD1(D1_ROWS) };
  const resp = await worker.fetch(new Request('https://misakanet.org/api/lessons'), env);
  assert.equal(resp.status, 200);
  const data = await resp.json();
  assert.ok(Array.isArray(data));
  assert.equal(data.length, 2);
  assert.equal(data[0].id, 'd1-pip-mirror');
  assert.deepEqual(data[0].tags, ['pip', 'network']);
});

test('falls back to GitHub/KV cache when D1 is not bound', async () => {
  const lessons = [
    { id: 'gh-lesson', title: 'GitHub lesson', domain: 'devops', description: 'from github' },
  ];
  const env = {
    MCP_TOKEN: TOKEN,
    MISAKANET_KV: createKV({
      'proxy:lessons': JSON.stringify({ ts: Date.now(), data: lessons }),
    }),
  };
  const resp = await mcpSearch('GitHub lesson', env);
  assert.equal(resp.status, 200);
  const result = await resultText(resp);
  assert.equal(result.results[0].id, 'gh-lesson');
});

test('falls back to GitHub when D1 is bound but empty', async () => {
  const lessons = [
    { id: 'gh-fallback', title: 'GitHub fallback lesson', domain: 'devops', description: 'fallback' },
  ];
  const env = {
    MCP_TOKEN: TOKEN,
    MISAKANET_D1: createD1([]),
    MISAKANET_KV: createKV({
      'proxy:lessons': JSON.stringify({ ts: Date.now(), data: lessons }),
    }),
  };
  const resp = await mcpSearch('fallback lesson', env);
  const result = await resultText(resp);
  assert.equal(result.results[0].id, 'gh-fallback');
});

// ── get_lesson via D1 (PRD ④ §3.3) ──

const D1_FULL = D1_ROWS.map((r) => ({ ...r, content_md: `# ${r.title}\n\nFull body for ${r.id}.` }));

function mcpGetLesson(args, env) {
  return worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '203.0.113.8',
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_get_lesson', arguments: args },
    }),
  }), env);
}

test('misakanet_get_lesson returns full content from D1 by path', async () => {
  const env = { MCP_TOKEN: TOKEN, MISAKANET_D1: createD1(D1_FULL), MISAKANET_KV: createKV() };
  const resp = await mcpGetLesson({ path: 'lessons/core/d1-pip-mirror.md' }, env);
  assert.equal(resp.status, 200);
  const result = await resultText(resp);
  assert.equal(result.path, 'lessons/core/d1-pip-mirror.md');
  assert.match(result.content, /Full body for d1-pip-mirror/);
});

test('misakanet_get_lesson returns full content from D1 by id', async () => {
  const env = { MCP_TOKEN: TOKEN, MISAKANET_D1: createD1(D1_FULL), MISAKANET_KV: createKV() };
  const resp = await mcpGetLesson({ id: 'd1-dco' }, env);
  assert.equal(resp.status, 200);
  const result = await resultText(resp);
  assert.match(result.content, /Full body for d1-dco/);
});

test('misakanet_get_lesson falls back to GitHub when D1 has no row', async () => {
  // D1 bound but no matching row → fetchLessonFromD1 returns null → GitHub path.
  // GitHub will 401 without REGISTER_TOKEN, proving we attempted the fallback.
  const env = { MCP_TOKEN: TOKEN, MISAKANET_D1: createD1([]), MISAKANET_KV: createKV() };
  const resp = await mcpGetLesson({ id: 'no-such-lesson' }, env);
  const body = await resp.json();
  const text = body.result.content[0].text;
  // The tool reports a failure, and reports it *without* internals: this assertion used
  // to require the internal message (REGISTER_TOKEN / GitHub API 401) to be echoed back,
  // which is exactly the exposure CodeQL flagged (js/stack-trace-exposure, alert #258,
  // 2026-09-12). What a caller needs is that it failed and whether retrying helps.
  assert.match(text, /Retry shortly|internal_error|error/);
  assert.doesNotMatch(text, /REGISTER_TOKEN|GitHub API 401|Bearer /);
});

// ── Structured /api/lessons filters (PRD ④ §3.3) ──

function apiLessons(query, env) {
  return worker.fetch(new Request(`https://misakanet.org/api/lessons${query || ''}`), env);
}

test('/api/lessons?domain= filters rows via D1 SQL', async () => {
  const env = { MISAKANET_D1: createD1(D1_ROWS) };
  const resp = await apiLessons('?domain=python', env);
  assert.equal(resp.status, 200);
  const data = await resp.json();
  assert.ok(Array.isArray(data));
  assert.equal(data.length, 1);
  assert.equal(data[0].id, 'd1-pip-mirror');
});

test('/api/lessons?tag= filters by JSON tag containment', async () => {
  const env = { MISAKANET_D1: createD1(D1_ROWS) };
  const resp = await apiLessons('?tag=dco', env);
  assert.equal(resp.status, 200);
  const data = await resp.json();
  assert.equal(data.length, 1);
  assert.equal(data[0].id, 'd1-dco');
});

test('/api/lessons?status= with no matches returns empty array', async () => {
  const env = { MISAKANET_D1: createD1(D1_ROWS) };
  const resp = await apiLessons('?status=draft', env);
  assert.equal(resp.status, 200);
  const data = await resp.json();
  assert.deepEqual(data, []);
});

test('/api/lessons?domain= without D1 binding returns a filter hint, not the full list', async () => {
  const env = { MISAKANET_KV: createKV() }; // no D1, no REGISTER_TOKEN
  const resp = await apiLessons('?domain=python', env);
  const body = await resp.json();
  assert.match(JSON.stringify(body), /require the D1 service/);
});

test('/api/lessons?limit= caps result count', async () => {
  const env = { MISAKANET_D1: createD1(D1_ROWS) };
  const resp = await apiLessons('?limit=1', env);
  assert.equal(resp.status, 200);
  const data = await resp.json();
  assert.equal(data.length, 1);
});

// ── Analytics (PRD ④ #1357) ──

function seedUsage(d1, entries) {
  for (const e of entries) {
    d1._usage.push({ ...e, created_at: e.created_at || new Date().toISOString() });
  }
}

test('/api/analytics aggregates usage without auth', async () => {
  const d1 = createD1([]);
  seedUsage(d1, [
    { event: 'search', query: 'pip timeout', lesson_id: '', domain: 'python' },
    { event: 'search', query: 'pip timeout', lesson_id: '', domain: 'python' },
    { event: 'search', query: 'dco signoff', lesson_id: '', domain: 'git' },
    { event: 'no_match', query: 'zzz nonexistent', lesson_id: '', domain: '' },
    { event: 'get_lesson', query: '', lesson_id: 'pip-install-timeout-ssl', domain: 'python' },
  ]);
  const env = { MISAKANET_D1: d1 };
  const resp = await worker.fetch(new Request('https://misakanet.org/api/analytics'), env);
  assert.equal(resp.status, 200);
  const data = await resp.json();
  assert.ok(Array.isArray(data.top_searches));
  assert.equal(data.top_searches[0].query, 'pip timeout');
  assert.equal(data.top_searches[0].count, 2);
  assert.ok(data.knowledge_gaps.some(g => g.query === 'zzz nonexistent'));
  assert.ok(data.top_lessons.some(l => l.lesson_id === 'pip-install-timeout-ssl'));
});

test('trackUsage anonymizes IP to /16 prefix', async () => {
  // D1 with real rows so search returns results and records a search event.
  const d1 = createD1(D1_ROWS);
  const env = { MISAKANET_D1: d1, MCP_TOKEN: 'x' };
  const ctx = { waitUntil: (p) => p };
  const resp = await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: 'Bearer x',
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '203.0.113.42',
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query: 'dco', top: 1 } },
    }),
  }), env, ctx);
  assert.equal(resp.status, 200);
  // Search had results (D1_ROWS has d1-dco) → search event tracked.
  assert.ok(d1._usage.some(u => u.event === 'search' && u.query === 'dco'));
  // IP anonymized to first 2 octets: 203.0.113.42 → 203.0.0.0
  assert.ok(d1._usage.some(u => u.ip === '203.0.0.0'));
});

// ── Optional structured fields: summary_plain / trigger / verify (#1783) ──
//
// Two properties, both demanded by the issue:
//
//   1. a lesson that carries NONE of the three fields must produce exactly today's
//      response — same keys, same order, no new nulls: byte-identical, not merely
//      "compatible";
//   2. a lesson that carries them gets them back, through both `misakanet_search`
//      (compact / summary / full) and `misakanet_get_lesson`.
//
// The projection is additive by construction (`{...(x ? {k: x} : {})}` — an empty
// spread adds nothing), so these tests pin the *observable* consequence rather than
// the mechanism.

function mcpTool(name, args, env) {
  return worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '203.0.113.91',
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name, arguments: args },
    }),
  }), env);
}

async function toolPayload(name, args, env) {
  const resp = await mcpTool(name, args, env);
  assert.equal(resp.status, 200);
  return await resp.json();
}

// A lesson body whose `updated` is always "5 days ago", so `freshness` is "recent"
// no matter when the suite runs — an exact-string assertion below depends on it.
const FIVE_DAYS_AGO = new Date(Date.now() - 5 * 86400000).toISOString();

const LEGACY_ROW = {
  id: 'legacy-shape',
  title: 'pip install timeout behind corporate proxy',
  domain: 'python',
  status: 'published',
  tags: '["pip","network"]',
  path: 'lessons/contrib/legacy-shape.md',
  summary: 'Use an internal mirror.',
  problem: 'pip install times out behind the proxy.',
  updated: FIVE_DAYS_AGO,
  created: FIVE_DAYS_AGO,
};

const PLAIN_FIELDS = {
  summary_plain: '公司网络里装不上 Python 包，是因为下载源要先换成公司内部的镜像。',
  trigger: 'pip install timeout behind proxy',
  verify: 'pip install -v httpie 退出码为 0',
};

// The same lesson's body, with frontmatter that predates the three fields — the
// content `misakanet_get_lesson` returns for a legacy lesson.
const LEGACY_BODY = [
  '---',
  'title: "pip install timeout behind corporate proxy"',
  'domain: "python"',
  'status: "published"',
  'tags: ["pip", "network"]',
  'evidence_level: "E2"',
  '---',
  '',
  '## Problem',
  '',
  'pip install times out behind the proxy.',
  '',
].join('\n');

const FIELDS_BODY = [  '---',
  'title: "pip install timeout behind corporate proxy"',
  'domain: "python"',
  'status: "published"',
  'tags: ["pip", "network"]',
  `summary_plain: "${PLAIN_FIELDS.summary_plain}"`,
  `trigger: "${PLAIN_FIELDS.trigger}"`,
  `verify: "${PLAIN_FIELDS.verify}"`,
  '---',
  '',
  '## Problem',
  '',
  'pip install times out behind the proxy.',
  '',
  '## Root Cause',
  '',
  'The corporate index is unreachable.',
  '',
  '## Solution',
  '',
  'Use an internal mirror.',
  '',
  '## Verification',
  '',
  'pip install -v httpie succeeds.',
  '',
].join('\n');

test('a lesson without the structured fields keeps the exact legacy shape (#1783)', async () => {
  // D1 row without a `frontmatter` column at all — the shape every legacy lesson has.
  const env = {
    MCP_TOKEN: TOKEN,
    MISAKANET_D1: createD1([{ ...LEGACY_ROW, content_md: LEGACY_BODY }]),
    MISAKANET_KV: createKV(),
  };

  for (const detail of ['compact', 'summary', 'full']) {
    const resp = await mcpTool('misakanet_search', { query: 'pip install timeout', detail }, env);
    const parsed = await resultText(resp);
    const hit = parsed.results[0];
    assert.equal(hit.id, 'legacy-shape');
    for (const field of Object.keys(PLAIN_FIELDS)) {
      assert.ok(!(field in hit), `detail=${detail} grew a ${field} key on a legacy lesson`);
    }
  }

  // Key *order* is part of the contract too: additive means appended-when-present,
  // never reordered.
  const compact = await resultText(await mcpTool('misakanet_search', { query: 'pip install timeout', detail: 'compact' }, env));
  assert.deepEqual(Object.keys(compact.results[0]),
    ['id', 'title', 'problem', 'freshness', 'evidence_level', 'kind']);

  const summary = await resultText(await mcpTool('misakanet_search', { query: 'pip install timeout', detail: 'summary' }, env));
  assert.deepEqual(Object.keys(summary.results[0]),
    ['id', 'title', 'problem', 'freshness', 'evidence_level', 'domain', 'tags', 'fix', 'kind']);

  // Byte level, not just key level: the compact hit serializes to exactly the string
  // it produced before #1783 touched the projection.
  assert.equal(
    JSON.stringify(compact.results[0]),
    '{"id":"legacy-shape","title":"pip install timeout behind corporate proxy",'
    + '"problem":"pip install times out behind the proxy.","freshness":"recent",'
    + '"evidence_level":"","kind":"lessons"}',
  );

  // And the same for get_lesson: no key, no empty value.
  const lessonResp = await mcpTool('misakanet_get_lesson', { id: 'legacy-shape' }, env);
  const lesson = await resultText(lessonResp);
  assert.deepEqual(Object.keys(lesson), ['path', 'content', 'identity', 'trust_notice', 'voice']);
  for (const field of Object.keys(PLAIN_FIELDS)) {
    assert.ok(!(field in lesson), `get_lesson grew a ${field} key on a legacy lesson`);
  }
});

test('a lesson with the structured fields carries them through search and get_lesson (#1783)', async () => {
  // Corpus row as D1 serves it: the three fields live inside the raw `frontmatter`
  // column, which the rich projection now reads.
  const row = { ...LEGACY_ROW, frontmatter: JSON.stringify({ ...PLAIN_FIELDS, title: LEGACY_ROW.title }) };
  const env = {
    MCP_TOKEN: TOKEN,
    MISAKANET_D1: createD1([{ ...row, content_md: FIELDS_BODY }]),
    MISAKANET_KV: createKV(),
  };

  const compact = await resultText(await mcpTool('misakanet_search', { query: 'pip install timeout', detail: 'compact' }, env));
  assert.equal(compact.results[0].summary_plain, PLAIN_FIELDS.summary_plain);
  assert.ok(!('trigger' in compact.results[0]), 'compact is the ~80-token tier: summary_plain only');
  assert.deepEqual(Object.keys(compact.results[0]),
    ['id', 'title', 'problem', 'freshness', 'evidence_level', 'summary_plain', 'kind']);

  const summary = await resultText(await mcpTool('misakanet_search', { query: 'pip install timeout', detail: 'summary' }, env));
  assert.equal(summary.results[0].summary_plain, PLAIN_FIELDS.summary_plain);
  assert.equal(summary.results[0].trigger, PLAIN_FIELDS.trigger);
  assert.equal(summary.results[0].verify, PLAIN_FIELDS.verify);
  assert.deepEqual(Object.keys(summary.results[0]),
    ['id', 'title', 'problem', 'freshness', 'evidence_level', 'summary_plain', 'domain', 'tags', 'fix', 'trigger', 'verify', 'kind']);

  const full = await resultText(await mcpTool('misakanet_search', { query: 'pip install timeout', detail: 'full' }, env));
  for (const [field, value] of Object.entries(PLAIN_FIELDS)) {
    assert.equal(full.results[0][field], value, `detail=full lost ${field}`);
  }

  // get_lesson reads them out of the returned body's frontmatter — the one path that
  // needs no ingest change, so it has to work for both frontmatter dialects.
  const lesson = await resultText(await mcpTool('misakanet_get_lesson', { id: 'legacy-shape' }, env));
  for (const [field, value] of Object.entries(PLAIN_FIELDS)) {
    assert.equal(lesson[field], value, `get_lesson lost ${field}`);
  }
  assert.deepEqual(Object.keys(lesson),
    ['path', 'content', 'summary_plain', 'trigger', 'verify', 'identity', 'trust_notice', 'voice']);

  // Legacy JSON frontmatter (the older convention) is parsed the same way.
  const jsonBody = `---\n${JSON.stringify({ ...PLAIN_FIELDS, title: 'JSON frontmatter lesson' })}\n---\n\n## Problem\n\nx\n`;
  const jsonEnv = {
    MCP_TOKEN: TOKEN,
    MISAKANET_D1: createD1([{ ...LEGACY_ROW, id: 'json-fm', content_md: jsonBody }]),
    MISAKANET_KV: createKV(),
  };
  const jsonLesson = await resultText(await mcpTool('misakanet_get_lesson', { id: 'json-fm' }, jsonEnv));
  assert.equal(jsonLesson.trigger, PLAIN_FIELDS.trigger);
  assert.equal(jsonLesson.verify, PLAIN_FIELDS.verify);
});

test('the index/KV fallback carries the structured fields when the row has them (#1783)', async () => {
  // data/lessons.json is another corpus source; the projection must not depend on
  // which one answered.
  const lessons = [{ ...LEGACY_ROW, tags: ['pip'], ...PLAIN_FIELDS }];
  const env = {
    MCP_TOKEN: TOKEN,
    MISAKANET_KV: createKV({ 'proxy:lessons': JSON.stringify({ ts: Date.now(), data: lessons }) }),
  };
  const summary = await resultText(await mcpTool('misakanet_search', { query: 'pip install timeout', detail: 'summary' }, env));
  assert.equal(summary.results[0].summary_plain, PLAIN_FIELDS.summary_plain);
  assert.equal(summary.results[0].trigger, PLAIN_FIELDS.trigger);
  assert.equal(summary.results[0].verify, PLAIN_FIELDS.verify);
});

