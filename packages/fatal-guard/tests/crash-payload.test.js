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

test('the payload is the last argv entry on the Windows branch too', async () => {
  // The wrapper's win32 branch used to deliver the payload through the
  // environment only, so on Windows a handler that reads `process.argv.at(-1)`
  // — the documented contract — saw its own path instead of the payload.
  // That is a platform-dependent contract, and it cost the Windows CI legs
  // of PR #3647.
  //
  // The win32 branch is exercised here on every platform: the wrapper is run
  // with process.platform forced to win32, so the branch that CI runs on
  // Windows is the branch this test runs on Linux.
  const tmp = await makeTmpDir('fatal-guard-win32-');
  try {
    const preload = path.join(tmp, 'force-win32.js');
    await writeFile(preload,
      "Object.defineProperty(process, 'platform', { value: 'win32' });\n");
    const argvFile = path.join(tmp, 'argv.json');
    const handler = path.join(tmp, 'handler.js');
    await writeFile(handler, [
      '#!/usr/bin/env node',
      "const fs = require('node:fs');",
      `fs.writeFileSync(${JSON.stringify(argvFile)}, JSON.stringify(process.argv.slice(2)));`,
    ].join('\n') + '\n');
    await chmod(handler, 0o755);

    const result = await run(process.execPath, ['--require', preload, WRAPPER, '--',
      process.execPath, '-e', "process.stderr.write('Error: boom\\n'); process.exit(1);"], {
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

test('a handler whose program path contains a space is dispatched', async (t) => {
  // "C:\Program Files\nodejs\node.exe" is the ordinary Windows node path,
  // and the tokenizer used to cut it in half — a program that does not
  // exist, so the handler never ran and nothing said why.
  const tmp = await makeTmpDir('fatal-guard-spaced-');
  try {
    // The copy keeps the original's extension. Windows resolves a program name
    // without an extension by appending ".exe" (libuv does it, and so does
    // CreateProcess), so "node copy" would be looked for as "node copy.exe" —
    // a spawn error with no useful message. The extension is part of the
    // program's name on Windows, not decoration.
    const spaced = path.join(tmp, `node copy${path.extname(process.execPath)}`);
    let linked = false;
    for (const method of ['linkSync', 'symlinkSync']) {
      try {
        fs[method](process.execPath, spaced);
        linked = true;
        break;
      } catch (_) { /* try the next way */ }
    }
    if (!linked) {
      // No hard link (a different volume) and no symlink (Windows wants a
      // privilege for that). A copy always works; it costs a node binary.
      try {
        fs.copyFileSync(process.execPath, spaced);
        linked = true;
      } catch (_) { /* the filesystem refuses both */ }
    }
    if (!linked) {
      t.skip('this filesystem cannot provide a second copy of the node executable');
      return;
    }

    const payloadFile = path.join(tmp, 'payload.json');
    const handler = path.join(tmp, 'handler.js');
    await writeFile(handler, [
      '#!/usr/bin/env node',
      "const fs = require('node:fs');",
      `fs.writeFileSync(${JSON.stringify(payloadFile)}, String(process.argv.at(-1)));`,
    ].join('\n') + '\n');
    await chmod(handler, 0o755);

    const result = await run(process.execPath, [WRAPPER, '--', process.execPath, '-e',
      "process.stderr.write('Error: boom\\n'); process.exit(1);"], {
      env: {
        ...process.env,
        // The program path has a space and is not quoted: it has to survive
        // the tokenizer on its own.
        FATAL_HANDLER: `${spaced} ${handler}`,
        FATAL_CRASH_OUT: '',
      },
    });
    assert.equal(result.code, 1, result.stderr);

    const raw = await readWhenPresent(payloadFile);
    assert.ok(raw, 'the handler was never dispatched');
    assert.equal(JSON.parse(raw).reason, 'process_crash');
  } finally {
    await rm(tmp, { recursive: true, force: true });
  }
});

test('the test suite uses the real node executable, not a hard-coded one', () => {
  // A hand-written node path in a test is how the "path with spaces" trap
  // comes back: the fake path has no space, so the test passes and the
  // developer's machine breaks.
  const testsDir = __dirname;
  for (const file of fs.readdirSync(testsDir).filter((name) => name.endsWith('.test.js'))) {
    const source = fs.readFileSync(path.join(testsDir, file), 'utf8');
    assert.doesNotMatch(source, /[A-Za-z]:[\\/][^\s'"]*[\\/]node(?:\.exe)?/,
      `${file} hard-codes a Windows node path`);
    assert.doesNotMatch(source, /['"]\/usr\/(?:local\/)?bin\/node['"]/,
      `${file} hard-codes a POSIX node path`);
  }
});
