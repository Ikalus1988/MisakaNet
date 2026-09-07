// #1526 tests: canonical "already have lesson" gate (server backstop).
// Run: node --test workers/intake-canonical.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { findCoveringLesson } from './register-proxy-sw.js';

const LESSONS = [
  { id: 'pip-install-proxy-timeout', title: 'pip install timeout behind corporate proxy', domain: 'devops',
    tags: ['pip', 'proxy', 'timeout'],
    description: '## Problem pip install ReadTimeoutError behind corporate proxy ## Solution fix cert & timeout config' },
  { id: 'git-credential-helper-gh-path-mismatch', title: 'git credential helper gh path mismatch github 401', domain: 'git',
    tags: ['git', 'github', 'credential'], description: '## Problem git credential lookup fails ## Solution fix helper path' },
  { id: 'python-venv-tiktoken', title: 'python venv tiktoken module not found', domain: 'python',
    tags: ['python', 'venv'], description: '## Problem ModuleNotFoundError tiktoken wrong venv ## Solution activate venv' },
];

test('near-verbatim failure covered by lesson → returns lesson', () => {
  const r = findCoveringLesson(
    'pip install times out behind corporate proxy ReadTimeoutError',
    'ReadTimeoutError while reading from pypi', LESSONS);
  assert.ok(r, 'expected a covering lesson');
  assert.equal(r.lesson.id, 'pip-install-proxy-timeout');
  assert.ok(r.ratio >= 0.5);
});

test('different stack / generic words do not match', () => {
  const r = findCoveringLesson(
    'error[E0308] mismatched types borrow checker rust cargo',
    'cargo build failed', LESSONS);
  assert.equal(r, null, 'cross-language must not be suppressed');
});

test('too few real tokens → no suppression (fall through to issue)', () => {
  assert.equal(findCoveringLesson('it broke', '', LESSONS), null);
  assert.equal(findCoveringLesson('error not found', '', LESSONS), null);
});

test('unrelated but wordy failure not suppressed', () => {
  const r = findCoveringLesson('terraform state lock backend initialization failed', 'tfstate locked', LESSONS);
  assert.equal(r, null);
});

test('empty lessons list → null', () => {
  assert.equal(findCoveringLesson('pip proxy timeout', 'ReadTimeoutError', []), null);
});
