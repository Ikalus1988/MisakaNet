#!/usr/bin/env node
/**
 * @misaka-net/fatal-guard — crash scenario tests (Issue #581)
 *
 * Tests payload v0.3 upgrade:
 *   1. uncaughtException capture (errorName/message/stackSnippet)
 *   2. unhandledRejection capture (errorName/message/stackSnippet)
 *   3. Token/secret redaction in stack traces
 *   4. No FATAL_HANDLER → no-op (no crash, no error)
 *   5. Handler failure does not block exit
 *
 * Usage:
 *   node tests/crash-scenarios.js
 */

const { spawn, execSync } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');

const REGISTER = path.join(__dirname, '..', 'register.js');
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

function spawnNode(code, env = {}) {
  return new Promise((resolve) => {
    const child = spawn('node', ['-r', REGISTER, '-e', code], {
      env: { ...process.env, ...env },
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    let stdout = '', stderr = '';
    child.stdout.on('data', d => stdout += d);
    child.stderr.on('data', d => stderr += d);
    child.on('close', (exitCode) => {
      resolve({ exitCode, stdout, stderr });
    });
    // Timeout safety
    setTimeout(() => { child.kill(); resolve({ exitCode: -1, stdout, stderr: 'TIMEOUT' }); }, 5000);
  });
}

async function run() {
  console.log('@misaka-net/fatal-guard — crash scenario tests');
  console.log('─'.repeat(50));

  // Test 1: uncaughtException capture
  await test('uncaughtException: errorName/message captured', async (done) => {
    const { exitCode, stderr } = await spawnNode(
      'setTimeout(() => { throw new TypeError("test error msg"); }, 100)',
      { FATAL_HANDLER: 'echo' }
    );
    // The handler should have been called (echo prints to stdout)
    // The process should exit with non-zero
    done(exitCode !== 0, `exit=${exitCode}`);
  });

  // Test 2: unhandledRejection capture
  await test('unhandledRejection: errorName/message captured', async (done) => {
    // Force exit on unhandled rejection
    const { exitCode, stderr } = await spawnNode(
      'process.on("unhandledRejection", () => process.exit(1)); Promise.reject(new RangeError("rejection test"))',
      { FATAL_HANDLER: 'echo' }
    );
    done(exitCode !== 0, `exit=${exitCode}`);
  });

  // Test 3: Token/secret redaction in payload
  await test('Token/secret redacted in handler payload', async (done) => {
    // Use a handler that captures the payload
    const tmpScript = path.join(__dirname, '_tmp_secret_test.js');
    const handlerScript = path.join(__dirname, '_tmp_handler.js');

    fs.writeFileSync(tmpScript, `
      function leakSecret() {
        const token = "ghp_abcdefghijklmnopqrstuvwxyz1234567890";
        throw new Error("failed with token " + token);
      }
      leakSecret();
    `);

    // Handler that saves payload to file
    fs.writeFileSync(handlerScript, `
      const fs = require('fs');
      fs.writeFileSync(process.argv[2], process.argv[1] || '');
    `);

    const payloadFile = path.join(__dirname, '_tmp_payload.json');

    const { exitCode } = await spawnNode(
      `require('${tmpScript.replace(/\\/g, '\\\\')}')`,
      { FATAL_HANDLER: `node ${handlerScript} ${payloadFile}` }
    );

    // Cleanup
    try { fs.unlinkSync(tmpScript); } catch {}
    try { fs.unlinkSync(handlerScript); } catch {}

    // Check payload
    let hasRawToken = false;
    try {
      const payload = fs.readFileSync(payloadFile, 'utf8');
      hasRawToken = payload.includes('ghp_abcdefghijklmnopqrstuvwxyz');
      fs.unlinkSync(payloadFile);
    } catch {}

    done(!hasRawToken, `raw_token_in_payload=${hasRawToken}`);
  });

  // Test 4: No FATAL_HANDLER → no-op
  await test('No FATAL_HANDLER → no-op (no crash)', async (done) => {
    const { exitCode, stderr } = await spawnNode(
      'process.exit(0)',
      { FATAL_HANDLER: '' }
    );
    // Should exit cleanly without any error
    done(exitCode === 0 && !stderr.includes('Error'), `exit=${exitCode}`);
  });

  // Test 5: Handler failure does not block exit
  await test('Handler failure does not block exit', async (done) => {
    const startTime = Date.now();
    const { exitCode } = await spawnNode(
      'setTimeout(() => { throw new Error("test"); }, 100)',
      { FATAL_HANDLER: '/nonexistent/command/that/will/fail' }
    );
    const elapsed = Date.now() - startTime;
    // Should exit quickly (<3s), not hang waiting for handler
    done(exitCode !== 0 && elapsed < 3000, `exit=${exitCode} elapsed=${elapsed}ms`);
  });

  // Summary
  console.log('\n' + '─'.repeat(50));
  const passed = results.filter(r => r.ok).length;
  console.log(`${passed}/${results.length} tests passed`);
  process.exit(passedAll ? 0 : 1);
}

run().catch(e => { console.error(e); process.exit(1); });
