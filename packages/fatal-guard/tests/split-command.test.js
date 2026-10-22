/**
 * splitCommand — the handler command tokenizer.
 *
 * `FATAL_HANDLER` is a program, optionally followed by arguments. The
 * tokenizer has to survive the two shapes that break silently:
 *
 *   - a program path with spaces ("C:\Program Files\nodejs\node.exe" is the
 *     ordinary Windows node path, and splitting it produced a program that
 *     does not exist — no error, no report, nothing),
 *   - a quoted path, which is one token by definition.
 *
 * The tokenizer never loosens `sanitizeCommand`: a program that is not an
 * existing file is never merged with its arguments, and whatever comes out
 * is still handed to the sanitizer.
 */
const assert = require('node:assert/strict');
const { mkdtemp, mkdir, rm, writeFile } = require('node:fs/promises');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { test } = require('node:test');

const { splitCommand, sanitizeCommand } = require('../src/lib/spawn-command');

/** Run `fn` with process.platform forced to `value`. */
function withPlatform(value, fn) {
  const original = process.platform;
  Object.defineProperty(process, 'platform', { value });
  try {
    return fn();
  } finally {
    Object.defineProperty(process, 'platform', { value: original });
  }
}

test('a program path with spaces stays one token', async () => {
  const tmp = await mkdtemp(path.join(os.tmpdir(), 'fatal-guard-split-'));
  try {
    const dir = path.join(tmp, 'handler dir');
    await mkdir(dir);
    const program = path.join(dir, 'handler');
    await writeFile(program, '#!/bin/sh\nexit 0\n');

    assert.deepEqual(splitCommand(program), [program]);
    // …and with arguments behind it.
    assert.deepEqual(splitCommand(`${program} --flag`), [program, '--flag']);
  } finally {
    await rm(tmp, { recursive: true, force: true });
  }
});

test('a quoted path is one token', async () => {
  const tmp = await mkdtemp(path.join(os.tmpdir(), 'fatal-guard-quote-'));
  try {
    const dir = path.join(tmp, 'handler dir');
    await mkdir(dir);
    const program = path.join(dir, 'handler');
    await writeFile(program, '#!/bin/sh\nexit 0\n');

    assert.deepEqual(splitCommand(`"${program}"`), [program]);
    assert.deepEqual(splitCommand(`"${program}" --flag`), [program, '--flag']);
  } finally {
    await rm(tmp, { recursive: true, force: true });
  }
});

test('the Windows tokenizer keeps a Windows path with spaces intact', () => {
  // The Windows rule of the tokenizer is that a backslash is a path separator,
  // not an escape character. That is a property of the tokenizer alone, so it
  // is asserted without a filesystem: the path below does not have to exist,
  // and must not be needed — on Windows a path like it cannot even be created
  // here, because its separators would have to be real directories.
  //
  // How many tokens come out depends on the machine: where the path exists,
  // the merge joins it back into one program; where it does not, the tokens
  // still have to reconstruct it. What must never happen is the path being
  // cut — a token boundary inside it would send a program that does not exist
  // to the spawn.
  const name = ['C:', 'Program Files', 'nodejs', 'node.exe'].join('\\');
  const parts = withPlatform('win32', () => splitCommand(name));
  assert.equal(
    parts.join(' '),
    name,
    `the path was cut: ${JSON.stringify(parts)}`,
  );
  if (fs.existsSync(name)) {
    // A Windows machine that has node installed there — most of them — has a
    // path that really exists, and then it must be one program.
    assert.deepEqual(
      parts,
      [name],
      'a path that exists must be one program, not two tokens',
    );
  }
});

test('a command that names no file is still split on whitespace', () => {
  // The merge only ever joins tokens into a path that exists, so a program
  // that lives on PATH keeps its arguments.
  assert.deepEqual(splitCommand('node /nonexistent/dir/handler.js'),
    ['node', '/nonexistent/dir/handler.js']);
  assert.deepEqual(splitCommand('logger --tag crash'), ['logger', '--tag', 'crash']);
});

test('the sanitizer still refuses a shell interpreter with arguments', () => {
  // The tokenizer splits "node -e evil" into three tokens, so the program is
  // "node" — but a *quoted* whole command stays one token, and that token is
  // still handed to the sanitizer, which refuses it. This is the injection
  // defence, and it is not loosened here.
  assert.equal(sanitizeCommand('node -e evil'), null);
  const quoted = splitCommand('"node -e evil"');
  assert.deepEqual(quoted, ['node -e evil']);
  assert.equal(sanitizeCommand(quoted[0]), null);
  // A quoted *path* with spaces is not a shell interpreter and is accepted.
  assert.equal(sanitizeCommand('C:\\Program Files\\nodejs\\node.exe'),
    'C:\\Program Files\\nodejs\\node.exe');
});
