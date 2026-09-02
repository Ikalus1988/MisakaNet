// PRD ④ #1356 tests: FTS5 full-text search via /api/lessons?q=.
// Run: node --test workers/d1-fts-search.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';

// D1 stub with lessons + lessons_fts MATCH support.
function createD1(rows) {
  const ftsRows = rows.map((r, i) => ({
    id: r.id, title: r.title, problem: r.problem || '', rank: i * 10,
    domain: r.domain, status: r.status, tags: JSON.stringify(r.tags || []),
    path: r.path, summary: r.summary || '', updated: r.updated, created: r.created,
  }));
  return {
    prepare(sql) {
      const stmt = {
        _bound: null,
        bind(...a) { stmt._bound = a; return stmt; },
        async all() {
          if (sql.includes('lessons_fts MATCH')) {
            // FTS5 MATCH is token-based: every query term must appear.
            const terms = String(stmt._bound?.[0] || '').toLowerCase().split(/\s+/).filter(Boolean);
            const domain = stmt._bound?.[1];
            const matched = ftsRows.filter(r => {
              const text = (r.title + ' ' + r.problem).toLowerCase();
              // Token-ish match: any query term appears as a word or prefix.
              const tokens = text.split(/[^a-z0-9]+/).filter(Boolean);
              return terms.every(t => tokens.some(tok => tok.startsWith(t) || t.startsWith(tok))) &&
                (!domain || r.domain === domain);
            }).sort((a, b) => a.rank - b.rank);
            return { results: matched.slice(0, 20) };
          }
          return { results: ftsRows };
        },
        async run() { return { success: true }; },
      };
      return stmt;
    },
  };
}

const ROWS = [
  {
    id: 'pip-timeout-ssl', title: 'pip install timeout with SSL', domain: 'python',
    status: 'published', tags: ['pip', 'ssl'], path: 'lessons/core/pip-timeout-ssl.md',
    problem: 'pip install fails with ReadTimeoutError', updated: 'u1', created: 'c1',
  },
  {
    id: 'dco-signoff', title: 'DCO sign-off failed', domain: 'git',
    status: 'published', tags: ['dco'], path: 'lessons/core/dco-signoff.md',
    problem: 'GitHub requires DCO sign-off on commits', updated: 'u2', created: 'c2',
  },
];

function apiSearch(query, env) {
  return worker.fetch(new Request(`https://misakanet.org/api/lessons?q=${encodeURIComponent(query)}`), env);
}

test('?q= returns ranked FTS5 results', async () => {
  const env = { MISAKANET_D1: createD1(ROWS) };
  const resp = await apiSearch('pip timeout', env);
  assert.equal(resp.status, 200);
  const data = await resp.json();
  assert.equal(data.source, 'd1-fts5');
  assert.ok(Array.isArray(data.results));
  assert.ok(data.results.length >= 1);
  assert.equal(data.results[0].id, 'pip-timeout-ssl');
  assert.equal(typeof data.results[0].rank, 'number');
});

test('?q= combines with domain filter', async () => {
  const env = { MISAKANET_D1: createD1(ROWS) };
  const resp = await worker.fetch(
    new Request('https://misakanet.org/api/lessons?q=signoff&domain=git'), env);
  assert.equal(resp.status, 200);
  const data = await resp.json();
  assert.equal(data.results.length, 1);
  assert.equal(data.results[0].id, 'dco-signoff');
});

test('?q= with no matches returns empty results', async () => {
  const env = { MISAKANET_D1: createD1(ROWS) };
  const resp = await apiSearch('zzz nonexistent topic', env);
  assert.equal(resp.status, 200);
  const data = await resp.json();
  assert.equal(data.results.length, 0);
});

test('?q= without D1 binding returns a hint', async () => {
  const env = {};
  const resp = await apiSearch('pip', env);
  assert.equal(resp.status, 200);
  const data = await resp.json();
  assert.match(JSON.stringify(data), /requires the D1 service/);
});
