#!/usr/bin/env node
// Which ranking should the search box use — the page's local scorer, `/api/lessons?q=` (FTS5), or the
// MCP tool's BM25 index?
//
// WHY (2026-09-30): migration step 3 of the frontend architecture review moves the site's search onto the
// Worker. That changes what a visitor sees, so it needs a parity measurement first — and the measurement
// has to run **the page's own scorer**, not a reimplementation of it, or it would compare a copy against
// the original and call the difference drift. So this bench extracts `isSearchable` and `search` from
// `docs/search/index.html` verbatim and evaluates them; if their shape changes, this file fails instead of
// quietly measuring something else.
//
// Usage:
//   node scripts/bench_search_parity.mjs                      # the built-in query set
//   node scripts/bench_search_parity.mjs --live-queries 8     # …plus today's real searches from /api/analytics
//   node scripts/bench_search_parity.mjs --json               # machine-readable
//   node scripts/bench_search_parity.mjs --query "dco signoff" --query "pdf hyphen"
//
// Read-only: it fetches public endpoints and reads two files. No writes, no tokens.

import { readFileSync } from 'node:fs';
// The page's own scorer, extracted at build time (`python3 scripts/build_page_scorer.py`) and gated against
// `docs/search/index.html` by tests/test_page_scorer_generated.py. It is extracted rather than constructed and
// executed at run time, because that is dynamic code execution (code scanning alert #290): this keeps the
// property — the bench measures the page's scorer — without the execution.
import { makePageSearch } from './page_scorer.mjs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..');
const SITE = 'https://misakanet.org';
const UA = 'misakanet-search-parity/1.0 (+https://misakanet.org)';   // the edge 403s a bare urllib/node UA
const TOP = 5;

// The queries a visitor actually arrives with: the site's own "Try:" hints, the shapes the MCP bench
// covers, and a few that exercise the fields each side can see (bodies vs four metadata fields).
const DEFAULT_QUERIES = [
  'DCO signoff', 'github token', 'pip timeout', 'database lock', 'encoding bug',
  'pdf hyphen', 'windows sandbox', 'docker exit 137', 'rate limit', 'workflow trigger',
  'proxy ssl', 'flock single instance', 'mock attribute cascade', 'java version mismatch',
  'playwright wsl libnss3',
];

function arg(name, fallback = null) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] && !process.argv[i + 1].startsWith('--') ? process.argv[i + 1] : fallback;
}
const flag = (name) => process.argv.includes(`--${name}`);

const ids = (rows) => (rows || []).map(r => r.id).filter(Boolean);

async function fetchJson(url, init = {}) {
  const response = await fetch(url, { headers: { 'User-Agent': UA, Accept: 'application/json', ...(init.headers || {}) }, ...init });
  if (!response.ok) throw new Error(`${url} → HTTP ${response.status}`);
  return response.json();
}

async function apiSearch(query) {
  const payload = await fetchJson(`${SITE}/api/lessons?q=${encodeURIComponent(query)}&limit=${TOP}`);
  return { ids: ids(payload.results), source: payload.source, noMatch: payload.no_match === true };
}

const RATE_LIMIT = /too many requests|speed limit/i;

/** A ranking that found nothing and a caller that got throttled are different facts. */
function readRows(payload) {
  const structured = payload?.result?.structuredContent;
  const text = payload?.result?.content?.[0]?.text || '';
  if (structured?.error || RATE_LIMIT.test(text) || payload?.error) {
    return { ids: [], source: 'throttled', throttled: true,
             note: String(structured?.error || payload?.error?.message || text).slice(0, 120) };
  }
  const rows = structured?.results || structured?.lessons || [];
  return { ids: ids(rows), source: structured?.source || structured?.retriever || 'mcp',
           noMatch: structured?.no_match === true, throttled: false };
}

