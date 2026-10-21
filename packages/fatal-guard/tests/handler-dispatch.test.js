/**
 * The in-process path reports the crash — issue #3645.
 *
 * Two things kept the preload mode (`node -r @misaka-net/fatal-guard/register`)
 * from delivering a usable payload:
 *
 *   1. the handler command was passed to the sanitizer unsplit, so the
 *      documented form `FATAL_HANDLER="node /opt/bin/handler.js"` was refused
 *      as "a shell interpreter with arguments" and the report was dropped
 *      without a word;
 *   2. one crash produced *two* reports — the uncaught exception, and the
 *      `process.exit(1)` that follows it. The second one carries no error
 *      text, and a handler that writes every payload to one file ends up
 *      holding the second one.
 */
const assert = require('node:assert/strict');
const { rm } = require('node:fs/promises');
const path = require('node:path');
const { test } = require('node:test');

const { run, readWhenPresent, writeAppendHandler, makeTmpDir } = require('./helpers');

const PACKAGE_ROOT = path.join(__dirname, '..');
const REGISTER = path.join(PACKAGE_ROOT, 'register.js');

test('the in-process path reports the crash once, and the report keeps err.message', async () => {
  const tmp = await makeTmpDir('fatal-guard-inproc-');
  try {
    const payloadFile = path.join(tmp, 'payloads.txt');
    const handler = await writeAppendHandler(tmp, 'handler.js', payloadFile);
    const result = await run(process.execPath, [
      '-r', REGISTER, '-e', "throw new Error('EACCES: permission denied, open /secret');",
    ], {
      env: {
        ...process.env,
        FATAL_HANDLER: process.execPath,
        FATAL_HANDLER_ARGS: JSON.stringify([handler]),
      },
    });
    assert.equal(result.code, 1, result.stderr);

    const raw = await readWhenPresent(payloadFile);
    assert.ok(raw, 'the handler never received a payload');
    const payloads = raw.trim().split('\n').filter(Boolean).map((line) => JSON.parse(line));
    // One crash, one report: the exit_code report that followed the
    // uncaught_exception one carried no error text and overwrote it.
    assert.equal(payloads.length, 1, `expected one payload, got ${raw}`);
    assert.equal(payloads[0].reason, 'uncaught_exception');
    assert.equal(payloads[0].message, 'EACCES: permission denied, open /secret');
    assert.equal(payloads[0].exit_code, 1);
    assert.match(payloads[0].stackSnippet, /Error: EACCES: permission denied/);
  } finally {
    await rm(tmp, { recursive: true, force: true });
  }
});

test('the in-process path dispatches a handler that carries its own arguments', async () => {
  const tmp = await makeTmpDir('fatal-guard-args-');
  try {
    const payloadFile = path.join(tmp, 'payload.json');
    const handler = await writeAppendHandler(tmp, 'handler.js', payloadFile);
    // FATAL_HANDLER="node /path/handler.js" — the documented form. Before the
    // fix the in-process path passed the whole string to the sanitizer, which
    // refused it as "a shell interpreter with arguments" and dropped the
    // report without a word.
    const result = await run(process.execPath, [
      '-r', REGISTER, '-e', "throw new Error('handler args');",
    ], {
      env: {
        ...process.env,
        FATAL_HANDLER: `${process.execPath} ${handler}`,
      },
    });
    assert.equal(result.code, 1, result.stderr);

    const raw = await readWhenPresent(payloadFile);
    assert.ok(raw, 'the handler was never dispatched');
    const payload = JSON.parse(raw.trim().split('\n')[0]);
    assert.equal(payload.reason, 'uncaught_exception');
    assert.equal(payload.message, 'handler args');
  } finally {
    await rm(tmp, { recursive: true, force: true });
  }
});
