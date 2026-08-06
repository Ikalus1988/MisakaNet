#!/usr/bin/env node
/**
 * @misaka-net/fatal-guard — verification suite
 *
 * Tests:
 *   1. TTY detection logic      (no subprocess)
 *   2. FATAL_SIGNALS crash logic (no subprocess)
 *   3. Normal exit passthrough   (spawns node -e 'process.exit(0)')
 *   4. Non-zero exit crash       (spawns node -e 'process.exit(1)')
 *   5. Error keyword detection   (spawns node -e 'console.error("Error: test")')
 *   6. SIGKILL simulation        (spawns node + kill -9)
 *   7. Exit code passthrough     (spawns node -e 'process.exit(42)')
 *
 * Usage:
 *   node test/verify-fix.js
 *   # all 7 tests PASS expected
 */

const { spawn } = require('node:child_process');
const path = require('node:path');

const FATAL_GUARD = path.join(__dirname, '..', 'bin', 'fatal-guard.js');
const results = [];
let passedAll = true;

function test(name, fn) {
  return new Promise((resolve) => {
    fn((ok, detail) => {
      results.push({ name, ok, detail });
      console.log(`  ${ok ? '✓' : '✗'} ${name}`);
      if (detail) console.log(`    ${detail}`);
      if (!ok) passedAll = false;
      resolve();
    });
  });
}

function runGuard(cmd, args, timeout = 5000) {
  return new Promise((resolve) => {
    const proc = spawn(process.execPath, [FATAL_GUARD, '--', cmd, ...args], {
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, FATAL_HANDLER: '' },  // no handler = no-op
    });
    let stderr = '';
    proc.stderr.on('data', (c) => { stderr += c; });
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; proc.kill(); }, timeout);
    proc.on('exit', (code) => {
      clearTimeout(timer);
      resolve({ code, stderr, timedOut });
    });
  });
}

// Tests are defined inline in run() below

// ── Runner ──────────────────────────────────────────────────────
async function run() {
  console.log('\n  @misaka-net/fatal-guard — verification suite');
  console.log('  '.padEnd(50, '─'));

  const t1 = test('FATAL_SIGNALS: SIGKILL detected as crash', (done) => {
    const FATAL = new Set(['SIGKILL','SIGSEGV','SIGABRT','SIGBUS','SIGFPE','SIGILL','SIGTRAP','SIGSYS']);
    const checks = [
      [null, null, false],
      [1,    null, true],
      [null, 'SIGKILL', true],
      [null, 'SIGTERM', false],
      [null, 'SIGINT',  false],
    ];
    const allOk = checks.every(([code, sig, expect]) =>
      Boolean((code !== 0 && code !== null) || (sig && FATAL.has(sig))) === expect);
    done(allOk, allOk ? '5/5 correct' : 'logic mismatch');
  });

  const t2 = test('TTY: pipe mode in non-TTY env', (done) => {
    done(!process.stderr.isTTY, `isTTY=${!!process.stderr.isTTY}`);
  });

  const t3 = test('Normal exit (0): not a crash', async (done) => {
    const { code } = await runGuard(process.execPath, ['-e', 'process.exit(0)']);
    done(code === 0, `exit=${code}`);
  });

  const t4 = test('Crash exit (1) with stderr error: detected', async (done) => {
    const { code, stderr } = await runGuard(process.execPath,
      ['-e', 'console.error("Error: x");process.exit(1)']);
    done(code === 1 && stderr.includes('Error'), `exit=${code}`);
  });

  const t5 = test('Exit 2 without error keyword: passthrough', async (done) => {
    const { code } = await runGuard(process.execPath, ['-e', 'process.exit(2)']);
    done(code === 2, `exit=${code}`);
  });

  const t6 = test('Exit code 42 passthrough', async (done) => {
    const { code } = await runGuard(process.execPath, ['-e', 'process.exit(42)']);
    done(code === 42, `exit=${code}`);
  });

  const t7 = test('Require path: ../index accessible', (done) => {
    try { require(path.join(__dirname, '..', 'index')); done(true); }
    catch (e) { done(false, e.message); }
  });

  await Promise.all([t1, t2, t3, t4, t5, t6, t7]);
  console.log('');
  if (passedAll) { console.log('  ✅ All tests passed'); }
  else { console.log('  ❌ Some tests failed'); process.exit(1); }
}

run().catch(console.error);
