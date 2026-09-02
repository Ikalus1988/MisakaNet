#!/usr/bin/env node
/**
 * Regression test for CodeQL alerts #46, #47, #48.
 *
 * Verifies that buildSpawnSpec:
 * - Routes .cmd/.bat files through ComSpec on Windows
 * - Keeps normal executables on direct spawn path (no shell)
 * - Handles paths with spaces correctly via quoteWindowsArg
 */

const { buildSpawnSpec, quoteWindowsArg } = require('../src/lib/spawn-command');

let passed = 0;
let failed = 0;

function assert(condition, msg) {
  if (condition) {
    passed++;
    console.log(`  ✓ ${msg}`);
  } else {
    failed++;
    console.error(`  ✗ ${msg}`);
    process.exitCode = 1;
  }
}

// ── quoteWindowsArg ──────────────────────────────────────────────
console.log('quoteWindowsArg:');

assert(quoteWindowsArg('simple') === 'simple', 'plain string unchanged');
assert(quoteWindowsArg('has space') === '"has space"', 'space triggers quoting');
assert(quoteWindowsArg('has"quote') === '"has^"quote"', 'double-quote caret-escaped');
assert(quoteWindowsArg('has^caret') === '"has^^caret"', 'caret caret-escaped');

// ── buildSpawnSpec — non-Windows ─────────────────────────────────
console.log('\nbuildSpawnSpec (non-Windows):');

const origPlatform = process.platform;
Object.defineProperty(process, 'platform', { value: 'linux' });

const linuxSpec = buildSpawnSpec('/usr/bin/logger', ['payload']);
assert(linuxSpec.command === '/usr/bin/logger', 'linux: command passed through');
assert(linuxSpec.args[0] === 'payload', 'linux: args passed through');
assert(JSON.stringify(linuxSpec.options) === '{}', 'linux: empty options');

Object.defineProperty(process, 'platform', { value: origPlatform });

// ── buildSpawnSpec — Windows non-script ──────────────────────────
console.log('\nbuildSpawnSpec (Windows, .exe):');

Object.defineProperty(process, 'platform', { value: 'win32' });

const winExeSpec = buildSpawnSpec('C:\\Program Files\\node\\node.exe', ['app.js']);
assert(winExeSpec.command === 'C:\\Program Files\\node\\node.exe', 'win32 .exe: direct spawn');
assert(winExeSpec.args[0] === 'app.js', 'win32 .exe: args passed through');

Object.defineProperty(process, 'platform', { value: origPlatform });

// ── buildSpawnSpec — Windows .cmd ────────────────────────────────
console.log('\nbuildSpawnSpec (Windows, .cmd):');

Object.defineProperty(process, 'platform', { value: 'win32' });
process.env.ComSpec = 'C:\\Windows\\System32\\cmd.exe';

const winCmdSpec = buildSpawnSpec('C:\\Users\\test\\handler.cmd', ['arg1']);
assert(winCmdSpec.command === 'C:\\Windows\\System32\\cmd.exe', 'win32 .cmd: routes through ComSpec');
assert(winCmdSpec.args[0] === '/d', 'win32 .cmd: first arg is /d');
assert(winCmdSpec.args[1] === '/s', 'win32 .cmd: second arg is /s');
assert(winCmdSpec.args[2] === '/c', 'win32 .cmd: third arg is /c');
assert(winCmdSpec.args[3].includes('handler.cmd'), 'win32 .cmd: command in shell string');

Object.defineProperty(process, 'platform', { value: origPlatform });

// ── buildSpawnSpec — Windows .bat with spaces ────────────────────
console.log('\nbuildSpawnSpec (Windows, .bat with spaces):');

Object.defineProperty(process, 'platform', { value: 'win32' });

const winBatSpec = buildSpawnSpec('C:\\My Tools\\run.bat', ['file with spaces.txt']);
assert(winBatSpec.command === 'C:\\Windows\\System32\\cmd.exe', 'win32 .bat with spaces: ComSpec');
assert(winBatSpec.args[3].includes('"file with spaces.txt"'), 'win32 .bat with spaces: args quoted');

Object.defineProperty(process, 'platform', { value: origPlatform });

// ── Summary ──────────────────────────────────────────────────────
console.log(`\n${passed + failed} tests, ${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
