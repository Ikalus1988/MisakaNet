// PRD ④ #1356 tests: FTS5 full-text search via /api/lessons?q=.
// Run: node --test workers/d1-fts-search.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, { buildFtsMatch } from './register-proxy-sw.js';

// D1 stub with lessons + lessons_fts MATCH support.
function createD1(rows) {
  const ftsRows = rows.map((r, i) => ({
    id: r.id, title: r.title, problem: r.problem || '', rank: i * 10,
    domain: r.domain, status: r.status, tags: JSON.stringify(r.tags || []),
    path: r.path, summary: r.summary || '', updated: r.updated, created: r.created,
  }));
  const d1 = {
    // Every MATCH string this stub was asked to evaluate, in order — so a test can assert that the strict
    // attempt happens first and the relaxed one only when it found nothing.
    matchQueries: [],
    prepare(sql) {
      const stmt = {
        _bound: null,
        bind(...a) { stmt._bound = a; return stmt; },
        async all() {
          if (sql.includes('lessons_fts MATCH')) {
            // The worker now sends `"literal" AND "terms"` (2026-09-29): quoting is what stops `C++` and
            // `NEAR(` from being read as query *syntax*, so the simulation has to understand quotes the way
            // FTS5 does — a quoted string is literal, a doubled quote inside it is one quote, and the terms
            // are joined by AND. A stub that split on whitespace would silently stop matching anything.
            const rawMatch = String(stmt._bound?.[0] || '');
            // Real D1/FTS5 *throws* on operator characters outside a quoted string — that is exactly what
            // turned `C++ compiler` and `NEAR(` into a 502 in production. The stub refuses the same shapes
            // (only quoted literals joined by AND are accepted), so these tests can fail: without
            // `buildFtsMatch` the guard throws and the endpoint answers 502.
            // Both joiners the worker can send: `"a" AND "b"` (every term) and `"a" OR "b"` (any term).
            if (!/^"(?:[^"]|"")*"(?:(?: AND | OR )"(?:[^"]|"")*")*$/.test(rawMatch)) {
              throw new Error('fts5: syntax error near "' + rawMatch.slice(0, 24) + '"');
            }
            d1.matchQueries.push(rawMatch);
            const orJoiner = / OR /.test(rawMatch);
            const terms = rawMatch
              .toLowerCase()
              .split(/\s+(?:and|or)\s+/)
              .map(part => part.trim().replace(/^"|"$/g, '').replace(/""/g, '"'))
              .filter(Boolean);
            const domain = stmt._bound?.[1];
            const hit = (terms, text) => {
              const tokens = text.split(/[^a-z0-9]+/).filter(Boolean);
              return terms.some(t => tokens.some(tok => tok.startsWith(t) || t.startsWith(tok)));
            };
            const matched = ftsRows.filter(r => {
              const text = (r.title + ' ' + r.problem).toLowerCase();
              // FTS5 semantics: AND needs every term, OR needs any one of them.
              const ok = orJoiner ? hit(terms, text) : terms.every(t => hit([t], text));
              return ok && (!domain || r.domain === domain);
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
  return d1;
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

test('?q= with no matches returns empty results, not an error', async () => {
  const env = { MISAKANET_D1: createD1(ROWS) };
  const resp = await apiSearch('zzz nonexistent topic', env);
  assert.equal(resp.status, 200);
  const data = await resp.json();
  assert.equal(data.results.length, 0);
  // Measured live 2026-09-29: this query answered **502 internal_error**, so a search box moving to this
  // endpoint would have shown "service error" for a query that simply matched nothing. The MCP tools call
  // this state `no_match` and point at intake; the HTTP surface now says the same.
  assert.equal(data.no_match, true, JSON.stringify(data));
});

test('a query full of FTS5 syntax is a literal search, not a 502', async () => {
  // The old `safeQ` only removed quotes, so the operators stayed: measured live, `C++ compiler` and `NEAR(`
  // both answered 502. Quoting every term is what makes them literal.
  const env = { MISAKANET_D1: createD1(ROWS) };
  for (const query of ['C++ compiler', 'NEAR(', 'a-b:c*d^e', 'pip OR timeout']) {
    const resp = await apiSearch(query, env);
    assert.equal(resp.status, 200, `"${query}" -> ${resp.status}`);
    const data = await resp.json();
    assert.ok(Array.isArray(data.results), `"${query}" -> ${JSON.stringify(data).slice(0, 120)}`);
  }
});

test('buildFtsMatch quotes every term so user text stays literal', () => {
  assert.equal(buildFtsMatch('pip install timeout'), '"pip" AND "install" AND "timeout"');
  assert.equal(buildFtsMatch('C++ compiler'), '"C++" AND "compiler"');
  assert.equal(buildFtsMatch('NEAR('), '"NEAR("');
  // A bare operator is data now, not a union: "all three words" is what a user typing them means.
  assert.equal(buildFtsMatch('pip OR timeout'), '"pip" AND "OR" AND "timeout"');
  // An embedded quote is escaped the one way FTS5 defines inside a string: by doubling it.
  const dq = '"'.repeat(2);
  assert.equal(buildFtsMatch('say "hi"'), '"say" AND "' + dq + 'hi' + dq + '"');
  // Punctuation-only input has no literal to look for; the caller answers "no match" rather than erroring.
  assert.equal(buildFtsMatch('  ...  '), '');
  // Bounds: a 200-term paste cannot become an unbounded query.
  assert.equal(buildFtsMatch(Array.from({ length: 40 }, (_, i) => `t${i}`).join(' ')).split(' AND ').length, 12);
});

test('?q= without D1 binding returns a hint', async () => {
  const env = {};
  const resp = await apiSearch('pip', env);
  assert.equal(resp.status, 200);
  const data = await resp.json();
  assert.match(JSON.stringify(data), /requires the D1 service/);
});

// ── a sentence is not a conjunction (2026-09-30) ────────────────────────────────────────────────────
// Measured live: `?q=docker compose port is already allocated` answered **zero** results and `no_match`,
// because FTS5 reads a bare list of tokens as "every one of these must appear". A visitor who types a
// sentence got an empty page for a lesson that exists. The endpoint now tries the strict query first
// (precision) and, only when it finds nothing, the same terms as an OR (recall) — and says which it was,
// because "these match some of your words" is a different claim from "these match".

const SENTENCE_ROWS = [
  { id: 'docker-port-allocated', title: 'Docker compose port is already allocated', domain: 'devops',
    status: 'published', tags: ['docker'], path: 'lessons/core/docker-port.md',
    problem: 'Run docker compose up for a second project', updated: 'u', created: 'c' },
  { id: 'compose-files', title: 'Compose files drift', domain: 'devops',
    status: 'published', tags: ['docker'], path: 'lessons/core/compose-files.md',
    problem: 'Two compose files disagree', updated: 'u', created: 'c' },
];

test('a sentence query falls back to any term instead of nothing', async () => {
  const d1 = createD1(SENTENCE_ROWS);
  const env = { MISAKANET_D1: d1 };
  const resp = await apiSearch('unknown port bind address collision lookup table', env);
  assert.equal(resp.status, 200);
  const data = await resp.json();
  // `port` and `bind`/`address` appear in some rows; nothing contains all six terms.
  assert.ok(data.results.length > 0, `a sentence still matched nothing: ${JSON.stringify(data)}`);
  assert.equal(data.relaxed, true, 'the answer must say the matches are partial');
  assert.match(data.note || '', /partial|some of them|every term/i);
  // Strict first, then relaxed — the order is the contract, not an implementation detail.
  assert.equal(d1.matchQueries.length, 2, JSON.stringify(d1.matchQueries));
  assert.match(d1.matchQueries[0], / AND /, 'the first attempt must be the strict one');
  assert.match(d1.matchQueries[1], / OR /, 'the second attempt must be the relaxed one');
});

test('a query where every term matches is answered strictly, and only once', async () => {
  const d1 = createD1(SENTENCE_ROWS);
  const resp = await apiSearch('docker compose port', { MISAKANET_D1: d1 });
  const data = await resp.json();
  assert.ok(data.results.length > 0, JSON.stringify(data));
  assert.ok(!('relaxed' in data), 'a strict answer must not be labelled partial');
  assert.equal(d1.matchQueries.length, 1, `expected exactly the strict attempt: ${JSON.stringify(d1.matchQueries)}`);
});

test('when neither attempt matches, the answer is still no_match rather than relaxed', async () => {
  const d1 = createD1(SENTENCE_ROWS);
  const resp = await apiSearch('zzzz yyyy xxxx', { MISAKANET_D1: d1 });
  const data = await resp.json();
  assert.equal(data.no_match, true, JSON.stringify(data));
  assert.ok(!('relaxed' in data), 'nothing matched either attempt, so nothing is partial');
  assert.equal(data.results.length, 0);
});
