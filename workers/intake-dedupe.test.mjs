import assert from 'node:assert/strict';
import test from 'node:test';
import worker, {
  CANONICAL_DEDUP_STOPWORDS,
  extractCanonicalTokens,
  calculateTokenSimilarity,
  scoreLessonSimilarity,
  findCanonicalDuplicate,
  recordSourceCount,
  getSourceCount,
} from './register-proxy-sw.js';

const SAMPLE_LESSONS = [
  {
    id: 'pip-install-proxy-timeout',
    title: 'pip install times out behind corporate proxy',
    summary: 'Configuring pip proxy with SSL certificates and environment variables.',
    domain: 'python',
    status: 'published',
    path: 'lessons/core/pip-install-proxy-timeout.md',
    url: 'https://misakanet.org/lessons/pip-install-proxy-timeout/',
  },
  {
    id: 'dco-signoff-failed',
    title: 'Git DCO sign-off missing from commits',
    summary: 'Resolving missing Signed-off-by in git rebase.',
    domain: 'git',
    status: 'published',
    path: 'lessons/core/dco-signoff-failed.md',
    url: 'https://misakanet.org/lessons/dco-signoff-failed/',
  },
  {
    id: 'archived-old-lesson',
    title: 'Old deprecated lesson for python 2',
    summary: 'This should never match because it is archived.',
    domain: 'python',
    status: 'archived',
    path: 'lessons/_archive/archived-old-lesson.md',
    url: 'https://misakanet.org/lessons/archived-old-lesson/',
  },
];

function createEnv(options = {}) {
  const store = new Map();
  return {
    REGISTER_TOKEN: 'gh-test-token',
    LESSONS: options.lessons || SAMPLE_LESSONS,
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) {
        store.set(key, String(value));
      },
      _store: store,
    },
  };
}

function captureGitHubFetch(onIssue) {
  const orig = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    if (typeof url === 'string' && url.includes('/issues')) {
      if (onIssue) {
        const payload = JSON.parse(opts.body);
        onIssue(payload);
      }
      return new Response(JSON.stringify({ number: 99, html_url: 'https://github.com/Ikalus1988/MisakaNet/issues/99' }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    return orig(url, opts);
  };
  return () => { globalThis.fetch = orig; };
}

function submitIntake(args, env) {
  return worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '203.0.113.88',
    },
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: 1,
      method: 'tools/call',
      params: { name: 'misakanet_submit_intake', arguments: args },
    }),
  }), env);
}

test('extractCanonicalTokens normalizes and filters stopwords', () => {
  const tokens = extractCanonicalTokens('Fatal error when pip install fails behind proxy');
  assert.ok(tokens.has('pip'));
  assert.ok(tokens.has('install'));
  assert.ok(tokens.has('proxy'));
  assert.ok(!tokens.has('fatal'));
  assert.ok(!tokens.has('error'));
  assert.ok(!tokens.has('when'));
  assert.ok(!tokens.has('fails'));
});

test('extractCanonicalTokens supports CJK sequences', () => {
  const tokens = extractCanonicalTokens('代理配置超时失败');
  assert.ok(tokens.has('代理配置超时失败'));
});

test('calculateTokenSimilarity computes Jaccard index', () => {
  const setA = new Set(['pip', 'install', 'timeout']);
  const setB = new Set(['pip', 'install', 'proxy']);
  const sim = calculateTokenSimilarity(setA, setB);
  assert.equal(sim, 2 / 3);

  assert.equal(calculateTokenSimilarity(new Set(), setB), 0);
  assert.equal(calculateTokenSimilarity(setA, null), 0);
});

test('scoreLessonSimilarity weights title match higher and ignores archived lessons', () => {
  const tokens = new Set(['pip', 'install', 'proxy']);
  const activeScore = scoreLessonSimilarity(tokens, SAMPLE_LESSONS[0]);
  assert.ok(activeScore > 0.5);

  const archivedScore = scoreLessonSimilarity(tokens, SAMPLE_LESSONS[2]);
  assert.equal(archivedScore, 0.0);
});

