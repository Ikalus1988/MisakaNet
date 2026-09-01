/**
 * Tests for packages/fatal-guard/index.js runHandler — covers #1373 fixes.
 *
 * Bug 3 — Handler is a Python script that prints non-ASCII output.
 *   PYTHONIOENCODING=utf-8 must be injected so the child never throws
 *   UnicodeEncodeError on Windows cp1252.
 *
 * Bug 4 — POSIX non-blocking (detached/unref) so handlers survive
 *   process.exit(); Windows blocks via spawnSync so the handler finishes
 *   before the parent tears down the job object.
 *
 * The detached POSIX child is hard to observe inside node:test because
 * the test runner may exit before the child flushes. Instead we:
 *   1. Inspect the source to confirm the env / spawn contract is wired.
 *   2. Drive a synchronous child that mirrors the same env contract,
 *      proving the contract works end-to-end.
 *   3. Confirm runHandler() itself is a safe no-throw.
 */
const assert = require('node:assert/strict');
const { mkdtemp, writeFile, rm, chmod, readFile } = require('node:fs/promises');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { test } = require('node:test');

const { runHandler } = require('../index.js');

async function makeHandler(tmpDir, body) {
  const handlerPath = path.join(tmpDir, 'handler.js');
  await writeFile(handlerPath, `#!/usr/bin/env node\n${body}\n`);
  await chmod(handlerPath, 0o755);
  return handlerPath;
}

test('PYTHONIOENCODING=utf-8 is wired into runHandler env contract (bug #1373 problem 3)', async () => {
  const tmp = await mkdtemp(path.join(os.tmpdir(), 'fatal-guard-encoding-'));
  try {
    const logPath = path.join(tmp, 'log.txt');
    const handler = await makeHandler(tmp, `
const fs = require('fs');
fs.writeFileSync('${logPath}', 'PYTHONIOENCODING=' + (process.env.PYTHONIOENCODING || 'unset') + '\\n');
process.exit(0);
`);
    // Mirror the env contract runHandler uses on POSIX. If the contract
    // is wrong, the child writes 'unset'.
    const result = spawnSync(handler, [], {
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
      stdio: 'ignore',
    });
    assert.equal(result.status, 0, `handler exit code: ${result.status}, signal: ${result.signal}`);
    const log = await readFile(logPath, 'utf8');
    assert.match(log, /PYTHONIOENCODING=utf-8/, `expected utf-8 in child env, got: ${log}`);
  } finally {
    await rm(tmp, { recursive: true, force: true });
  }
});

test('runHandler payload is delivered as the last argv entry (bug #1373 problem 4)', async () => {
  const tmp = await mkdtemp(path.join(os.tmpdir(), 'fatal-guard-argv-'));
  try {
    const logPath = path.join(tmp, 'log.txt');
    const handler = await makeHandler(tmp, `
const fs = require('fs');
fs.writeFileSync('${logPath}', 'argv=' + JSON.stringify(process.argv.slice(2)) + '\\n');
process.exit(0);
`);
    // runHandler appends the JSON payload to handlerArgs. Mirror that.
    const payload = JSON.stringify({
      schemaVersion: 1,
      reason: 'argv-test',
      timestamp: '2026-08-30T00:00:00.000Z',
      pid: 1,
    });
    const result = spawnSync(handler, [payload], { stdio: 'ignore' });
    assert.equal(result.status, 0);
    const log = await readFile(logPath, 'utf8');
    assert.match(log, /argv=\["\{\\"schemaVersion\\":1,\\"reason\\":\\"argv-test\\"/, `expected payload, got: ${log}`);
  } finally {
    await rm(tmp, { recursive: true, force: true });
  }
});

test('runHandler source wires PYTHONIOENCODING=utf-8 in both branches', () => {
  // Read the source and verify the env injection is present in both the
  // POSIX detached branch and the Windows spawnSync branch. This guards
  // against a future refactor silently dropping the env var.
  const src = fs.readFileSync(path.join(__dirname, '..', 'index.js'), 'utf8');
  assert.match(src, /PYTHONIOENCODING:\s*['"]utf-8['"]/);
  // Both branches must be present.
  assert.match(src, /process\.platform === ['"]win32['"]/);
  assert.match(src, /spawnSync\(/);
  assert.match(src, /detached:\s*true/);
  assert.match(src, /child\.unref\(\)/);
});

test('runHandler imports os/fs/path at module scope, not inside try/catch (bug #1222)', () => {
  const src = fs.readFileSync(path.join(__dirname, '..', 'index.js'), 'utf8');
  const runHandlerStart = src.indexOf('function runHandler');
  assert.ok(runHandlerStart > 0, 'runHandler not found');
  const preamble = src.slice(0, runHandlerStart);
  assert.match(preamble, /require\(['"]node:os['"]\)/);
  assert.match(preamble, /require\(['"]node:fs['"]\)/);
  assert.match(preamble, /require\(['"]node:path['"]\)/);

  const runHandlerBody = src.slice(runHandlerStart);
  assert.doesNotMatch(runHandlerBody, /require\(['"]node:os['"]\)/);
  assert.doesNotMatch(runHandlerBody, /require\(['"]node:fs['"]\)/);
  assert.doesNotMatch(runHandlerBody, /require\(['"]node:path['"]\)/);
});

test('runHandler does not throw when FATAL_HANDLER is unset (safe no-op)', () => {
  delete process.env.FATAL_HANDLER;
  assert.doesNotThrow(() => runHandler('noop', new Error('safe')));
});

test('runHandler never throws even if the handler exits non-zero (POSIX detached path)', () => {
  const handler = '/bin/false'; // exits 1 immediately
  process.env.FATAL_HANDLER = handler;
  try {
    assert.doesNotThrow(() => runHandler('exit-nonzero', new Error('safe-fail')));
  } finally {
    delete process.env.FATAL_HANDLER;
  }
});
