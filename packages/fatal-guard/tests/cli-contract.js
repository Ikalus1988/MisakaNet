#!/usr/bin/env node
/** Contract tests for the fatal-guard CLI entry point. */

const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const path = require('node:path');

const CLI = path.join(__dirname, '..', 'bin', 'fatal-guard.js');

function run(args) {
  return spawnSync(process.execPath, [CLI, ...args], {
    encoding: 'utf8',
    env: { ...process.env, FATAL_HANDLER: '' },
    timeout: 5000,
  });
}

function check(name, fn) {
  try {
    fn();
    console.log(`  ✓ ${name}`);
  } catch (error) {
    console.error(`  ✗ ${name}: ${error.message}`);
    process.exitCode = 1;
  }
}

console.log('@misaka-net/fatal-guard — CLI contract tests');
check('--help prints usage and exits 0', () => {
  const result = run(['--help']);
  assert.equal(result.status, 0);
  assert.match(result.stdout, /Usage:/);
  assert.match(result.stdout, /--timeout/);
  assert.match(result.stdout, /Exit codes:/);
});

check('--version prints package version and exits 0', () => {
  const result = run(['--version']);
  assert.equal(result.status, 0);
  assert.match(result.stdout, /^0\.3\.0\n$/);
});

check('missing command is a usage error (2)', () => {
  const result = run([]);
  assert.equal(result.status, 2);
  assert.match(result.stderr, /missing command/);
  assert.match(result.stderr, /--help/);
});

check('unknown option is a usage error (2)', () => {
  const result = run(['--not-a-real-option', '--', process.execPath, '-e', '0']);
  assert.equal(result.status, 2);
  assert.match(result.stderr, /unknown option/);
});

check('wrapped success preserves exit code 0', () => {
  const result = run(['--', process.execPath, '-e', 'process.exit(0)']);
  assert.equal(result.status, 0);
});

check('wrapped failure preserves exit code 42', () => {
  const result = run(['--', process.execPath, '-e', 'process.exit(42)']);
  assert.equal(result.status, 42);
});

check('missing executable returns actionable error and exit 1', () => {
  const result = run(['--', 'definitely-not-a-command']);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /could not start command/);
  assert.match(result.stderr, /ENOENT/);
});

check('timeout returns exit code 3 and names the command', () => {
  const result = run([
    '--timeout', '50', '--', process.execPath, '-e', 'setTimeout(() => {}, 1000)',
  ]);
  assert.equal(result.status, 3);
  assert.match(result.stderr, /timed out after 50ms/);
});

if (process.exitCode) process.exit(1);
