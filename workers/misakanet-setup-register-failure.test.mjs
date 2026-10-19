// When registration fails, the installer must say *whose* problem it is.
//
// Measured 2026-10-18: `misakanet_register` answered
// `{"code":"storage_unavailable","hint":"… Retry shortly.","storage":{"token":true}}` because D1's
// daily quota was spent — and the installer told the user "匿名注册没成功（多半是网络）→ 网络恢复后
// 重跑". The network was fine. A person following that advice reboots a router while the thing that
// needs to change is a server-side budget and time.
//
// The server already names the cause, so this test pins that its `code` and `hint` reach the user
// instead of a guess, and that a genuine transport failure still reads as one.
//
// Run: node --test workers/misakanet-setup-register-failure.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { spawn } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const CLI = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'packages', 'misakanet-setup', 'bin', 'misakanet-setup.mjs');
const DEAD_ENDPOINT = 'http://127.0.0.1:9/mcp';

/** A home with one detectable assistant, so the installer proceeds to registration. */
function makeHome() {
  const home = mkdtempSync(join(tmpdir(), 'mn-regfail-'));
  mkdirSync(join(home, '.claude'), { recursive: true });
  writeFileSync(join(home, '.claude.json'), JSON.stringify({ mcpServers: {} }));
  return home;
}

