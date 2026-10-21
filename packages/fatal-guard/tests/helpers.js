/**
 * Shared helpers for the fatal-guard test files.
 *
 * The handler contract: the payload is the **last** argv entry, and the
 * handler runs detached — so a test that wants to see the payload has to
 * poll for the file the handler writes.
 */
const { mkdtemp, readFile, writeFile, chmod } = require('node:fs/promises');
const { spawn } = require('node:child_process');
const os = require('node:os');
const path = require('node:path');

function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { ...options, stdio: ['ignore', 'pipe', 'pipe'] });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => { stdout += chunk; });
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.once('error', reject);
    child.once('close', (code, signal) => resolve({ code, signal, stdout, stderr }));
  });
}

/** Poll until the file exists and is readable, or give up. */
async function readWhenPresent(file, attempts = 40, intervalMs = 50) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      return await readFile(file, 'utf8');
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
      await new Promise((resolve) => setTimeout(resolve, intervalMs));
    }
  }
  return null;
}

/** A handler that appends every payload it receives to `outFile`. */
async function writeAppendHandler(dir, name, outFile) {
  const handler = path.join(dir, name);
  await writeFile(handler, [
    '#!/usr/bin/env node',
    "const fs = require('node:fs');",
    `fs.appendFileSync(${JSON.stringify(outFile)}, String(process.argv.at(-1)) + '\\n');`,
  ].join('\n') + '\n');
  await chmod(handler, 0o755);
  return handler;
}

async function makeTmpDir(prefix) {
  return mkdtemp(path.join(os.tmpdir(), prefix));
}

module.exports = { run, readWhenPresent, writeAppendHandler, makeTmpDir };
