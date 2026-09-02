/**
 * Tests for sanitizeCommand — the security gate that rejects shell
 * metacharacters / shell interpreters in env-derived handler commands
 * (CodeQL js/shell-command-injection-from-environment, 2026-08-31).
 */
const assert = require('node:assert/strict');
const { test } = require('node:test');

const { sanitizeCommand, buildSpawnSpec } = require('../src/lib/spawn-command');

test('legal commands pass through unchanged', () => {
  assert.equal(sanitizeCommand('/usr/bin/logger'), '/usr/bin/logger');
  assert.equal(sanitizeCommand('python3'), 'python3');
  assert.equal(sanitizeCommand('node'), 'node'); // args come via FATAL_HANDLER_ARGS
  assert.equal(sanitizeCommand('/opt/alert-to-slack.sh'), '/opt/alert-to-slack.sh');
  assert.equal(sanitizeCommand('/usr/bin/curl'), '/usr/bin/curl');
  // Windows paths with spaces are fine (not a shell interpreter)
  assert.equal(sanitizeCommand('C:\\Program Files\\node\\node.exe'), 'C:\\Program Files\\node\\node.exe');
  assert.equal(sanitizeCommand('C:\\Users\\test\\handler.cmd'), 'C:\\Users\\test\\handler.cmd');
});

test('shell metacharacters are rejected', () => {
  assert.equal(sanitizeCommand('echo; rm -rf /'), null);
  assert.equal(sanitizeCommand('$(curl evil)'), null);
  assert.equal(sanitizeCommand('a|b'), null);
  assert.equal(sanitizeCommand('a&&b'), null);
  assert.equal(sanitizeCommand('a>b'), null);
  assert.equal(sanitizeCommand('a`b`'), null);
});

test('shell interpreters with arguments are rejected', () => {
  // `cmd /c evil`, `sh -c evil` etc. would execute arbitrary commands even
  // with no metacharacters — they must be refused.
  assert.equal(sanitizeCommand('cmd /c evil'), null);
  assert.equal(sanitizeCommand('cmd.exe /c evil'), null);
  assert.equal(sanitizeCommand('sh -c evil'), null);
  assert.equal(sanitizeCommand('bash -c evil'), null);
  assert.equal(sanitizeCommand('zsh -c evil'), null);
  assert.equal(sanitizeCommand('powershell -Command evil'), null);
  assert.equal(sanitizeCommand('pwsh -Command evil'), null);
  assert.equal(sanitizeCommand('node -e evil'), null);
  assert.equal(sanitizeCommand('python3 -c evil'), null);
  assert.equal(sanitizeCommand('perl -e evil'), null);
  assert.equal(sanitizeCommand('ruby -e evil'), null);
});

test('option injection and whitespace tricks rejected', () => {
  assert.equal(sanitizeCommand('-n'), null);
  assert.equal(sanitizeCommand('  /usr/bin/logger  '), null);
  assert.equal(sanitizeCommand(''), null);
  assert.equal(sanitizeCommand('   '), null);
});

test('buildSpawnSpec marks rejected commands', () => {
  const spec = buildSpawnSpec('echo; rm -rf /', ['x']);
  assert.equal(spec.rejected, true);
  assert.equal(spec.command, '');
  assert.deepEqual(spec.args, []);
});

test('buildSpawnSpec still routes .cmd through ComSpec when safe', () => {
  const origPlatform = process.platform;
  Object.defineProperty(process, 'platform', { value: 'win32' });
  try {
    process.env.ComSpec = 'C:\\Windows\\System32\\cmd.exe';
    const spec = buildSpawnSpec('C:\\Users\\test\\handler.cmd', ['arg1']);
    assert.equal(spec.rejected, undefined);
    assert.equal(spec.command, 'C:\\Windows\\System32\\cmd.exe');
    assert.equal(spec.args[2], '/c');
    assert.ok(spec.args[3].includes('handler.cmd'));
  } finally {
    Object.defineProperty(process, 'platform', { value: origPlatform });
  }
});
