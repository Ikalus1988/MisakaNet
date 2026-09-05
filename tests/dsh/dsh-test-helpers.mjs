import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
export const pythonCommand = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');

export function readJson(relativePath) {
  return JSON.parse(fs.readFileSync(path.join(repoRoot, relativePath), 'utf8'));
}

export function makeTempDir(prefix = 'misakanet-dsh-') {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

export async function importModule(modulePath) {
  const href = pathToFileURL(modulePath).href;
  return import(`${href}?t=${Date.now()}-${Math.random()}`);
}

export async function run(command, args, options = {}) {
  const child = spawn(command, args, {
    cwd: repoRoot,
    shell: false,
    ...options,
    env: { ...process.env, ...(options.env || {}) },
  });
  let stdout = '';
  let stderr = '';
  child.stdout?.setEncoding('utf8');
  child.stderr?.setEncoding('utf8');
  child.stdout?.on('data', (chunk) => { stdout += chunk; });
  child.stderr?.on('data', (chunk) => { stderr += chunk; });
  const [code, signal] = await once(child, 'exit');
  return { code, signal, stdout, stderr };
}

export function contentJson(response) {
  assert.equal(response?.jsonrpc, '2.0');
  const text = response?.result?.content?.[0]?.text;
  assert.equal(typeof text, 'string');
  return JSON.parse(text);
}

export function firstPublishedLessonPath() {
  for (const subdir of ['core', 'contrib']) {
    const dir = path.join(repoRoot, 'lessons', subdir);
    if (!fs.existsSync(dir)) continue;
    const file = fs.readdirSync(dir).find((name) => name.endsWith('.md'));
    if (file) return path.posix.join('lessons', subdir, file);
  }
  throw new Error('No published lesson markdown files found under lessons/core or lessons/contrib');
}

export class McpStdioClient {
  constructor() {
    this.nextId = 1;
    this.buffer = '';
    this.pending = new Map();
    this.stderr = '';
    this.child = spawn(pythonCommand, ['scripts/mcp_server.py'], {
      cwd: repoRoot,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        MISAKANET_USAGE_DISABLE_REMOTE: '1',
      },
    });

    this.child.stdout.setEncoding('utf8');
    this.child.stderr.setEncoding('utf8');
    this.child.stdout.on('data', (chunk) => this.#handleStdout(chunk));
    this.child.stderr.on('data', (chunk) => { this.stderr += chunk; });
    this.child.on('exit', (code, signal) => {
      const error = new Error(`MCP server exited before response (code=${code}, signal=${signal})\n${this.stderr}`);
      for (const { reject, timer } of this.pending.values()) {
        clearTimeout(timer);
        reject(error);
      }
      this.pending.clear();
    });
  }

  #handleStdout(chunk) {
    this.buffer += chunk;
    let newline;
    while ((newline = this.buffer.indexOf('\n')) !== -1) {
      const line = this.buffer.slice(0, newline).trim();
      this.buffer = this.buffer.slice(newline + 1);
      if (!line) continue;
      let message;
      try {
        message = JSON.parse(line);
      } catch (error) {
        continue;
      }
      const id = message.id;
      const pending = this.pending.get(id);
      if (pending) {
        clearTimeout(pending.timer);
        this.pending.delete(id);
        pending.resolve(message);
      }
    }
  }

  request(method, params = {}, timeoutMs = 5000) {
    const id = this.nextId++;
    const payload = { jsonrpc: '2.0', id, method, params };
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Timed out waiting for ${method} response. stderr:\n${this.stderr}`));
      }, timeoutMs);
      this.pending.set(id, { resolve, reject, timer });
      this.child.stdin.write(`${JSON.stringify(payload)}\n`);
    });
  }

  notify(method, params = {}) {
    this.child.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', method, params })}\n`);
  }

  async close() {
    if (this.child.exitCode !== null) return;
    this.child.stdin.end();
    const exit = once(this.child, 'exit');
    const timeout = new Promise((resolve) => setTimeout(resolve, 1000, 'timeout'));
    if ((await Promise.race([exit, timeout])) === 'timeout') this.child.kill('SIGTERM');
  }
}
