// Tests for @misaka-net/misakanet-setup (the npx installer).
//
// Why this exists: the audience cannot debug anything, so a broken installer is
// indistinguishable from "the product does nothing". Everything runs against a temporary
// HOME - never the developer's real agent config - and the network is stubbed out by
// pointing MISAKANET_ENDPOINT at a dead port, so a run offline is the *tested* default.
//
// Lives in workers/ because that is the glob CI runs (mcp-stress.yml).
import assert from 'node:assert/strict';
import test from 'node:test';
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync, readdirSync, chmodSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { testToken } from './_test-token.mjs';

const CLI = resolve(import.meta.dirname, '..', 'packages', 'misakanet-setup', 'bin', 'misakanet-setup.mjs');
// Synthetic, per-run: a literal that looks like a credential is indistinguishable from one
// to a scanner (HARDCODED_SECRET #261), and workers/_test-token.mjs exists for that reason.
const STUB_TOKEN = testToken('setup');
const FILE_TOKEN = testToken('file');
const EXPORTED_TOKEN = testToken('exported');
// The CLI validates the shape before persisting (mcp_ + >=20 chars), so the stub must
// answer like the real server does.
const TOKEN_SHAPE_OK = `mcp_${testToken('node')}`;
const OFFLINE = 'http://127.0.0.1:9/mcp';

function makeHome({ codex = true, claude = true } = {}) {
  const home = mkdtempSync(join(tmpdir(), 'mn-setup-'));
  if (claude) {
    mkdirSync(join(home, '.claude'), { recursive: true });
    writeFileSync(join(home, '.claude.json'), JSON.stringify({ mcpServers: { existing: { type: 'http', url: 'https://x' } } }));
    writeFileSync(join(home, '.claude', 'settings.json'), JSON.stringify({ hooks: { Stop: [{ hooks: [{ type: 'command', command: 'echo hi' }] }] } }));
  }
  if (codex) {
    mkdirSync(join(home, '.codex'), { recursive: true });
    writeFileSync(join(home, '.codex', 'config.toml'), 'model = "gpt-5"\n\n[mcp_servers.context7]\ncommand = "npx"\n');
  }
  return home;
}

function run(home, ...flags) {
  const result = spawnSync(process.execPath, [CLI, '--home', home, ...flags], {
    encoding: 'utf8',
    env: { ...process.env, MISAKANET_ENDPOINT: OFFLINE },
  });
  return result;
}

/**
 * Structural run: no endpoint override and no registration, so it asserts the real
 * production URL and touches no network (the hook ships inside the package).
 * `run()` above is for the paths that need a dead endpoint on purpose.
 */
function runOffline(home, ...flags) {
  const env = { ...process.env };
  delete env.MISAKANET_ENDPOINT;
  return spawnSync(process.execPath, [CLI, '--home', home, '--no-register', ...flags], {
    encoding: 'utf8',
    env,
  });
}

function snapshot(dir) {
  const out = {};
  const walk = (p) => {
    for (const entry of readdirSync(p, { withFileTypes: true })) {
      const full = join(p, entry.name);
      if (entry.isDirectory()) walk(full);
      else out[full.replace(dir, '')] = readFileSync(full, 'utf8');
    }
  };
  walk(dir);
  return out;
}


/**
 * Async run. Required whenever an in-process stub server is involved: `spawnSync` blocks
 * the event loop, so the stub in this same process can never answer and the child times
 * out (which is exactly how this test failed the first time).
 */
function runAsync(home, env, ...flags) {
  return new Promise((done) => {
    const child = spawn(process.execPath, [CLI, '--home', home, ...flags], { env });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => { stdout += chunk; });
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.on('close', (status) => done({ status, stdout, stderr }));
  });
}

