const assert = require('node:assert/strict');
const { mkdtemp, writeFile, rm, chmod } = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { test } = require('node:test');
const { buildSpawnSpec } = require('../src/lib/spawn-command');

const WRAPPER = path.join(__dirname, '..', 'bin', 'fatal-guard.js');

function run(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ['ignore', 'pipe', 'pipe'] });
    let stderr = '';
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.once('error', reject);
    child.once('close', (code, signal) => resolve({ code, signal, stderr }));
  });
}

test('normal executables keep direct shell-free spawning', () => {
  const spec = buildSpawnSpec(process.execPath, ['-e', 'process.exit(0)']);
  assert.equal(spec.command, process.execPath);
  assert.deepEqual(spec.args, ['-e', 'process.exit(0)']);
  assert.deepEqual(spec.options, {});
});

test('Windows command scripts are routed through ComSpec without a shell option', async () => {
  if (process.platform !== 'win32') return;
  const tmp = await mkdtemp(path.join(os.tmpdir(), 'fatal-guard-cmd-'));
  try {
    const script = path.join(tmp, 'fail.cmd');
    await writeFile(script, '@echo off\r\nexit /b 7\r\n');
    await chmod(script, 0o755);
    const result = await run(process.execPath, [WRAPPER, '--', script]);
    assert.equal(result.code, 7, result.stderr);
  } finally {
    await rm(tmp, { recursive: true, force: true });
  }
});
