/**
 * Where the crash lands — issue #3645.
 *
 * The handler is started detached with `stdio: 'ignore'`, so whatever it
 * prints never reaches the user's terminal: the payload file is the only
 * channel that survives the crash, and it has to be a conventional one an
 * agent can find.
 *
 * The same issue found two timeout budgets in one package: the CLI wrapper
 * gave a handler 1 s, the in-process path 5 s. A handler that searches the
 * network and writes a draft lesson needs seconds, not one.
 */
const assert = require('node:assert/strict');
const { mkdir, rm, writeFile } = require('node:fs/promises');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const { run, readWhenPresent, makeTmpDir } = require('./helpers');

const PACKAGE_ROOT = path.join(__dirname, '..');
const WRAPPER = path.join(PACKAGE_ROOT, 'bin', 'fatal-guard.js');
const { HANDLER_TIMEOUT_MS } = require('../src/lib/spawn-command');

test('the crash payload is written where an agent can read it', async () => {
  const tmp = await makeTmpDir('fatal-guard-crashfile-');
  try {
    const workdir = path.join(tmp, 'work');
    await mkdir(workdir);
    const result = await run(process.execPath, [WRAPPER, '--', process.execPath, '-e',
      "process.stderr.write('Error: boom\\n'); process.exit(1);"], {
      cwd: workdir,
      env: { ...process.env, FATAL_HANDLER: '' },
    });
    assert.equal(result.code, 1, result.stderr);

    const crashFile = path.join(workdir, '.misakanet', 'last-crash.json');
    const raw = await readWhenPresent(crashFile);
    assert.ok(raw, 'no crash payload file was written');
    const payload = JSON.parse(raw);
    assert.equal(payload.message, 'Error: boom');
    assert.match(result.stderr, /crash payload written to .*last-crash\.json/);
  } finally {
    await rm(tmp, { recursive: true, force: true });
  }
});

test('FATAL_CRASH_OUT redirects the crash file, and an empty value turns it off', async () => {
  const tmp = await makeTmpDir('fatal-guard-crashout-');
  try {
    const workdir = path.join(tmp, 'work');
    await mkdir(workdir);
    const target = path.join(tmp, 'elsewhere', 'crash.json');
    const result = await run(process.execPath, [WRAPPER, '--', process.execPath, '-e',
      "process.stderr.write('Error: boom\\n'); process.exit(1);"], {
      cwd: workdir,
      env: { ...process.env, FATAL_HANDLER: '', FATAL_CRASH_OUT: target },
    });
    assert.equal(result.code, 1, result.stderr);
    const raw = await readWhenPresent(target);
    assert.ok(raw, 'FATAL_CRASH_OUT was ignored');
    assert.equal(JSON.parse(raw).message, 'Error: boom');
    assert.ok(!fs.existsSync(path.join(workdir, '.misakanet')), 'the default path was written too');

    const off = await run(process.execPath, [WRAPPER, '--', process.execPath, '-e',
      "process.stderr.write('Error: boom\\n'); process.exit(1);"], {
      cwd: workdir,
      env: { ...process.env, FATAL_HANDLER: '', FATAL_CRASH_OUT: '' },
    });
    assert.equal(off.code, 1, off.stderr);
    assert.ok(!fs.existsSync(path.join(workdir, '.misakanet')), 'FATAL_CRASH_OUT="" still wrote a file');
  } finally {
    await rm(tmp, { recursive: true, force: true });
  }
});

test('one handler timeout budget, and it is not one second', () => {
  // The wrapper used 1000 ms while the in-process path used 5000 ms: the same
  // handler was cut off on Windows depending on how the program was started.
  assert.ok(HANDLER_TIMEOUT_MS >= 5000, `handler timeout is ${HANDLER_TIMEOUT_MS}ms`);
  const wrapperSource = fs.readFileSync(WRAPPER, 'utf8');
  const indexSource = fs.readFileSync(path.join(PACKAGE_ROOT, 'index.js'), 'utf8');
  for (const [name, source] of [['bin/fatal-guard.js', wrapperSource], ['index.js', indexSource]]) {
    assert.doesNotMatch(source, /HANDLER_TIMEOUT_MS\s*=\s*\d/, `${name} defines its own timeout`);
    assert.match(source, /HANDLER_TIMEOUT_MS/);
  }
});

test('a slow handler is not cut off on Windows', async (t) => {
  if (process.platform !== 'win32') {
    t.skip('the wrapper only blocks for the handler on Windows');
    return;
  }
  const tmp = await makeTmpDir('fatal-guard-slow-');
  try {
    const marker = path.join(tmp, 'done.txt');
    const handler = path.join(tmp, 'slow.js');
    await writeFile(handler, [
      '#!/usr/bin/env node',
      "setTimeout(() => require('node:fs').writeFileSync(",
      `${JSON.stringify(marker)}, 'done'), 2000);`,
    ].join('\n') + '\n');
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
    assert.ok(fs.existsSync(marker), 'the handler was killed before it finished');
  } finally {
    await rm(tmp, { recursive: true, force: true });
  }
});