test('installs all three pieces for Claude Code and Codex', () => {
  const home = makeHome();
  const result = runOffline(home);
  assert.equal(result.status, 0, result.stdout + result.stderr);

  const claude = JSON.parse(readFileSync(join(home, '.claude.json'), 'utf8'));
  assert.equal(claude.mcpServers.misakanet.url, 'https://misakanet.org/mcp');
  assert.equal(claude.mcpServers.misakanet.type, 'http');
  assert.ok(claude.mcpServers.existing, 'existing servers must survive');

  const settings = JSON.parse(readFileSync(join(home, '.claude', 'settings.json'), 'utf8'));
  assert.ok(settings.hooks.Stop, "the user's own hooks must survive");
  const commands = Object.values(settings.hooks).flat().flatMap((e) => e.hooks.map((h) => h.command));
  assert.ok(commands.some((c) => c.includes('hook.mjs') && c.endsWith('prompt')), commands.join('|'));
  assert.ok(commands.some((c) => c.includes('hook.mjs') && c.endsWith('failure')), commands.join('|'));

  assert.ok(existsSync(join(home, '.misakanet-agent', 'hook.mjs')), 'hook ships with the package');
  for (const rel of ['.claude/CLAUDE.md', '.codex/AGENTS.md']) {
    const text = readFileSync(join(home, rel), 'utf8');
    assert.match(text, /misakanet:start/);
    assert.match(text, /misakanet_search/);
  }
  const toml = readFileSync(join(home, '.codex', 'config.toml'), 'utf8');
  assert.match(toml, /\[mcp_servers\.misakanet\]/);
  assert.match(toml, /experimental_use_rmcp_client = true/);
  // the top-level key must precede the first table, or TOML scopes it to that table
  assert.ok(toml.indexOf('experimental_use_rmcp_client') < toml.indexOf('[mcp_servers.'), toml);
  assert.match(toml, /\[mcp_servers\.context7\]/, 'existing servers must survive');
});

test('is idempotent: a second run changes nothing', () => {
  const home = makeHome();
  runOffline(home);
  const first = snapshot(home);
  const second = runOffline(home);
  assert.equal(second.status, 0);
  assert.deepEqual(snapshot(home), first, 'second run must be a no-op');
  assert.match(second.stdout, /无改动|已存在/, second.stdout);
});

test('dry-run writes nothing at all', () => {
  const home = makeHome();
  const before = snapshot(home);
  const result = runOffline(home, '--dry-run');
  assert.equal(result.status, 0);
  assert.deepEqual(snapshot(home), before);
  assert.ok(!existsSync(join(home, '.misakanet-agent')), 'dry-run must not create state');
});

test('uninstall restores the original config', () => {
  const home = makeHome();
  runOffline(home);
  const result = runOffline(home, '--uninstall');
  assert.equal(result.status, 0, result.stdout + result.stderr);

  const claude = JSON.parse(readFileSync(join(home, '.claude.json'), 'utf8'));
  assert.deepEqual(claude.mcpServers, { existing: { type: 'http', url: 'https://x' } });

  const settings = JSON.parse(readFileSync(join(home, '.claude', 'settings.json'), 'utf8'));
  assert.deepEqual(Object.keys(settings.hooks), ['Stop'], 'empty event keys must not be left behind');
  assert.ok(!readFileSync(join(home, '.codex', 'config.toml'), 'utf8').includes('misakanet'));
  assert.ok(!existsSync(join(home, '.claude', 'CLAUDE.md')), 'a file created only for our block should go');
  assert.ok(!existsSync(join(home, '.misakanet-agent')), 'state directory removed');
});

test('verify fails clearly when nothing is installed, and says what to do', () => {
  const home = makeHome();
  const result = run(home, '--verify');
  assert.equal(result.status, 1, 'an unconfigured home must not report READY');
  assert.match(result.stdout, /NOT READY/);
  assert.match(result.stdout, /端点不可达|缺失|没装/);
});