test('findCanonicalDuplicate returns existing lesson when similarity exceeds threshold', () => {
  const match = findCanonicalDuplicate(
    SAMPLE_LESSONS,
    'pip install timeout corporate proxy',
    'proxy connection refused'
  );
  assert.ok(match);
  assert.equal(match.id, 'pip-install-proxy-timeout');
  assert.equal(match.url, 'https://misakanet.org/lessons/pip-install-proxy-timeout/');
  assert.ok(match.sim >= 0.30);
});

test('findCanonicalDuplicate returns null when similarity is below threshold', () => {
  const match = findCanonicalDuplicate(
    SAMPLE_LESSONS,
    'kubernetes ingress cert manager renew failed',
    'cert-manager validation error'
  );
  assert.equal(match, null);
});

test('submit_intake returns already_have and prevents issue creation on near-duplicate', async () => {
  const env = createEnv();
  let issueCreated = false;
  const restore = captureGitHubFetch(() => {
    issueCreated = true;
  });

  try {
    const resp = await submitIntake({
      kind: 'missing_lesson',
      problem: 'pip install times out behind corporate proxy',
      error: 'ReadTimeoutError: HTTPSConnectionPool',
      source: 'claude-code',
    }, env);

    assert.equal(resp.status, 200);
    const body = await resp.json();
    const result = JSON.parse(body.result.content[0].text);

    assert.equal(result.submitted, false);
    assert.equal(result.duplicate, true);
    assert.ok(result.already_have);
    assert.equal(result.already_have.lesson_id, 'pip-install-proxy-timeout');
    assert.equal(result.already_have.url, 'https://misakanet.org/lessons/pip-install-proxy-timeout/');
    assert.ok(result.already_have.sim >= 0.30);
    assert.match(result.note, /already covers this topic/);
    assert.equal(issueCreated, false);

    const counts = await getSourceCount(env, 'claude-code');
    assert.equal(counts.daily, 1);
    assert.equal(counts.total, 1);
  } finally {
    restore();
  }
});

test('submit_intake creates issue and logs source count when no duplicate exists', async () => {
  const env = createEnv();
  let captured = null;
  const restore = captureGitHubFetch((payload) => {
    captured = payload;
  });

  try {
    const resp = await submitIntake({
      kind: 'missing_lesson',
      problem: 'unique redis sentinel failover split-brain during netsplit',
      error: 'READONLY You cannot write against a read only replica',
      source: 'cursor',
    }, env);

    assert.equal(resp.status, 200);
    const body = await resp.json();
    const result = JSON.parse(body.result.content[0].text);

    assert.equal(result.submitted, true);
    assert.equal(result.status, 'pending_review');
    assert.ok(captured);
    assert.match(captured.title, /unique redis sentinel failover/);

    const counts = await getSourceCount(env, 'cursor');
    assert.equal(counts.daily, 1);
    assert.equal(counts.total, 1);
  } finally {
    restore();
  }
});

test('submit_intake question kind bypasses canonical dedupe and routes to triage', async () => {
  const env = createEnv();
  let captured = null;
  const restore = captureGitHubFetch((payload) => {
    captured = payload;
  });

  try {
    const resp = await submitIntake({
      kind: 'question',
      problem: 'How do I resolve pip install timeout behind proxy?',
      source: 'dsh',
    }, env);

    assert.equal(resp.status, 200);
    const body = await resp.json();
    const result = JSON.parse(body.result.content[0].text);

    assert.equal(result.submitted, true);
    assert.equal(result.routing.kind, 'question');
    assert.ok(captured);
    assert.ok(captured.labels.includes('needs-human-review'));
  } finally {
    restore();
  }
});

test('recordSourceCount and getSourceCount correctly update counters', async () => {
  const env = createEnv();
  await recordSourceCount(env, 'test-client', 'submitted');
  await recordSourceCount(env, 'test-client', 'duplicate');
  await recordSourceCount(env, 'test-client', 'submitted');

  const counts = await getSourceCount(env, 'test-client');
  assert.equal(counts.daily, 3);
  assert.equal(counts.total, 3);
});
