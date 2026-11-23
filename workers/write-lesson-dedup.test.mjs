// A retried `misakanet_write_lesson` must not file the lesson twice (#5619).
//
// The gap this closes, measured from one client (node Misaka54052, 2026-11-22/23): three submissions
// answered `Error: Request timed out` while `search` / `register` / `preflight` were fine in the same
// session. The handler POSTs a GitHub issue through `fetchWithTimeout(..., UPSTREAM_TIMEOUT_MS)` — an
// 8 s deadline — and a timeout is exactly the case where the request *may* have created its issue. The
// client had no key to hold, and no lookup for a lesson submission (`me_inbox` covered intakes only),
// so it could either resubmit (duplicates) or not (silent loss).
//
// The fix is the intake path's own primitive, reused: a content hash, the `intake_dedup:` key, and the
// response carries `dedup_key`. `me_inbox(dedup_key=…)` then answers "what happened to it" with no new
// tool, because it already reads that namespace.
//
// Run: node --test workers/write-lesson-dedup.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = 'mcp_' + testToken('write-lesson-dedup');
const REGISTER_TOKEN = testToken('write-lesson-dedup-register');

/** Capture the GitHub issue requests instead of sending them. */
function captureIssue(startAt = 5000) {
  const calls = [];
  let next = startAt;
  const original = globalThis.fetch;
  globalThis.fetch = async (url, init = {}) => {
    const number = next++;
    calls.push({ url: String(url), body: init.body ? JSON.parse(init.body) : null, number });
    return {
      ok: true,
      status: 201,
      async json() { return { number, html_url: `https://example.invalid/issues/${number}` }; },
      async text() { return ''; },
    };
  };
  return { calls, restore: () => { globalThis.fetch = original; } };
}

function createEnv() {
  const tokenRecord = JSON.stringify({
    node_id: 'Misaka10042',
    expires: new Date(Date.now() + 86_400_000).toISOString(),
  });
  const store = new Map([[`mcp_token:${TOKEN}`, tokenRecord]]);
  return {
    REGISTER_TOKEN,
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
    _store: store,
  };
}

async function writeLesson(args, env) {
  const res = await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '198.51.100.42',
    },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_write_lesson', arguments: args } }),
  }), env);
  const body = await res.json();
  return body?.result?.structuredContent || body?.result || {};
}

const BASE = {
  title: 'pip install times out behind a proxy',
  domain: 'python',
  problem: 'pip install hangs for minutes and then fails with a read timeout.',
  root_cause: 'The corporate proxy needs an explicit index-url and a longer default timeout.',
  fix: 'Set --default-timeout and point pip at the internal mirror.',
  verification: 'Ran pip install with the flag set; the package installed in 12 seconds.',
};

/** One capture for both submissions: the point is how many issues the pair creates. */
async function submitTwice(second) {
  const env = createEnv();
  const { calls, restore } = captureIssue();
  let first;
  let again;
  try {
    first = await writeLesson(BASE, env);
    again = await writeLesson({ ...BASE, ...second }, env);
  } finally {
    restore();
  }
  return { env, calls, first, again };
}

test('the same lesson submitted twice files one issue', async () => {
  const { calls, first, again } = await submitTwice({});

  assert.equal(first.submitted, true, `the first submission must be accepted: ${JSON.stringify(first)}`);
  assert.equal(calls.filter((c) => c.url.endsWith('/issues')).length, 1,
    'a retried submission created a second issue — this is the duplication the timeout path causes');

  assert.equal(again.submitted, false, `the retry must not claim a new submission: ${JSON.stringify(again)}`);
  assert.equal(again.duplicate, true);
  assert.equal(again.issue_url, first.issue_url, 'the retry must name the original issue');
  assert.equal(again.lesson_id, first.lesson_id);
  assert.ok(again.note && again.note.includes('me_inbox'),
    `the retry must say how to check its status: ${JSON.stringify(again)}`);
});

test('every accepted submission carries a dedup_key the client can hold', async () => {
  const { first } = await submitTwice({});
  assert.match(first.dedup_key, /^[0-9a-f]{8}$/,
    `dedup_key must be the 8-char FNV-1a key me_inbox accepts: ${JSON.stringify(first)}`);
});

test('the duplicate is content-specific, not a blanket refusal', async () => {
  const { calls, again } = await submitTwice({ fix: 'Pin the wheel mirror and raise the timeout to 120 s.' });
  assert.equal(calls.filter((c) => c.url.endsWith('/issues')).length, 2,
    'a different fix is a different lesson and must file its own issue');
  assert.equal(again.submitted, true, `a changed lesson must be accepted: ${JSON.stringify(again)}`);
});

test('the verification excerpt is excluded from the key, deliberately', async () => {
  // Same reason the intake hash excludes `error` (#3930/#3932): a retry carries a longer or shorter
  // excerpt of the same check, and a key that changed with it would miss the duplicate it exists for.
  const { calls } = await submitTwice({ verification: 'pip install -q requests, 12 s' });
  assert.equal(calls.filter((c) => c.url.endsWith('/issues')).length, 1,
    'a different verification excerpt must not defeat the dedup');
});

test('a scrubbed secret does not defeat the dedup either', async () => {
  // The key is taken **after** redaction, so the same raw text retried maps to the same key even when
  // a credential was in it. Hashing before redaction would file a second issue for exactly the
  // submissions most likely to be retried (a submitter who pasted a token and was told it was scrubbed
  // has no way to know what the worker wrote instead).
  const env = createEnv();
  const { calls, restore } = captureIssue();
  const withSecret = { ...BASE, problem: `${BASE.problem} Token was ghp_${'c'.repeat(24)}.` };
  let first;
  let again;
  try {
    first = await writeLesson(withSecret, env);
    again = await writeLesson(withSecret, env);
  } finally {
    restore();
  }
  assert.equal(first.redactions_applied, true, 'the guard must scrub the token first');
  assert.equal(calls.filter((c) => c.url.endsWith('/issues')).length, 1,
    'retrying the same text filed a second issue when a secret was in it');
  assert.equal(again.duplicate, true, `the retry must dedupe: ${JSON.stringify(again)}`);
});