test('verify passes once installed, against a reachable endpoint', async () => {
  const { createServer } = await import('node:http');
  const server = createServer((req, res) => {
    let body = '';
    req.on('data', (chunk) => { body += chunk; });
    req.on('end', () => {
      const payload = JSON.parse(body || '{}');
      const tool = payload.params?.name;
      const result = tool === 'misakanet_register'
        ? { node_id: 'MisakaTEST', token: TOKEN_SHAPE_OK }
        : { results: [{ id: 'stub', type: 'lesson' }] };
      const reply = JSON.stringify({ jsonrpc: '2.0', id: 1, result: {
        content: [{ type: 'text', text: JSON.stringify(result) }], structuredContent: result } });
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(reply);
    });
  });
  await new Promise((done) => server.listen(0, '127.0.0.1', done));
  const url = `http://127.0.0.1:${server.address().port}/mcp`;

  try {
    const home = makeHome();
    const install = await runAsync(home, { ...process.env, MISAKANET_ENDPOINT: url });
    assert.equal(install.status, 0, install.stdout + install.stderr);

    // the token must reach the config, or the user hits the 5-reads/day wall
    const claude = JSON.parse(readFileSync(join(home, '.claude.json'), 'utf8'));
    assert.equal(claude.mcpServers.misakanet.url, url, 'the CLI honours MISAKANET_ENDPOINT');
    assert.equal(claude.mcpServers.misakanet.headers.Authorization, `Bearer ${TOKEN_SHAPE_OK}`);
    const toml = readFileSync(join(home, '.codex', 'config.toml'), 'utf8');
    assert.ok(toml.includes(`http_headers = { Authorization = "Bearer ${TOKEN_SHAPE_OK}" }`), toml);

    const verify = await runAsync(home, { ...process.env, MISAKANET_ENDPOINT: url }, '--verify');
    assert.equal(verify.status, 0, verify.stdout + verify.stderr);
    assert.match(verify.stdout, /READY/);
  } finally {
    server.close();
  }
});

test('offline install still leaves a working read path and says so', () => {
  const home = makeHome();
  const result = run(home);
  assert.equal(result.status, 0);
  assert.match(result.stdout, /注册没成功|离线/, 'the user must be told, in plain words');
  assert.ok(!existsSync(join(home, '.misakanet-agent', 'token')), 'no fake token');
  const claude = JSON.parse(readFileSync(join(home, '.claude.json'), 'utf8'));
  assert.equal(claude.mcpServers.misakanet.headers, undefined, 'no token, no header');
});

test('a machine with no agents gets told what to do instead of a silent success', () => {
  const home = mkdtempSync(join(tmpdir(), 'mn-empty-'));
  try {
    const result = runOffline(home);
    assert.equal(result.status, 0);
    assert.match(result.stdout, /没检测到/, result.stdout);
    assert.ok(!existsSync(join(home, '.misakanet-agent')), 'nothing to configure, nothing to litter');
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('the verification probe never forwards the stored token', async () => {
  // CodeQL js/file-access-to-http #268 was exactly this: read the token file, attach it to
  // a request. The probe does not need a credential, so it sends none - the token's job is
  // to be written into the agent's MCP config, which is file-to-file.
  const { createServer } = await import('node:http');
  const seen = [];
  const server = createServer((req, res) => {
    seen.push(req.headers.authorization || null);
    let body = '';
    req.on('data', (c) => { body += c; });
    req.on('end', () => {
      const result = { results: [{ id: 'stub', type: 'lesson' }] };
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ jsonrpc: '2.0', id: 1, result: {
        content: [{ type: 'text', text: JSON.stringify(result) }], structuredContent: result } }));
    });
  });
  await new Promise((done) => server.listen(0, '127.0.0.1', done));
  const url = `http://127.0.0.1:${server.address().port}/mcp`;

  try {
    const home = makeHome();
    mkdirSync(join(home, '.misakanet-agent'), { recursive: true });
    writeFileSync(join(home, '.misakanet-agent', 'token'), FILE_TOKEN);
    const result = await runAsync(home, { ...process.env, MISAKANET_ENDPOINT: url }, '--verify');
    assert.equal(seen.length > 0, true, 'the verify probe must have been made');
    for (const header of seen) {
      assert.equal(header, null, `file token leaked to a custom endpoint: ${header}`);
    }
    assert.equal(result.status, 1, 'a home with no MCP entry still reports NOT READY');

    // ...and an exported token is not forwarded by the probe either (it is the agent's
    // MCP config that carries it, not this process).
    seen.length = 0;
    await runAsync(home, { ...process.env, MISAKANET_ENDPOINT: url, MISAKANET_TOKEN: EXPORTED_TOKEN }, '--verify');
    assert.equal(seen[0], null, `probe must stay anonymous, saw ${seen[0]}`);
  } finally {
    server.close();
  }
});