function runCli(home, endpoint) {
  return new Promise((done) => {
    const child = spawn(process.execPath, [CLI, '--home', home], {
      env: { ...process.env, MISAKANET_ENDPOINT: endpoint, NO_COLOR: '1', CI: '1' },
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => { stdout += chunk; });
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.on('close', (status) => done({ status, stdout, stderr }));
  });
}

test('a server that cannot store the token is reported as the server, not the network', async () => {
  const { createServer } = await import('node:http');
  const server = createServer((req, res) => {
    let body = '';
    req.on('data', (chunk) => { body += chunk; });
    req.on('end', () => {
      const payload = JSON.parse(body || '{}');
      const result = payload.method === 'tools/list'
        ? { tools: [{ name: 'misakanet_search' }] }
        : {
            error: 'Registration storage is temporarily unavailable (token could not be saved). Retry shortly.',
            code: 'storage_unavailable',
            storage: { node: false, token: true },
            hint: 'Anonymous misakanet_search / misakanet_get_lesson still work, with no daily cap.',
          };
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ jsonrpc: '2.0', id: 1, result: {
        content: [{ type: 'text', text: JSON.stringify(result) }], structuredContent: result } }));
    });
  });
  await new Promise((ready) => server.listen(0, '127.0.0.1', ready));
  const endpoint = `http://127.0.0.1:${server.address().port}/mcp`;
  const home = makeHome();
  try {
    const out = await runCli(home, endpoint);
    const text = out.stdout + out.stderr;
    assert.match(text, /服务端暂时存不了 token/, `the cause must be named: ${text}`);
    assert.match(text, /不是你的网络/, `and it must say it is not the user's network: ${text}`);
    assert.match(text, /Anonymous misakanet_search/, 'the server hint is the actionable part');
    assert.doesNotMatch(text, /多半是网络/, 'the old guess must not be printed when the server answered');
    assert.match(text, /读课程不受影响/, 'what still works is the reason a user does not uninstall');
  } finally {
    server.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test('an unreachable endpoint still reads as a transport failure, with the reason', async () => {
  const home = makeHome();
  try {
    const out = await runCli(home, DEAD_ENDPOINT);
    const text = out.stdout + out.stderr;
    assert.match(text, /多半是网络/, `with no server answer, the transport guess is the honest one: ${text}`);
    assert.doesNotMatch(text, /服务端暂时存不了 token/, 'and it must not claim a server-side cause it never saw');
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('a server-provided retry horizon is named instead of a vague "later"', async () => {
  // The other half of the same message (issue #3511): the 2026-10-18 failure left the user with
  // "稍后重跑" while the server knew the window. When the answer carries one — `retry_after` seconds
  // in the body, the same semantics as the `Retry-After` header `docs/index.html` already reads —
  // the message must say *when*; when it does not, the vague wording is the honest one.
  const { createServer } = await import('node:http');
  const server = createServer((req, res) => {
    let body = '';
    req.on('data', (chunk) => { body += chunk; });
    req.on('end', () => {
      const payload = JSON.parse(body || '{}');
      const result = payload.method === 'tools/list'
        ? { tools: [{ name: 'misakanet_search' }] }
        : {
            error: 'Registration storage is temporarily unavailable (token could not be saved). Retry shortly.',
            code: 'storage_unavailable',
            storage: { node: false, token: true },
            hint: 'Anonymous misakanet_search / misakanet_get_lesson still work, with no daily cap.',
            retry_after: 900, // 15 minutes — the horizon the server provides
          };
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ jsonrpc: '2.0', id: 1, result: {
        content: [{ type: 'text', text: JSON.stringify(result) }], structuredContent: result } }));
    });
  });
  await new Promise((ready) => server.listen(0, '127.0.0.1', ready));
  const endpoint = `http://127.0.0.1:${server.address().port}/mcp`;
  const home = makeHome();
  try {
    const out = await runCli(home, endpoint);
    const text = out.stdout + out.stderr;
    assert.match(text, /15 分钟/, `the horizon must be named in the words a person reads a clock in: ${text}`);
    assert.match(text, /服务端给出的重试窗口/, 'and labelled as the server\'s retry window, not as a guess');
    assert.doesNotMatch(text, /稍后重跑/, 'the vague "later" must not stand when the server said how long');
    assert.match(text, /服务端暂时存不了 token/, 'the code half from #3512 is untouched: the cause is still named');
  } finally {
    server.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test('a Retry-After response header is the same horizon as the body field', async () => {
  const { createServer } = await import('node:http');
  const server = createServer((req, res) => {
    let body = '';
    req.on('data', (chunk) => { body += chunk; });
    req.on('end', () => {
      const payload = JSON.parse(body || '{}');
      const result = payload.method === 'tools/list'
        ? { tools: [{ name: 'misakanet_search' }] }
        : {
            error: 'Registration storage is temporarily unavailable (token could not be saved). Retry shortly.',
            code: 'storage_unavailable',
            storage: { node: false, token: true },
            hint: 'Anonymous misakanet_search / misakanet_get_lesson still work, with no daily cap.',
          };
      // Horizon only on the header, so the body field cannot be the sole channel.
      res.writeHead(200, { 'Content-Type': 'application/json', 'Retry-After': '300' });
      res.end(JSON.stringify({ jsonrpc: '2.0', id: 1, result: {
        content: [{ type: 'text', text: JSON.stringify(result) }], structuredContent: result } }));
    });
  });
  await new Promise((ready) => server.listen(0, '127.0.0.1', ready));
  const endpoint = `http://127.0.0.1:${server.address().port}/mcp`;
  const home = makeHome();
  try {
    const out = await runCli(home, endpoint);
    const text = out.stdout + out.stderr;
    assert.match(text, /5 分钟/, `the header's horizon must reach the message too: ${text}`);
    assert.doesNotMatch(text, /稍后重跑/, 'a header-only horizon is still a horizon');
  } finally {
    server.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test('with no horizon at all the message keeps the vague wording', async () => {
  // The conditional half of the rule: a server that did not say when must not have a wait invented
  // for it — that would be the same class of lie as "多半是网络".
  const { createServer } = await import('node:http');
  const server = createServer((req, res) => {
    let body = '';
    req.on('data', (chunk) => { body += chunk; });
    req.on('end', () => {
      const payload = JSON.parse(body || '{}');
      const result = payload.method === 'tools/list'
        ? { tools: [{ name: 'misakanet_search' }] }
        : {
            error: 'Registration storage is temporarily unavailable (token could not be saved). Retry shortly.',
            code: 'storage_unavailable',
            storage: { node: false, token: true },
            hint: 'Anonymous misakanet_search / misakanet_get_lesson still work, with no daily cap.',
          };
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ jsonrpc: '2.0', id: 1, result: {
        content: [{ type: 'text', text: JSON.stringify(result) }], structuredContent: result } }));
    });
  });
  await new Promise((ready) => server.listen(0, '127.0.0.1', ready));
  const endpoint = `http://127.0.0.1:${server.address().port}/mcp`;
  const home = makeHome();
  try {
    const out = await runCli(home, endpoint);
    const text = out.stdout + out.stderr;
    assert.match(text, /稍后重跑/, `with no horizon the vague wording is the honest one: ${text}`);
    assert.doesNotMatch(text, /重试窗口/, 'and nothing claims a window the server never sent');
  } finally {
    server.close();
    rmSync(home, { recursive: true, force: true });
  }
});
