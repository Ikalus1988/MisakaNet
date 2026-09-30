// Conversion receipts on the misakanet_submit_intake re-submit channel (#1528, worker half).
//
// The rule being pinned: a reporter who re-submits the same text gets the maintainer's answer (that
// already existed for questions) *and*, once their report has become a lesson, a verifiable receipt
// naming it. The source of truth for "does this lesson cite this intake?" is
// `scripts/intake_receipt.py`, judged by `tests/intake_receipt_cases/`; `lookupIntakeConversion` is a
// faithful port, so the citation shapes exercised here are the ones that corpus actually uses.
// Run: node --test workers/intake-receipt.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, { hashString } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';
import { withKvStore } from './_test-kv-store.mjs';

const TOKEN = testToken('intake-receipt');
const GITHUB_ISSUE_42 = 'https://github.com/Ikalus1988/MisakaNet/issues/42';

// ── D1 stub: the `questions` table (answers) + the `lessons` citation prefilter ──
//
// `createQuestionD1` in intake-kind.test.mjs falls through to "return every seeded question row" for
// any SELECT it does not recognise — right for the questions lookups it was written for, hazardous for
// a conversion lookup. This stub keeps that permissive fallthrough but adds an explicit `FROM lessons`
// branch, and in `questionsOnly` mode lets the fallthrough answer a lessons query with *lesson-shaped
// rows dressed up out of the question rows*. That is what makes test 7 below bite: if the worker's
// conversion lookup ever stops saying `FROM lessons`, it reads those fabricated rows and claims a
// conversion no lesson backs.
function createIntakeD1({ questions = [], lessons = [], questionsOnly = false } = {}) {
  const qrows = questions.map((r) => ({ ...r }));
  const sqlLog = [];
  const fallthrough = () => ({
    results: questionsOnly
      ? qrows.map((r) => ({
          id: `fake-${r.issue_number}`,
          path: `lessons/fake/issue-${r.issue_number}.md`,
          title: `fake lesson for #${r.issue_number}`,
          status: 'published',
          frontmatter: JSON.stringify({
            status: 'published', evidence_level: 'E3', source: `intake-${r.issue_number}`,
          }),
        }))
      : qrows,
  });
  const selectAll = (sql, bound) => {
    const text = String(sql);
    if (text.includes('FROM questions')) {
      if (text.includes("status = 'answered'")) {
        return { results: qrows.filter((r) => r.status === 'answered') };
      }
      if (text.includes('WHERE dedup_hash = ?1')) {
        return { results: qrows.filter((r) => r.dedup_hash === bound[0]) };
      }
      return { results: qrows };
    }
    if (text.includes('FROM lessons')) {
      // Unfiltered read (`fetchLessonsFromD1`): the whole seeded corpus, so the #1526 covering-lesson
      // backstop still sees rows. Filtered read (the conversion prefilter): the LIKE superset.
      if (!text.includes('LIKE')) return { results: lessons };
      const needle = String(bound[0] || '').replace(/%/g, '');
      return { results: lessons.filter((l) => String(l.frontmatter || '').includes(needle)) };
    }
    return fallthrough();
  };
  const makeStatement = (sql, bound) => ({
    async run() {
      if (String(sql).trim().startsWith('INSERT INTO questions')) {
        qrows.push({
          issue_number: bound[0], dedup_hash: bound[1], problem: bound[2],
          source: bound[3], status: 'pending', issue_url: bound[4],
        });
      }
      return { meta: { changes: 1 } };
    },
    async all() { return selectAll(sql, bound); },
  });
  return {
    _rows: qrows,
    sqlLog,
    prepare(sql) {
      sqlLog.push(String(sql));
      return {
        bind: (...bound) => makeStatement(sql, bound),
        all: () => makeStatement(sql, []).all(),   // real D1: prepare().all() works without bind
      };
    },
  };
}

/** One D1 `lessons` row whose raw frontmatter is the only place a citation can live. */
function lessonRow({ id, path, frontmatter, title = 'seed lesson', status = 'published' }) {
  return {
    id: id || path.split('/').pop().replace(/\.md$/, ''),
    path,
    title,
    status,
    frontmatter: JSON.stringify(frontmatter),
  };
}

function createEnv(d1 = null) {
  const store = new Map();
  return {
    MCP_TOKEN: TOKEN,
    MCP_VERSION: 'intake-receipt-test',
    REGISTER_TOKEN: TOKEN,
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) { store.set(key, value); },
      async delete(key) { store.delete(key); },
      _store: store,
    },
    ...(d1 ? { MISAKANET_D1: withKvStore(d1) } : {}),
  };
}