// ── OpenClaw (issue #1680) ──────────────────────────────────────────────────
// OpenClaw is the one target whose MCP registration is handed to another program
// (`openclaw mcp add`), so its tests own PATH: "the CLI is there" and "the CLI is missing"
// are both real user states, and neither is reachable from the developer's own PATH.

function makeOpenclawHome() {
  const home = mkdtempSync(join(tmpdir(), 'mn-openclaw-'));
  mkdirSync(join(home, '.openclaw', 'workspace'), { recursive: true });
  return home;
}

/** A stand-in CLI that records how it was called, and answers `mcp list` when asked. */
function fakeOpenclaw(dir, { listLine = '', fail = '' } = {}) {
  mkdirSync(dir, { recursive: true });
  const argsFile = join(dir, 'args.txt');
  const lines = ['#!/bin/sh', `echo "$@" >> "${argsFile}"`];
  if (fail) lines.push(`echo "${fail}" >&2`, 'exit 1');
  else if (listLine) lines.push(`if [ "$1" = "mcp" ] && [ "$2" = "list" ]; then echo "${listLine}"; fi`, 'exit 0');
  else lines.push('exit 0');
  writeFileSync(join(dir, 'openclaw'), `${lines.join('\n')}\n`);
  chmodSync(join(dir, 'openclaw'), 0o755);
  return { bin: dir, argsFile };
}

/** Minimal PATH so the child finds sh and nothing else - never the real openclaw. */
const BARE_PATH = ['/usr/bin', '/bin'];

/**
 * Structural run with a controlled PATH: no endpoint override, so the assertions can pin the
 * real production URL that a user's install would carry.
 */
function runWithPath(home, pathDirs, ...flags) {
  const env = { ...process.env, PATH: pathDirs.join(':') };
  delete env.MISAKANET_ENDPOINT;
  return spawnSync(process.execPath, [CLI, '--home', home, ...flags], { encoding: 'utf8', env });
}

/** Same, but pointed at a dead port: for `--verify`, which probes the endpoint itself. */
function verifyWithPath(home, pathDirs) {
  const env = { ...process.env, PATH: pathDirs.join(':'), MISAKANET_ENDPOINT: OFFLINE };
  return spawnSync(process.execPath, [CLI, '--home', home, '--verify'], { encoding: 'utf8', env });
}

