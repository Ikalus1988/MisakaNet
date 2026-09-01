import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');

export function request(method, params = {}, id = 1) {
  return new Promise((resolve, reject) => {
    // Cross-platform: use 'python' on Windows, 'python3' on Unix-like systems
    const pythonCmd = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
    const child = spawn(pythonCmd, ['scripts/mcp_server.py'], {cwd: root});
    let output = '';
    const timer = setTimeout(() => { child.kill(); reject(new Error(`timeout waiting for ${method}`)); }, 30000);
    child.stdout.on('data', chunk => { output += chunk; });
    child.stderr.on('data', () => {});
    child.on('error', reject);
    child.on('close', () => {
      clearTimeout(timer);
      const line = output.trim().split('\n').find(candidate => candidate.trimStart().startsWith('{"jsonrpc"'));
      if (!line) return reject(new Error(`no JSON-RPC response for ${method}: ${output}`));
      try { resolve(JSON.parse(line)); } catch (error) { reject(new Error(`${error.message}: ${output}`)); }
    });
    child.stdin.end(JSON.stringify({jsonrpc: '2.0', id, method, params}) + '\n');
  });
}

export function toolResult(response) {
  const text = response?.result?.content?.find(item => item.type === 'text')?.text;
  return text ? JSON.parse(text) : response;
}
