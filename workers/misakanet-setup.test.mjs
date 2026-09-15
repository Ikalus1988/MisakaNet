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
// OpenClaw is configured by writing its own config file, the same way this installer already
// handles ~/.claude.json and ~/.codex/config.toml. It used to shell out to `openclaw mcp add`,
// which put the token in argv and tripped the plugin scanner's SHELL_INJECTION_PATTERN
// (alert #269, 2026-09-15); the tests below pin the property that replaced it.

function makeOpenclawHome() {
  const home = mkdtempSync(join(tmpdir(), 'mn-openclaw-'));
  mkdirSync(join(home, '.openclaw', 'workspace'), { recursive: true });
  writeFileSync(join(home, '.openclaw', 'openclaw.json'),
    JSON.stringify({ meta: { keep: true }, mcp: { servers: { other: { url: 'https://x' } } } }, null, 2));
  return home;
}

const readOpenclaw = (home) =>
  JSON.parse(readFileSync(join(home, '.openclaw', 'openclaw.json'), 'utf8'));

test('openclaw: dry-run says what it would write, and writes nothing', () => {
  const home = makeOpenclawHome();
  const before = snapshot(home);
  try {
    const result = runOffline(home, '--only', 'openclaw', '--dry-run');
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.match(result.stdout, /OpenClaw：规则块 added/, result.stdout);
    assert.match(result.stdout, /OpenClaw：注册 MCP/, result.stdout);
    assert.deepEqual(snapshot(home), before, 'dry-run must write nothing');
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('openclaw: writes the MCP entry beside the servers the user already has', () => {
  const home = makeOpenclawHome();
  try {
    const result = runOffline(home, '--only', 'openclaw');
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.match(result.stdout, /OpenClaw：注册 MCP/, result.stdout);

    const cfg = readOpenclaw(home);
    assert.equal(cfg.mcp.servers.misakanet.url, 'https://misakanet.org/mcp');
    assert.equal(cfg.mcp.servers.misakanet.transport, 'streamable-http');
    assert.ok(cfg.mcp.servers.other, 'existing servers must survive');
    assert.ok(cfg.meta.keep, 'unrelated top-level keys must survive');
    assert.match(readFileSync(join(home, '.openclaw', 'workspace', 'AGENTS.md'), 'utf8'),
      /misakanet:start/);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('openclaw: the token reaches the config and never an argv', () => {
  const home = makeOpenclawHome();
  try {
    mkdirSync(join(home, '.misakanet-agent'), { recursive: true });
    writeFileSync(join(home, '.misakanet-agent', 'token'), TOKEN_SHAPE_OK);
    // Must NOT pass --no-register, or there is no bearer to check; and a stored token means
    // ensureIdentity returns it without any network call.
    const env = { ...process.env };
    delete env.MISAKANET_ENDPOINT;
    const result = spawnSync(process.execPath,
      [CLI, '--home', home, '--only', 'openclaw'], { encoding: 'utf8', env });
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.equal(readOpenclaw(home).mcp.servers.misakanet.headers.Authorization,
      `Bearer ${TOKEN_SHAPE_OK}`);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('openclaw: an unreadable config becomes a manual step, not a silent pass', () => {
  const home = makeOpenclawHome();
  try {
    writeFileSync(join(home, '.openclaw', 'openclaw.json'), '{ this is not json');
    const before = readFileSync(join(home, '.openclaw', 'openclaw.json'), 'utf8');
    const result = runOffline(home, '--only', 'openclaw');
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.match(result.stdout, /读不到或解析不了/, result.stdout);
    assert.match(result.stdout, /openclaw mcp add misakanet --url/);
    assert.equal(readFileSync(join(home, '.openclaw', 'openclaw.json'), 'utf8'), before,
      'a config we cannot parse must be left exactly as it was');
    // the half that does not need the config is still installed
    assert.match(readFileSync(join(home, '.openclaw', 'workspace', 'AGENTS.md'), 'utf8'),
      /misakanet:start/);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('openclaw: idempotent — a second run changes nothing', () => {
  const home = makeOpenclawHome();
  try {
    runOffline(home, '--only', 'openclaw');
    const first = snapshot(home);
    const second = runOffline(home, '--only', 'openclaw');
    assert.match(second.stdout, /MCP 已注册（无改动）/, second.stdout);
    assert.deepEqual(snapshot(home), first, 'second run must be a no-op');
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('openclaw: verify reads the registry file and reports both states', () => {
  const home = makeOpenclawHome();
  try {
    // not registered yet: the rules may be in place, the MCP entry is not
    let verify = run(home, '--verify');
    assert.match(verify.stdout, /OpenClaw：MCP 未注册/, verify.stdout);
    assert.equal(verify.status, 1, 'not-registered must not report READY');

    runOffline(home, '--only', 'openclaw');
    verify = run(home, '--verify');
    assert.match(verify.stdout, /OpenClaw：MCP 已注册/, verify.stdout);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('openclaw: uninstall removes both the entry we wrote and the rules block', () => {
  const home = makeOpenclawHome();
  try {
    runOffline(home, '--only', 'openclaw');
    const result = runOffline(home, '--uninstall');
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.match(result.stdout, /移除规则块 → \.openclaw\/workspace\/AGENTS\.md/, result.stdout);
    assert.equal(readOpenclaw(home).mcp.servers.misakanet, undefined);
    assert.ok(readOpenclaw(home).mcp.servers.other, "the user's own servers stay");
    assert.ok(!existsSync(join(home, '.openclaw', 'workspace', 'AGENTS.md')),
      'a file created only for our block should go');
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('the installer never hands a value to another program', () => {
  // Property, not incident: alert #269 (plugin scanner, 2026-09-15) was "file-derived value
  // interpolated into a shell execution call" from the old `openclaw mcp add` path, and argv
  // is visible to every process on the box. Every target is configured by writing its config.
  // Matched on import and call shapes, not the bare words: the comment above the import that
  // explains why we do not spawn must not fail this test (it did, first run).
  const source = readFileSync(CLI, 'utf8');
  for (const forbidden of ["'node:child_process'", '"child_process"', 'spawnSync(', 'spawn(',
    'execSync(', 'execFile(']) {
    assert.ok(!source.includes(forbidden), `the installer must not use ${forbidden}`);
  }
});

test('the User-Agent version is bound to the manifest by a test, not by a file read', () => {
  // Both halves matter. The literal must match package.json (otherwise a release ships a stale
  // UA), and it must stay a literal: reading the manifest at runtime made the value flow from a
  // file into a request header, which is CodeQL js/file-access-to-http #268 all over again.
  const declared = JSON.parse(
    readFileSync(join(CLI, '..', '..', 'package.json'), 'utf8')).version;
  assert.equal(declared, '0.4.0', 'bump this test when the package version moves');
  // A plain substring, not a RegExp: building a pattern from a value with `.replace(/\./g…)`
  // left backslashes unescaped, which CodeQL correctly reported as incomplete sanitization
  // (js/incomplete-sanitization, high) on the first version of this test.
  assert.ok(readFileSync(CLI, 'utf8').includes(`const VERSION = '${declared}'`),
    `the installer's VERSION literal must equal package.json's ${declared}`);
  assert.ok(!readFileSync(CLI, 'utf8').includes("join(PKG_ROOT, 'package.json')"),
    'the manifest must not be read at runtime');
});

// ── Hermes (issue #1681) ────────────────────────────────────────────────────
// Hermes keeps its MCP registry in ~/.hermes/config.yaml and the token in ~/.hermes/.env,
// which is exactly what `hermes mcp add --auth header` writes. The installer does it by file
// (no subprocess), so these tests own the two files that must stay valid from a plain text
// edit: a YAML mapping and a dotenv file.

const HERMES_CONFIG = [
  'model:',
  '  default: MiniMax-M3',
  'mcp_servers:',
  '  rag:',
  '    command: /usr/local/bin/rag',
  '    args: []',
  'toolsets:',
  '  - hermes-cli',
  '',
].join('\n');

function makeHermesHome(config = HERMES_CONFIG) {
  const home = mkdtempSync(join(tmpdir(), 'mn-hermes-'));
  mkdirSync(join(home, '.hermes'), { recursive: true });
  writeFileSync(join(home, '.hermes', 'config.yaml'), config);
  return home;
}

const readHermes = (home) => readFileSync(join(home, '.hermes', 'config.yaml'), 'utf8');

test('hermes: registers under mcp_servers and keeps the servers already there', () => {
  const home = makeHermesHome();
  try {
    const result = runOffline(home, '--only', 'hermes');
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.match(result.stdout, /Hermes：注册 MCP/, result.stdout);
    const cfg = readHermes(home);
    assert.match(cfg, /^mcp_servers:\n  misakanet:  # misakanet:start\n    url: https:\/\/misakanet\.org\/mcp\n  # misakanet:end\n  rag:/m,
      'the entry must be a child of mcp_servers and sit before the existing server, with no\n'
      + 'blank line invented between them:\n' + cfg);
    assert.match(readFileSync(join(home, '.hermes', 'SOUL.md'), 'utf8'), /misakanet:start/);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('hermes: the token goes to .env, and only a template goes in the config', () => {
  const home = makeHermesHome();
  try {
    mkdirSync(join(home, '.misakanet-agent'), { recursive: true });
    writeFileSync(join(home, '.misakanet-agent', 'token'), TOKEN_SHAPE_OK);
    const env = { ...process.env };
    delete env.MISAKANET_ENDPOINT;
    const result = spawnSync(process.execPath,
      [CLI, '--home', home, '--only', 'hermes'], { encoding: 'utf8', env });
    assert.equal(result.status, 0, result.stdout + result.stderr);

    const cfg = readHermes(home);
    assert.match(cfg, /Authorization: Bearer \$\{MCP_MISAKANET_API_KEY\}/, cfg);
    assert.ok(!cfg.includes(TOKEN_SHAPE_OK), 'the token must not be written into the YAML');
    assert.match(readFileSync(join(home, '.hermes', '.env'), 'utf8'),
      new RegExp(`^MCP_MISAKANET_API_KEY=${TOKEN_SHAPE_OK}$`, 'm'));
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('hermes: an entry the CLI wrote earlier is replaced, not duplicated', () => {
  const home = makeHermesHome(HERMES_CONFIG.replace('  rag:',
    '  misakanet:\n    url: https://misakanet.org/mcp\n    enabled: true\n  rag:'));
  try {
    const result = runOffline(home, '--only', 'hermes');
    assert.equal(result.status, 0, result.stdout + result.stderr);
    const cfg = readHermes(home);
    assert.equal((cfg.match(/^[ \t]*misakanet:/gm) || []).length, 1,
      'a duplicate YAML key would be a config corruption:\n' + cfg);
    assert.match(cfg, /misakanet:  # misakanet:start/);
    assert.ok(!cfg.includes('enabled: true'), 'the old entry is gone, replaced by ours');
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('hermes: a config with no mcp_servers key gets a new section', () => {
  const home = makeHermesHome('model:\n  default: MiniMax-M3\n');
  try {
    runOffline(home, '--only', 'hermes');
    assert.match(readHermes(home), /^mcp_servers:\n  misakanet:  # misakanet:start/m);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('hermes: verify reports the registration, and uninstall restores the file exactly', () => {
  const home = makeHermesHome();
  try {
    let verify = run(home, '--verify');
    assert.match(verify.stdout, /Hermes：MCP 未注册/, verify.stdout);
    assert.equal(verify.status, 1, 'a detected Hermes without our entry must not report READY');

    // With a stored token the install also writes ~/.hermes/.env, which is the branch that
    // claims "written, but whether Hermes loaded it cannot be confirmed from here".
    mkdirSync(join(home, '.misakanet-agent'), { recursive: true });
    writeFileSync(join(home, '.misakanet-agent', 'token'), TOKEN_SHAPE_OK);
    const env = { ...process.env };
    delete env.MISAKANET_ENDPOINT;
    spawnSync(process.execPath, [CLI, '--home', home, '--only', 'hermes'],
      { encoding: 'utf8', env });
    verify = run(home, '--verify');
    assert.match(verify.stdout, /Hermes：MCP 条目与 token 都在/, verify.stdout);
    assert.match(verify.stdout, /无法确认 Hermes 是否已加载/, verify.stdout);

    runOffline(home, '--uninstall');
    assert.equal(readHermes(home), HERMES_CONFIG,
      'uninstall must leave the config byte-for-byte as it was');
    assert.ok(!readFileSync(join(home, '.hermes', '.env'), 'utf8').includes(TOKEN_SHAPE_OK),
      'the token line goes with the entry');
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('hermes: the unmarked-entry pattern cannot eat the next server', () => {
  // HERMES_BARE matches an entry plus its indented children. Written too loosely it would
  // swallow whatever follows, so the replacement is pinned against a neighbour.
  const home = makeHermesHome('mcp_servers:\n  misakanet:\n    url: https://x/mcp\n  rag:\n    command: rag\n');
  try {
    runOffline(home, '--only', 'hermes');
    const cfg = readHermes(home);
    assert.match(cfg, /  rag:\n    command: rag\n/, cfg);
    assert.equal((cfg.match(/^[ \t]*misakanet:/gm) || []).length, 1, cfg);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

// ── version stamp (issue #1682) ─────────────────────────────────────────────
// The stamp is what makes an upgrade path possible at all: the hook reads it to decide whether
// to mention an upgrade, and `--verify` reads it to say how old the install is. `installed_at`
// must survive a re-run, or the 14-day cadence the user was promised never arrives.

const VERSION_FILE = (home) => join(home, '.misakanet-agent', 'version');

test('install records the version and the moment it was installed', () => {
  const home = makeHome();
  try {
    runOffline(home);
    const stamp = JSON.parse(readFileSync(VERSION_FILE(home), 'utf8'));
    const declared = JSON.parse(
      readFileSync(join(CLI, '..', '..', 'package.json'), 'utf8')).version;
    assert.equal(stamp.version, declared, 'the stamp must name the version that wrote it');
    assert.equal(stamp.package, '@misaka-net/misakanet-setup');
    assert.match(stamp.installed_at, /^\d{4}-\d{2}-\d{2}T/);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('re-running the same version does not restart the upgrade clock', () => {
  const home = makeHome();
  try {
    runOffline(home);
    const first = JSON.parse(readFileSync(VERSION_FILE(home), 'utf8'));
    const second = runOffline(home);
    assert.match(second.stdout, /版本戳已存在/);
    const after = JSON.parse(readFileSync(VERSION_FILE(home), 'utf8'));
    assert.equal(after.installed_at, first.installed_at,
      'a re-run that moved installed_at would postpone the nudge forever');
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('a newer version moves the stamp forward', () => {
  const home = makeHome();
  try {
    mkdirSync(join(home, '.misakanet-agent'), { recursive: true });
    writeFileSync(VERSION_FILE(home), JSON.stringify({
      package: '@misaka-net/misakanet-setup', version: '0.0.1', installed_at: '2020-01-01T00:00:00Z',
    }));
    const result = runOffline(home);
    assert.match(result.stdout, /版本戳 → .*原 0\.0\.1/, result.stdout);
    const stamp = JSON.parse(readFileSync(VERSION_FILE(home), 'utf8'));
    assert.notEqual(stamp.installed_at, '2020-01-01T00:00:00Z');
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('verify reports the version, and stays quiet when the registry is unreachable', () => {
  const home = makeHome();
  try {
    runOffline(home);
    const env = {
      ...process.env,
      MISAKANET_ENDPOINT: OFFLINE,
      MISAKANET_REGISTRY_URL: 'http://127.0.0.1:9/latest',
    };
    const verify = spawnSync(process.execPath, [CLI, '--home', home, '--verify'],
      { encoding: 'utf8', env });
    assert.match(verify.stdout, /版本：装机版本 \d+\.\d+\.\d+/,
      `an offline registry check must not hide the installed version:\n${verify.stdout}`);
    assert.match(verify.stdout, /查不到最新版本/, verify.stdout);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('uninstall takes the version stamp with it', () => {
  const home = makeHome();
  try {
    runOffline(home);
    assert.ok(existsSync(VERSION_FILE(home)));
    runOffline(home, '--uninstall');
    assert.ok(!existsSync(join(home, '.misakanet-agent')),
      'leaving a stamp behind would let the hook nudge a machine that no longer has MisakaNet');
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('verify compares versions properly, including an install ahead of the registry', async () => {
  // Three cases share one stub: behind, current, and ahead. The last one matters because a
  // checkout stamps a version the registry has not caught up with, and "update to 0.0.1" is
  // advice to downgrade.
  //
  // runAsync, not spawnSync: the stub lives in this process, and spawnSync blocks the event
  // loop, so the child would time out waiting for an answer that can never arrive (the trap
  // this file's harness comment already documents).
  const { createServer } = await import('node:http');
  let published = '';
  const server = createServer((req, res) => {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ name: '@misaka-net/misakanet-setup', version: published }));
  });
  await new Promise((done) => server.listen(0, '127.0.0.1', done));
  const registry = `http://127.0.0.1:${server.address().port}/latest`;

  try {
    const home = makeHome();
    try {
      await runAsync(home, { ...process.env, MISAKANET_ENDPOINT: OFFLINE });
      const installed = JSON.parse(
        readFileSync(join(CLI, '..', '..', 'package.json'), 'utf8')).version;
      const env = {
        ...process.env, MISAKANET_ENDPOINT: OFFLINE, MISAKANET_REGISTRY_URL: registry,
      };
      const check = async () => (await runAsync(home, env, '--verify')).stdout;

      published = '0.0.1';                       // older than what is installed
      const ahead = await check();
      assert.match(ahead, /领先于已发布的最新 0\.0\.1/, ahead);

      published = installed;                     // exactly current
      assert.match(await check(), /已是最新/);

      published = '99.0.0';                      // newer
      const behind = await check();
      assert.match(behind, /装机 \d+\.\d+\.\d+.*→ 最新 99\.0\.0/, behind);
      assert.match(behind, /npx @misaka-net\/misakanet-setup@latest/, behind);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  } finally {
    server.close();
  }
});