test('openclaw: dry-run reports the rules block and the exact CLI command it would run', () => {
  const home = makeOpenclawHome();
  const args = fakeOpenclaw(join(home, 'fakebin'));
  const before = snapshot(home);
  try {
    const result = runWithPath(home, [args.bin, ...BARE_PATH], '--only', 'openclaw', '--no-register', '--dry-run');
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.match(result.stdout, /OpenClaw：规则块 added/, result.stdout);
    assert.match(result.stdout,
      /openclaw mcp add misakanet --url https:\/\/misakanet\.org\/mcp --transport streamable-http --no-probe/);
    assert.deepEqual(snapshot(home), before, 'dry-run must write nothing');
    assert.ok(!existsSync(args.argsFile), 'dry-run must not run the CLI either');
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('openclaw: a machine without the CLI is told the exact command instead of a silent pass', () => {
  const home = makeOpenclawHome();
  try {
    // PATH holds an empty directory: whatever the developer has installed, this run cannot
    // see an `openclaw`, which is exactly the state the message is for.
    const empty = join(home, 'empty-bin');
    mkdirSync(empty, { recursive: true });
    const result = runWithPath(home, [empty, ...BARE_PATH], '--only', 'openclaw', '--no-register');
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.match(result.stdout, /没找到 openclaw CLI/, result.stdout);
    assert.match(result.stdout,
      /openclaw mcp add misakanet --url https:\/\/misakanet\.org\/mcp --transport streamable-http/);
    // the rules block is still written: the half that does not need the CLI must not be lost
    assert.match(readFileSync(join(home, '.openclaw', 'workspace', 'AGENTS.md'), 'utf8'), /misakanet:start/);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('openclaw: registers through the CLI, and the token travels as a header', () => {
  const home = makeOpenclawHome();
  const args = fakeOpenclaw(join(home, 'fakebin'));
  try {
    // A stored token means ensureIdentity() returns it without any network call, so this
    // test can assert the header without a stub server.
    mkdirSync(join(home, '.misakanet-agent'), { recursive: true });
    writeFileSync(join(home, '.misakanet-agent', 'token'), TOKEN_SHAPE_OK);
    const result = runWithPath(home, [args.bin, ...BARE_PATH], '--only', 'openclaw');
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.match(result.stdout, /OpenClaw：已注册 MCP/, result.stdout);
    const called = readFileSync(args.argsFile, 'utf8').trim();
    assert.equal(called,
      `mcp add misakanet --url https://misakanet.org/mcp --transport streamable-http --no-probe `
      + `--header Authorization=Bearer ${TOKEN_SHAPE_OK}`);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('openclaw: a CLI that cannot start gets the cache hint, not a raw stderr', () => {
  const home = makeOpenclawHome();
  const args = fakeOpenclaw(join(home, 'fakebin'), { fail: 'Could not start the CLI EACCES' });
  try {
    const result = runWithPath(home, [args.bin, ...BARE_PATH], '--only', 'openclaw', '--no-register');
    assert.match(result.stdout, /XDG_CACHE_HOME/, result.stdout);
    assert.match(result.stdout, /openclaw mcp add misakanet --url/);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('openclaw: verify distinguishes installed, not-registered and unverifiable', () => {
  const home = makeOpenclawHome();
  const home2 = home;
  try {
    // 1) registered
    const good = fakeOpenclaw(join(home2, 'bin-ok'), { listLine: 'misakanet  streamable-http' });
    runWithPath(home2, [good.bin, ...BARE_PATH], '--only', 'openclaw', '--no-register');
    let verify = verifyWithPath(home2, [good.bin, ...BARE_PATH]);
    assert.match(verify.stdout, /OpenClaw：MCP 已注册/, verify.stdout);

    // 2) the CLI answers, but has no such entry
    const bare = fakeOpenclaw(join(home2, 'bin-bare'));
    verify = verifyWithPath(home2, [bare.bin, ...BARE_PATH]);
    assert.match(verify.stdout, /OpenClaw：MCP 未注册/, verify.stdout);
    assert.equal(verify.status, 1, 'not-registered must not report READY');

    // 3) no CLI at all: honest "cannot confirm", never a silent pass
    const empty = join(home2, 'bin-empty');
    mkdirSync(empty, { recursive: true });
    verify = verifyWithPath(home2, [empty, ...BARE_PATH]);
    assert.match(verify.stdout, /无法确证 MCP 是否注册/, verify.stdout);
    assert.equal(verify.status, 1);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('openclaw: uninstall removes the block it added and says who owns the MCP entry', () => {
  const home = makeOpenclawHome();
  const args = fakeOpenclaw(join(home, 'fakebin'));
  try {
    runWithPath(home, [args.bin, ...BARE_PATH], '--only', 'openclaw', '--no-register');
    assert.ok(existsSync(join(home, '.openclaw', 'workspace', 'AGENTS.md')));
    const result = runWithPath(home, [args.bin, ...BARE_PATH], '--uninstall');
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.match(result.stdout, /移除规则块 → \.openclaw\/workspace\/AGENTS\.md/, result.stdout);
    assert.match(result.stdout, /openclaw mcp remove misakanet/);
    assert.ok(!existsSync(join(home, '.openclaw', 'workspace', 'AGENTS.md')),
      'a file created only for our block should go');
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});