/** Mirror the worker: `hashString(`${kind}:${safeProblem}:${safeError}`)`. */
function contentHashOf(kind, problem, error = '') {
  return hashString(`${kind}:${problem}:${error}`);
}

/** Seed the KV dedup value the first submit would have written (the issue URL). */
function seedDedup(env, kind, problem, issueUrl, error = '') {
  env.MISAKANET_KV.put(`intake_dedup:${contentHashOf(kind, problem, error)}`, issueUrl);
}

// Intercept the worker's global fetch. The GitHub issue POST is counted, so "a re-submit must not
// open a second issue" is asserted against real calls rather than against the response alone.
function captureGitHubFetch() {
  const posts = [];
  const orig = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    if (typeof url === 'string' && url.includes('/issues')) {
      posts.push(JSON.parse(opts.body));
      return new Response(JSON.stringify({ number: 42, html_url: GITHUB_ISSUE_42 }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    return orig(url, opts);
  };
  return {
    posts,
    restore() { globalThis.fetch = orig; },
  };
}

async function submitIntake(args, env) {
  const resp = await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '203.0.113.61',
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_submit_intake', arguments: args },
    }),
  }), env);
  const body = await resp.json();
  return JSON.parse(body.result.content[0].text);
}

async function submitAndCapture(args, env) {
  const gh = captureGitHubFetch();
  try {
    return { result: await submitIntake(args, env), posts: gh.posts };
  } finally {
    gh.restore();
  }
}

// ── 1 & 2: the fresh response carries the machine-readable poll contract ──

test('fresh question submit carries dedup_key + poll_hint (6h recheck)', async () => {
  const env = createEnv();
  const problem = 'How do I configure MCP auth in production?';
  const { result, posts } = await submitAndCapture({ kind: 'question', problem }, env);

  assert.equal(result.submitted, true);
  assert.equal(result.intake_id, 'issue-42');
  assert.equal(result.dedup_key, contentHashOf('question', problem));
  assert.match(result.dedup_key, /^[0-9a-f]{8}$/);
  assert.equal(result.poll_hint.tool, 'misakanet_submit_intake');
  assert.match(result.poll_hint.argument, /problem/);
  assert.match(result.poll_hint.how, /SAME problem text/);
  assert.match(result.poll_hint.how, /receipt/);
  assert.equal(result.poll_hint.recheck_after_seconds, 21600);
  // The pre-existing contract is untouched.
  assert.equal(result.follow_up.intake_id, 'issue-42');
  assert.equal(result.dedup_hash.length, 12);
  assert.equal(posts.length, 1);
});

test('fresh missing_lesson submit carries dedup_key + poll_hint (24h recheck)', async () => {
  const env = createEnv(createIntakeD1({ lessons: [] }));
  const problem = 'vertex chat completions rejects a bare model id with 404';
  const { result, posts } = await submitAndCapture({ kind: 'missing_lesson', problem }, env);

  assert.equal(result.submitted, true);
  assert.equal(result.intake_id, 'issue-42');
  assert.equal(result.status, 'pending_review');
  assert.equal(result.dedup_key, contentHashOf('missing_lesson', problem));
  assert.equal(result.poll_hint.recheck_after_seconds, 86400);
  assert.equal(result.follow_up, undefined, 'only questions get follow_up');
  assert.equal(posts.length, 1);
});

// ── 3: the conversion receipt rides on the re-submit ──

test('re-submitting an intake cited by a lesson returns converted + receipt, no second issue', async () => {
  const problem = 'vertex chat completions rejects a bare model id with 404';
  const env = createEnv(createIntakeD1({
    lessons: [lessonRow({
      id: 'vertex-gemini-model-id-naming',
      path: 'lessons/contrib/vertex-gemini-model-id-naming.md',
      title: 'Vertex AI vs Gemini model ID naming',
      frontmatter: {
        title: 'Vertex AI vs Gemini model ID naming',
        status: 'published',
        evidence_level: 'E3',
        source: 'intake #42 + #43 — bare model ID for Vertex AI',
        provenance: { source: 'intake', issue: '#42' },
      },
    })],
  }));

  const { posts } = await submitAndCapture({ kind: 'missing_lesson', problem }, env);
  const result = await submitIntake({ kind: 'missing_lesson', problem }, env);

  assert.equal(result.submitted, false);
  assert.equal(result.duplicate, true);
  assert.equal(result.converted, true);
  assert.equal(result.receipt,
    'Your report #42 became lesson vertex-gemini-model-id-naming (evidence_level E3).');
  assert.equal(result.events.length, 1);
  assert.deepEqual(result.events[0], {
    type: 'converted',
    intake: '#42',
    lesson_id: 'vertex-gemini-model-id-naming',
    lesson_path: 'lessons/contrib/vertex-gemini-model-id-naming.md',
    evidence_level: 'E3',
    search: 'python3 search_knowledge.py "vertex-gemini-model-id-naming" --lessons',
  });
  assert.equal(result.dedup_key, contentHashOf('missing_lesson', problem));
  assert.equal(result.intake_id, 'issue-42');
  assert.equal(posts.length, 1, 'a re-submit must never open a second issue');
});

