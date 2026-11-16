// The two fields that separate a lesson from a story (2026-11-16).
//
// `lessons/TEMPLATE.md` already requires `trigger:` (the error fragment a future search would use) and
// `verify:` (a checkable pass/fail) of every NEW lesson — #1783. The intake path satisfied both by
// *synthesis*: `intake_lesson_to_file.trigger_of()` builds a trigger out of `title + problem`, so a
// project-specific story with no transferable hook passed the screen (measured 2026-11-16: the same
// content scored 58/100 and landed in `needs-human-review`). This file pins the check that now happens
// at submission, where the person who hit the failure can still answer it.
//
// Run: node --test workers/intake-trigger-gate.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('intake-trigger');

function createEnv() {
  const store = new Map();
  return {
    MCP_TOKEN: TOKEN,
    MCP_VERSION: 'intake-trigger-test',
    REGISTER_TOKEN: TOKEN,
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) { store.set(key, value); },
      _store: store,
    },
  };
}

function captureGitHubFetch(onIssue) {
  const orig = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    if (typeof url === 'string' && url.includes('/issues')) {
      onIssue(JSON.parse(opts.body));
      return new Response(JSON.stringify({ number: 77, html_url: 'https://github.com/x/issues/77' }), {
        status: 201, headers: { 'Content-Type': 'application/json' },
      });
    }
    return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } });
  };
  return () => { globalThis.fetch = orig; };
}

let ipCounter = 0;
function submitIntake(args, env) {
  ipCounter += 1;
  return worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      // One IP per call: the intake budget is 10/hour per address, and a refusal here would look
      // like the gate firing.
      'CF-Connecting-IP': `198.51.100.${ipCounter % 250}`,
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_submit_intake', arguments: args },
    }),
  }), env);
}

async function call(args, env) {
  const response = await submitIntake(args, env);
  const body = await response.json();
  return JSON.parse(body.result.content[0].text);
}

const LESSON_SHAPED = `M9 push rejected

## Root Cause
The M9 project protects main and the account is a Developer, so clone works and push does not.

## Fix
Ask the maintainer to raise the role.`;

test('a lesson-shaped submission without a trigger is not filed, and says what is missing', async () => {
  const env = createEnv();
  let captured = null;
  const restore = captureGitHubFetch((payload) => { captured = payload; });
  try {
    const result = await call({ kind: 'missing_lesson', problem: LESSON_SHAPED, source: 'codex' }, env);
    assert.equal(result.submitted, false, JSON.stringify(result));
    assert.deepEqual(result.missing, ['trigger', 'verification']);
    assert.match(result.error, /trigger/);
    assert.match(result.hint, /future search would use/);
    assert.match(result.note, /no dedup entry/, 'a corrected retry must not be treated as a duplicate');
    assert.equal(captured, null, 'nothing may reach GitHub when the submission is refused');
  } finally {
    restore();
  }
});

test('a short trigger is treated as missing, because a keyword fragment is not the title again', async () => {
  const env = createEnv();
  const restore = captureGitHubFetch(() => {});
  try {
    const result = await call({
      kind: 'missing_lesson',
      problem: LESSON_SHAPED,
      trigger: 'M9 push',
      verification: 'ran the push again and it worked',
    }, env);
    assert.equal(result.submitted, false);
    assert.deepEqual(result.missing, ['trigger']);
  } finally {
    restore();
  }
});

test('the required pair lets the same submission through, and the trigger reaches the issue body', async () => {
  const env = createEnv();
  let captured = null;
  const restore = captureGitHubFetch((payload) => { captured = payload; });
  try {
    const result = await call({
      kind: 'missing_lesson',
      problem: LESSON_SHAPED,
      trigger: 'git push denied but clone works protected branch role',
      verification: 're-run `git push origin HEAD`: it creates the commit instead of 403',
      source: 'codex',
    }, env);
    assert.equal(result.submitted, true, JSON.stringify(result));
    assert.ok(captured, 'the issue was created');
    assert.match(captured.body, /## Trigger\n/);
    assert.match(captured.body, /git push denied but clone works protected branch role/);
    assert.match(captured.body, /## Verification/);
  } finally {
    restore();
  }
});

test('a question is never asked for a trigger — its exit is an answer, not a lesson', async () => {
  const env = createEnv();
  const restore = captureGitHubFetch(() => {});
  try {
    const result = await call({
      kind: 'question',
      problem: 'How do I configure MCP auth in production? It fails with a handshake error when I set a bearer token.',
    }, env);
    assert.equal(result.submitted, true, JSON.stringify(result));
  } finally {
    restore();
  }
});

test('a partial report with no root cause is still welcome', async () => {
  const env = createEnv();
  const restore = captureGitHubFetch(() => {});
  try {
    const result = await call({
      kind: 'missing_lesson',
      problem: 'pip install times out behind the corporate proxy and I have not found the cause yet.',
      source: 'claude-code',
    }, env);
    assert.equal(result.submitted, true, 'a report the submitter cannot explain is still a filing');
  } finally {
    restore();
  }
});

test('a `fix` argument makes it lesson-shaped even without headings in problem', async () => {
  const env = createEnv();
  const restore = captureGitHubFetch(() => {});
  try {
    const result = await call({
      kind: 'new_lesson_candidate',
      problem: 'push rejected by the remote',
      fix: 'raise the account role in the project settings',
    }, env);
    assert.equal(result.submitted, false);
    assert.deepEqual(result.missing, ['trigger', 'verification']);
  } finally {
    restore();
  }
});