async function mcpSearch(query) {
  const payload = await fetchJson(`${SITE}/mcp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'MCP-Protocol-Version': '2025-06-18', Origin: SITE },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query, top: TOP, detail: 'compact' } } }),
  });
  return readRows(payload);
}

/** Set overlap, so "3 of 5" means the same lessons rather than the same count. */
const overlap = (a, b) => a.filter(id => b.includes(id)).length;

async function liveQueries(limit) {
  try {
    const payload = await fetchJson(`${SITE}/api/analytics`);
    return (payload.top_searches || []).map(r => String(r.query || '').trim()).filter(Boolean).slice(0, limit);
  } catch {
    return [];
  }
}

async function main() {
  // Whichever file the site is actually serving today: the projection from step 3 part A when it is
  // there, otherwise the corpus (the local scorer reads the same four fields from either).
  const sources = ['lessons-lite.json', 'lessons.json'];
  let lessons, corpusFile;
  for (const name of sources) {
    try {
      lessons = JSON.parse(readFileSync(join(REPO, 'docs', 'data', name), 'utf8'));
      corpusFile = `docs/data/${name}`;
      break;
    } catch { /* try the next one */ }
  }
  if (!lessons) throw new Error(`no browser corpus found (tried ${sources.join(', ')})`);
  const localSearch = makePageSearch(lessons).search;

  const explicit = process.argv.flatMap((a, i) => (a === '--query' && process.argv[i + 1] ? [process.argv[i + 1]] : []));
  const extra = explicit.length ? explicit : await liveQueries(Number(arg('live-queries', 0)) || 0);
  const queries = [...new Set([...(explicit.length ? [] : DEFAULT_QUERIES), ...extra])];

  // Three passes, not one: this worker shares ONE anti-burst window across every read entry point
  // (documented: "max 20 reads per 60s from one address … reads are unlimited, this is only a speed
  // limit"). Interleaving two endpoints per query tripped it, and the error payload then looked exactly
  // like "this ranking found nothing" — the one mistake a parity bench must not make.
  const delay = Number(arg('delay', '1.6')) * 1000;
  const pause = Number(arg('pause', '20')) * 1000;
  const local = queries.map(q => ids(localSearch(q)).slice(0, TOP));
  const api = [], mcp = [];
  const failed = (e) => ({ ids: [], source: 'error', error: e.message,
                            // 429 / "too many requests" is a *caller* problem, not an empty result set —
                            // counting it as "this ranking found nothing" is how a parity bench lies.
                            throttled: /\b429\b|too many|rate limit|speed limit/i.test(e.message) });
  for (const query of queries) {
    try { const r = await apiSearch(query); api.push({ ids: r.ids.slice(0, TOP), source: r.source, noMatch: r.noMatch }); }
    catch (e) { api.push(failed(e)); }
    await new Promise(r => setTimeout(r, delay));
  }
  if (pause) await new Promise(r => setTimeout(r, pause));
  for (const query of queries) {
    try { const r = await mcpSearch(query); mcp.push({ ids: r.ids.slice(0, TOP), source: r.source, noMatch: r.noMatch, throttled: r.throttled }); }
    catch (e) { mcp.push(failed(e)); }
    await new Promise(r => setTimeout(r, delay));
  }
  const rows = queries.map((query, i) => ({
    query, local: local[i], api: api[i].ids, mcp: mcp[i].ids,
    apiSource: api[i].source, mcpSource: mcp[i].source,
    apiNoMatch: api[i].noMatch, mcpNoMatch: mcp[i].noMatch,
    throttled: api[i].throttled || mcp[i].throttled || false,
    errored: api[i].source === 'error' || mcp[i].source === 'error',
  }));

  const answered = rows.filter(r => !r.throttled && !r.errored);
  const summary = answered.reduce((acc, r) => {
    acc.localOnly += r.local.filter(id => !r.api.includes(id) && !r.mcp.includes(id)).length;
    acc.apiOnly += r.api.filter(id => !r.local.includes(id)).length;
    acc.mcpOnly += r.mcp.filter(id => !r.local.includes(id)).length;
    acc.localApiOverlap += overlap(r.local, r.api);
    acc.localMcpOverlap += overlap(r.local, r.mcp);
    acc.apiEmpty += r.api.length === 0 ? 1 : 0;
    acc.mcpEmpty += r.mcp.length === 0 ? 1 : 0;
    acc.localEmpty += r.local.length === 0 ? 1 : 0;
    return acc;
  }, { localOnly: 0, apiOnly: 0, mcpOnly: 0, localApiOverlap: 0, localMcpOverlap: 0, apiEmpty: 0, mcpEmpty: 0, localEmpty: 0 });
  summary.throttled = rows.filter(r => r.throttled).length;
  summary.errored = rows.filter(r => r.errored && !r.throttled).length;

  if (flag('json')) {
    console.log(JSON.stringify({ queries: rows, summary, top: TOP }, null, 2));
    return;
  }

  console.log(`search parity — top ${TOP}, ${answered.length} answered queries` +
              (summary.throttled ? ` (${summary.throttled} throttled and excluded)` : '') +
              `, corpus ${lessons.length} lessons (${corpusFile})\n`);
  console.log('  query                       local  /api  /mcp   overlap(local∩api / local∩mcp)');
  for (const r of rows) {
    const ov = r.throttled || r.errored ? '—  excluded (throttled/error)'
      : `${overlap(r.local, r.api)}/${r.local.length || 0} · ${overlap(r.local, r.mcp)}/${r.local.length || 0}`;
    console.log(`  ${r.query.padEnd(26)} ${String(r.local.length).padStart(5)} ${String(r.api.length).padStart(5)} ${String(r.mcp.length).padStart(5)}   ${ov}`);
  }
  console.log('\n  totals over the top-5 of every query:');
  console.log(`    lessons only the local scorer found : ${summary.localOnly}`);
  console.log(`    lessons only /api/lessons (FTS5)    : ${summary.apiOnly}`);
  console.log(`    lessons only MCP (BM25 + fusion)    : ${summary.mcpOnly}`);
  console.log(`    queries with no local result        : ${summary.localEmpty}/${rows.length}`);
  console.log(`    queries with no /api result         : ${summary.apiEmpty}/${rows.length}`);
  console.log(`    queries with no MCP result          : ${summary.mcpEmpty}/${rows.length}`);
  console.log('\n  Read it as: "only X found it" is a recall gap on the other side, and a query where one side is');
  console.log('  empty is the case that decides what a visitor sees. Bodies are indexed on the server (since');
  console.log('  #2444/#2447) and were never available to the local scorer, so a server-only hit is expected');
  console.log('  for body-only terms — that is the improvement, not the drift.');
}

main().catch(err => { console.error(`bench_search_parity: ${err.message}`); process.exit(1); });