// ── 4 & 5: the negative controls — no conversion may be invented ──

test('an unconverted intake is still a plain duplicate (no converted key)', async () => {
  const problem = 'some failure nobody has turned into a lesson yet';
  const env = createEnv(createIntakeD1({
    lessons: [lessonRow({
      path: 'lessons/contrib/unrelated.md',
      frontmatter: { title: 'unrelated', status: 'published', source: 'intake-9999' },
    })],
  }));

  const { posts } = await submitAndCapture({ kind: 'missing_lesson', problem }, env);
  const result = await submitIntake({ kind: 'missing_lesson', problem }, env);

  assert.equal(result.submitted, false);
  assert.equal(result.duplicate, true);
  assert.equal('converted' in result, false, 'no lesson cites this intake — nothing may be claimed');
  assert.equal(result.events, undefined);
  assert.match(result.error, /Duplicate intake/);
  assert.equal(result.dedup_key, contentHashOf('missing_lesson', problem));
  assert.equal(result.intake_id, 'issue-42');
  assert.equal(posts.length, 1);
  // The refusal has to be the matcher's, not an accident of the row never being looked at.
  assert.ok(env.MISAKANET_D1.sqlLog.some((sql) => sql.includes('FROM lessons') && sql.includes('LIKE')),
    'the conversion lookup must actually run and refuse');
});

test('a number mentioned only in the frontmatter body is NOT a citation', async () => {
  // The real artifact from `intake_receipt._cites`: a forum path containing 481940 made the first
  // matcher "find" intake #1940. The SQL prefilter happily selects this row (it does contain 1940),
  // so only the exact matcher can refuse it.
  const problem = 'a failure whose lesson only mentions a forum thread';
  const env = createEnv(createIntakeD1({
    lessons: [lessonRow({
      path: 'lessons/contrib/forum-thread.md',
      frontmatter: {
        title: 'fanuc',
        status: 'published',
        evidence_level: 'E1',
        source: 'bbs.gongkong.com/d/201302/481940',
        trigger: 'also resembles #1940 and the year 2015',
      },
    })],
  }));
  seedDedup(env, 'missing_lesson', problem, 'https://github.com/Ikalus1988/MisakaNet/issues/1940');

  const result = await submitIntake({ kind: 'missing_lesson', problem }, env);
  assert.equal(result.duplicate, true);
  assert.equal('converted' in result, false, 'a bare number inside a source URL is not a citation');
  // The LIKE prefilter *did* select this row (481940 contains 1940): what refused it is the exact
  // matcher, which is the rule `intake_receipt._cites` exists for. Without this assertion the test
  // would also pass if the prefilter never looked at the row at all.
  assert.ok(env.MISAKANET_D1.sqlLog.some((sql) => sql.includes('FROM lessons') && sql.includes('LIKE')),
    'the refusal must come from the matcher, not from the row never being selected');
});

// ── 6: every citation shape the corpus uses resolves ──

