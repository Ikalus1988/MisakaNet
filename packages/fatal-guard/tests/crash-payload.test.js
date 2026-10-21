/**
 * The crash payload carries the error text — issue #3645.
 *
 * The chain that turns a crash into a lesson starts with the payload: if the
 * payload only says "exit code: 1, signal: none", every search downstream
 * returns an unrelated lesson. The wrapper used to build `message` from the
 * generic exit string and to keep only the last four lines of stderr — which
 * drops exactly the line that names the error ("Error: EACCES: permission
 * denied").
 */
const assert = require('node:assert/strict');
const { readFile, rm, writeFile, chmod } = require('node:fs/promises');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const { run, readWhenPresent, writeAppendHandler, makeTmpDir } = require('./helpers');

const PACKAGE_ROOT = path.join(__dirname, '..');
const WRAPPER = path.join(PACKAGE_ROOT, 'bin', 'fatal-guard.js');

test('the wrapper payload carries the error text, not just the exit code', async (t) => {
  const tmp = await makeTmpDir('fatal-guard-eacces-');
  try {
    // A file the process cannot read: the crash text is a real EACCES.
    const locked = path.join(tmp, 'locked.txt');
    await writeFile(locked, 'secret\n');
    await chmod(locked, 0o000);
    let readable = true;
    try {
      fs.readFileSync(locked);
    } catch (error) {
      if (error.code !== 'EACCES') throw error;
      readable = false;
    }
    if (readable) {
      // The process can read mode-000 files (root, or Windows): no EACCES to
      // report, so there is nothing to assert here.
      t.skip('this user can read a mode-000 file — no EACCES to report');
      return;
    }

    const payloadFile = path.join(tmp, 'payload.json');
    const handler = await writeAppendHandler(tmp, 'handler.js', payloadFile);
    const result = await run(process.execPath, [WRAPPER, '--', process.execPath, '-e',
      "require('node:fs').readFileSync(process.argv[1]);", locked], {
      env: {
        ...process.env,
        FATAL_HANDLER: process.execPath,
        FATAL_HANDLER_ARGS: JSON.stringify([handler]),
        FATAL_CRASH_OUT: '',
      },
    });
    assert.equal(result.code, 1, result.stderr);

    const raw = await readWhenPresent(payloadFile);
    assert.ok(raw, 'the handler never received a payload');
    const payload = JSON.parse(raw.trim().split('\n')[0]);
    assert.equal(payload.reason, 'process_crash');
    assert.equal(payload.exit_code, 1);
    assert.match(payload.message, /EACCES: permission denied/);
    assert.doesNotMatch(payload.message, /exit code: 1, signal: none/);
    assert.match(payload.snippet, /EACCES: permission denied/);
  } finally {
    await rm(tmp, { recursive: true, force: true });
  }
});

test('the wrapper keeps the old message when stderr names no failure', async () => {
  const tmp = await makeTmpDir('fatal-guard-nofail-');
  try {
    const payloadFile = path.join(tmp, 'payload.json');
    const handler = await writeAppendHandler(tmp, 'handler.js', payloadFile);
    // "killed" counts as a crash signal for the wrapper but names no error, so
    // the payload falls back to the message it has always carried.
    const result = await run(process.execPath, [WRAPPER, '--', process.execPath, '-e',
      "process.stderr.write('killed\\n'); process.exit(1);"], {
      env: {
        ...process.env,
        FATAL_HANDLER: process.execPath,
        FATAL_HANDLER_ARGS: JSON.stringify([handler]),
        FATAL_CRASH_OUT: '',
      },
    });
    assert.equal(result.code, 1, result.stderr);

    const raw = await readWhenPresent(payloadFile);
    assert.ok(raw, 'the handler never received a payload');
    const payload = JSON.parse(raw.trim().split('\n')[0]);
    assert.equal(payload.message, 'exit code: 1, signal: none');
    assert.equal(payload.exit_code, 1);
  } finally {
    await rm(tmp, { recursive: true, force: true });
  }
});

test('the payload the handler receives is the last argv entry', async () => {
  const tmp = await makeTmpDir('fatal-guard-argv-');
  try {
    const argvFile = path.join(tmp, 'argv.json');
    const handler = path.join(tmp, 'handler.js');
    await writeFile(handler, [
      '#!/usr/bin/env node',
      "const fs = require('node:fs');",
      `fs.writeFileSync(${JSON.stringify(argvFile)}, JSON.stringify(process.argv.slice(2)));`,
    ].join('\n') + '\n');
    await chmod(handler, 0o755);

    const result = await run(process.execPath, [WRAPPER, '--', process.execPath, '-e',
      "process.stderr.write('Error: boom\\n'); process.exit(1);"], {
      env: {
        ...process.env,
        FATAL_HANDLER: process.execPath,
        FATAL_HANDLER_ARGS: JSON.stringify([handler]),
        FATAL_CRASH_OUT: '',
      },
    });
    assert.equal(result.code, 1, result.stderr);

    const raw = await readWhenPresent(argvFile);
    assert.ok(raw, 'the handler never ran');
    const argv = JSON.parse(raw);
    assert.equal(argv.length, 1, `expected only the payload in argv, got ${raw}`);
    assert.equal(JSON.parse(argv[0]).reason, 'process_crash');
  } finally {
    await rm(tmp, { recursive: true, force: true });
  }
});
