const assert = require('node:assert/strict');
const { mkdtemp, readFile, rm, writeFile, chmod } = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { test } = require('node:test');

const PACKAGE_ROOT = path.join(__dirname, '..');
const WRAPPER = path.join(PACKAGE_ROOT, 'bin', 'fatal-guard.js');
const CONVERTER = path.join(PACKAGE_ROOT, '..', '..', 'scripts', 'tombstone_to_draft.py');
const PYTHON = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');

function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { ...options, stdio: ['ignore', 'pipe', 'pipe'] });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => { stdout += chunk; });
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.once('error', reject);
    child.once('close', (code, signal) => resolve({ code, signal, stdout, stderr, pid: child.pid }));
  });
}

test('crash smoke captures a four-field tombstone and converts it to a draft', async () => {
  const tmp = await mkdtemp(path.join(os.tmpdir(), 'fatal-guard-smoke-'));
  try {
    const payloadFile = path.join(tmp, 'tombstone.json');
    const handler = path.join(tmp, 'record-handler.js');
    const markerFile = path.join(tmp, 'handler-ran.marker');
    await writeFile(handler, [
      '#!/usr/bin/env node',
      "const fs = require('node:fs');",
      `try { fs.writeFileSync(${JSON.stringify(markerFile)}, 'ran'); } catch(_) {}`,
      "let data;",
      "if (process.env.FATAL_PAYLOAD_FILE) {",
      "  try { data = fs.readFileSync(process.env.FATAL_PAYLOAD_FILE, 'utf8'); } catch(e) {",
      `    fs.writeFileSync(${JSON.stringify(markerFile)}, 'read-error: ' + e.message);`,
      "  }",
      "} else {",
      "  data = process.env.FATAL_PAYLOAD || process.argv.at(-1);",
      "}",
      "if (data) {",
      "  try { fs.writeFileSync(process.env.PAYLOAD_FILE, data); } catch(e) {",
      `    fs.writeFileSync(${JSON.stringify(markerFile)}, 'write-error: ' + e.message);`,
      "  }",
      "} else {",
      `  fs.writeFileSync(${JSON.stringify(markerFile)}, 'no-data');`,
      "}",
    ].join('\n') + '\n');
    await chmod(handler, 0o755);

    const result = await run(process.execPath, [WRAPPER, '--', process.execPath, '-e',
      "setTimeout(() => { throw new Error('smoke crash'); }, 10);"], {
      env: {
        ...process.env,
        FATAL_HANDLER: process.execPath,
        FATAL_HANDLER_ARGS: JSON.stringify([handler]),
        PAYLOAD_FILE: payloadFile,
      },
    });
    assert.equal(result.code, 1, result.stderr);

    // The handler is detached by design; poll briefly instead of sleeping a
    // fixed interval so the test remains fast on both Linux and Windows.
    const maxAttempts = 30;
    const pollInterval = 50;
    let payload;
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      try {
        payload = JSON.parse(await readFile(payloadFile, 'utf8'));
        break;
      } catch (_) {
        await new Promise((resolve) => setTimeout(resolve, pollInterval));
      }
    }
    if (!payload) {
      // Debug: check if handler ran at all
      let marker = 'not found';
      try { marker = await readFile(markerFile, 'utf8'); } catch (_) {}
      let payloadTmp = 'not found';
      try {
        payloadTmp = await readFile(path.join(os.tmpdir(), `fatal-guard-${result.pid || 'unknown'}.json`), 'utf8');
        payloadTmp = payloadTmp.slice(0, 100);
      } catch (_) {}
      assert.fail(`fatal handler did not write a payload (marker: ${marker}, payloadTmp: ${payloadTmp}, stderr: ${(result.stderr || '').slice(0, 200)})`);
    }
    for (const field of ['schemaVersion', 'reason', 'timestamp', 'pid']) {
      assert.ok(Object.hasOwn(payload, field), `missing ${field}`);
    }
    assert.equal(payload.schemaVersion, 1);
    assert.equal(payload.reason, 'process_crash');
    assert.equal(payload.exit_code, 1);

    const draft = await run(PYTHON, [CONVERTER, '--from-file', payloadFile, '--dry-run'], {
      cwd: path.join(PACKAGE_ROOT, '..', '..'),
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });
    assert.equal(draft.code, 0, draft.stderr);
    assert.match(draft.stdout, /\[DRY RUN\]/);
    assert.match(draft.stdout, /Root Cause|根因/);
  } finally {
    await rm(tmp, { recursive: true, force: true });
  }
});