test('all four citation shapes the corpus uses resolve to a receipt', async () => {
  const shapes = [
    {
      issue: 1555, path: 'lessons/contrib/by-issue-field.md', level: 'E2',
      frontmatter: { title: 'a', status: 'published', evidence_level: 'E2', provenance: { issue: '#1555' } },
    },
    {
      issue: 1130, path: 'lessons/contrib/by-source-slug.md', level: 'E1',
      frontmatter: { title: 'b', status: 'published', evidence_level: 'E1', source: 'intake-1130 — SSE calls failed' },
    },
    {
      issue: 1200, path: 'lessons/contrib/by-long-form.md', level: 'E3',
      frontmatter: { title: 'c', status: 'published', evidence_level: 'E3', source: 'intake-issue-1200' },
    },
    {
      issue: 1569, path: 'lessons/contrib/by-repo-link.md', level: 'E3',
      frontmatter: {
        title: 'd', status: 'published', evidence_level: 'E3',
        source: 'https://github.com/Ikalus1988/MisakaNet/issues/1569',
      },
    },
  ];

  for (const shape of shapes) {
    const problem = `failure tracked as intake ${shape.issue}`;
    const env = createEnv(createIntakeD1({
      lessons: [lessonRow({ path: shape.path, frontmatter: shape.frontmatter })],
    }));
    seedDedup(env, 'missing_lesson', problem,
      `https://github.com/Ikalus1988/MisakaNet/issues/${shape.issue}`);

    const result = await submitIntake({ kind: 'missing_lesson', problem }, env);
    assert.equal(result.converted, true, `#${shape.issue} (${shape.path}) did not resolve`);
    assert.equal(result.events.length, 1);
    assert.equal(result.events[0].intake, `#${shape.issue}`);
    assert.equal(result.events[0].lesson_path, shape.path);
    assert.equal(result.events[0].evidence_level, shape.level);
    assert.equal(result.receipt,
      `Your report #${shape.issue} became lesson ${shape.path.split('/').pop().replace(/\.md$/, '')} (evidence_level ${shape.level}).`);
  }
});

// ── 7: a questions-only D1 must not manufacture a conversion ──

test('a questions-only D1 stub does not fake a conversion', async () => {
  const problem = 'How do I configure MCP server authentication for production?';
  const env = createEnv(createIntakeD1({
    questionsOnly: true,
    lessons: [],
    questions: [{
      issue_number: 1364, dedup_hash: contentHashOf('question', problem),
      problem, status: 'answered', answer: '## Answered\nRegister once per node...',
      issue_url: 'https://github.com/Ikalus1988/MisakaNet/issues/1364',
      answered_at: '2026-09-03 00:00:00',
    }],
  }));

  const result = await submitIntake({ kind: 'question', problem }, env);
  assert.equal(result.answered, true, 'the answer itself must still be delivered');
  assert.match(result.answer, /Register once per node/);
  assert.equal(result.dedup_key, contentHashOf('question', problem));
  assert.equal('converted' in result, false,
    'no `lessons` row cites this question — the answer text is not a citation');
  assert.equal(result.intake_id, 'issue-1364');
  // And the lookup really did ask the lessons table, not whatever else the stub would answer.
  assert.ok(env.MISAKANET_D1.sqlLog.some((sql) => sql.includes('FROM lessons')),
    'the conversion lookup must query lessons');
});

// ── 8: the pre-existing answer pull keeps working, now with dedup_key ──

test('re-submitting an answered question still returns the answer, now with dedup_key', async () => {
  const problem = 'How do I configure MCP server authentication for production?';
  const env = createEnv(createIntakeD1({
    questions: [{
      issue_number: 1364, dedup_hash: contentHashOf('question', problem),
      problem, status: 'answered', answer: '## Answered\nRegister once per node...',
      issue_url: 'https://github.com/Ikalus1988/MisakaNet/issues/1364',
      answered_at: '2026-09-03 00:00:00',
    }],
  }));

  const result = await submitIntake({ kind: 'question', problem }, env);
  assert.equal(result.submitted, false);
  assert.equal(result.duplicate, true);
  assert.equal(result.answered, true);
  assert.equal(result.intake_id, 'issue-1364');
  assert.match(result.answer, /Register once per node/);
  assert.equal(result.dedup_key, contentHashOf('question', problem));
  assert.equal('converted' in result, false);
});

test('a pending question re-submit carries dedup_key and the pending pointer', async () => {
  const problem = 'How should agents handle rate limits on shared runners?';
  const env = createEnv(createIntakeD1({
    questions: [{
      issue_number: 1362, dedup_hash: contentHashOf('question', problem),
      problem, status: 'pending',
      issue_url: 'https://github.com/Ikalus1988/MisakaNet/issues/1362',
    }],
  }));

  const result = await submitIntake({ kind: 'question', problem }, env);
  assert.equal(result.duplicate, true);
  assert.equal(result.pending, true);
  assert.equal(result.intake_id, 'issue-1362');
  assert.equal(result.dedup_key, contentHashOf('question', problem));
  assert.match(result.note, /pending a maintainer answer/i);
});
