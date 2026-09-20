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
import { existsSync, mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync, readdirSync, chmodSync, openSync, fstatSync, closeSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { testToken } from './_test-token.mjs';

// `fileURLToPath(import.meta.url)`, not `import.meta.dirname`: the shipped code must run on Node 18
// (package.json engines says >=18), and this suite is what proves it — a test file that needs
// Node 20.11 to *load* would hide an 18-incompatibility instead of reporting it.
const CLI = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'packages', 'misakanet-setup', 'bin', 'misakanet-setup.mjs');
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

// ── uninstall on a *bare* home: the case every earlier test missed ────────────────────────
// `makeHome()` above gives the user their own `mcpServers` and `hooks.Stop`, so the containers our
// install writes into already existed and removing only our leaves looked like a full restore.
// On a bare home the leaves left containers behind: `{}` came back as `{"mcpServers": {}}`,
// `{"hooks": {}, "permissions": {"allow": []}}`, `{"mcp": {"servers": {}}}`, `{"servers": {}}`, and
// `model: x` grew a dangling `mcp_servers:` key. Found 2026-09-18 by the packaged-tarball e2e.
// The table below is per agent, and asserts the whole tree — the generic version of that finding.
const BARE_HOMES = {
  claude: (home) => {
    mkdirSync(join(home, '.claude'), { recursive: true });
    writeFileSync(join(home, '.claude.json'), '{}\n');
    writeFileSync(join(home, '.claude', 'settings.json'), '{}\n');
    writeFileSync(join(home, '.claude', 'CLAUDE.md'), '# mine\n');
  },
  codex: (home) => {
    mkdirSync(join(home, '.codex'), { recursive: true });
    writeFileSync(join(home, '.codex', 'config.toml'), 'model = "gpt-5"\n');
  },
  hermes: (home) => {
    mkdirSync(join(home, '.hermes'), { recursive: true });
    writeFileSync(join(home, '.hermes', 'config.yaml'), 'model: x\n');
  },
  openclaw: (home) => {
    mkdirSync(join(home, '.openclaw', 'workspace'), { recursive: true });
    writeFileSync(join(home, '.openclaw', 'openclaw.json'), '{}\n');
  },
  codewhale: (home) => {
    mkdirSync(join(home, '.codewhale'), { recursive: true });
    writeFileSync(join(home, '.codewhale', 'mcp.json'), '{}\n');
  },
  cursor: (home) => {
    mkdirSync(join(home, '.cursor'), { recursive: true });
    writeFileSync(join(home, '.cursor', 'mcp.json'), '{}\n');
  },
};

function makeCursorHome() {
  const home = mkdtempSync(join(tmpdir(), 'mn-cursor-'));
  mkdirSync(join(home, '.cursor'), { recursive: true });
  writeFileSync(join(home, '.cursor', 'mcp.json'),
    JSON.stringify({ mcpServers: { existing: { url: 'https://x' } } }));
  return home;
}

/** The tree without the documented `.misakanet.bak` safety copies (`--uninstall` keeps them). */
const withoutBackups = (tree) => Object.fromEntries(
  Object.entries(tree).filter(([rel]) => !rel.includes('.misakanet.bak')));

for (const [agent, build] of Object.entries(BARE_HOMES)) {
  test(`uninstall: a bare ${agent} home comes back as it was`, () => {
    const home = mkdtempSync(join(tmpdir(), `mn-bare-${agent}-`));
    try {
      build(home);
      const before = snapshot(home);
      const install = runOffline(home, '--only', agent);
      assert.equal(install.status, 0, install.stdout + install.stderr);
      const removed = runOffline(home, '--only', agent, '--uninstall');
      assert.equal(removed.status, 0, removed.stdout + removed.stderr);

      const after = withoutBackups(snapshot(home));
      assert.deepEqual(after, before,
        `--uninstall must hand a bare home back exactly; left: ${JSON.stringify(after)}`);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });
}

// The counter-proof for the pruning above: it must not eat a container the user filled themselves.
test('uninstall: a home with the user\'s own servers and keys keeps all of them', () => {
  const home = makeHome();
  const json = JSON.parse(readFileSync(join(home, '.claude.json'), 'utf8'));
  json.myOwnKey = { keep: true };
  writeFileSync(join(home, '.claude.json'), `${JSON.stringify(json, null, 2)}\n`);
  const settings = JSON.parse(readFileSync(join(home, '.claude', 'settings.json'), 'utf8'));
  settings.permissions = { allow: ['Bash(git status)'] };
  writeFileSync(join(home, '.claude', 'settings.json'), `${JSON.stringify(settings, null, 2)}\n`);

  try {
    assert.equal(runOffline(home).status, 0);
    assert.equal(runOffline(home, '--uninstall').status, 0);

    const after = JSON.parse(readFileSync(join(home, '.claude.json'), 'utf8'));
    assert.deepEqual(after.myOwnKey, { keep: true }, 'a top-level key of theirs must survive');
    assert.deepEqual(after.mcpServers, { existing: { type: 'http', url: 'https://x' } },
      'their own MCP server must survive, and the container must stay because it is not empty');
    const afterSettings = JSON.parse(readFileSync(join(home, '.claude', 'settings.json'), 'utf8'));
    assert.deepEqual(afterSettings.permissions.allow, ['Bash(git status)'],
      'their own permission grants must survive');
    assert.ok(JSON.stringify(afterSettings).includes('my-hook.mjs') || afterSettings.hooks.Stop,
      'their own hook must survive');
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
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
      // tools/list is the handshake the verify probe uses now; it answers with plain fields and
      // no content array, which is the shape the old unwrapping threw on.
      const result = payload.method === 'tools/list'
        ? { tools: [{ name: 'misakanet_search' }, { name: 'misakanet_get_lesson' }] }
        : payload.params?.name === 'misakanet_register'
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

    // the token must reach the config; a token is what unlocks the write path (reads are not
    // metered since 2026-09-18)
    const claude = JSON.parse(readFileSync(join(home, '.claude.json'), 'utf8'));
    assert.equal(claude.mcpServers.misakanet.url, url, 'the CLI honours MISAKANET_ENDPOINT');
    assert.equal(claude.mcpServers.misakanet.headers.Authorization, `Bearer ${TOKEN_SHAPE_OK}`);
    const toml = readFileSync(join(home, '.codex', 'config.toml'), 'utf8');
    // One inline table, not "the line looks exactly like this": the entry grew the hint headers, and
    // a second `http_headers` line would be a duplicate TOML key that kills the whole file.
    const headerLines = toml.split('\n').filter((l) => /^\s*http_headers\s*=/.test(l));
    assert.equal(headerLines.length, 1, 'exactly one http_headers line:\n' + toml);
    assert.ok(headerLines[0].includes(`Authorization = "Bearer ${TOKEN_SHAPE_OK}"`),
      'the token must be inside that one table:\n' + toml);
    // The self-declared hints are the same story as the token: they reach the config, and the
    // minted client id is the one this run registered with.
    assert.equal(claude.mcpServers.misakanet.headers['X-MisakaNet-Agent'], 'claude-code');
    assert.match(claude.mcpServers.misakanet.headers['X-MisakaNet-Client'], /^setup-/,
      'the id this run minted must be the one the config declares');
    assert.ok(headerLines[0].includes(`X-MisakaNet-Client = "${claude.mcpServers.misakanet.headers['X-MisakaNet-Client']}"`),
      'codex must declare the same client id as Claude Code:\n' + toml);
    // A run that HAS a token must not claim it has none. The no-token note used to be pushed
    // unconditionally once the header list became one table (found 2026-09-19).
    assert.doesNotMatch(toml, /没有 token/, 'this run has a token, so that note is false:\n' + toml);

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
  const headers = claude.mcpServers.misakanet.headers || {};
  assert.equal(headers.Authorization, undefined, 'no token => no Authorization header');
  assert.equal(headers['X-MisakaNet-Agent'], 'claude-code',
    'the self-declared hints are not credentials and are written anyway (analytics, 2026-09-18)');
  assert.equal(typeof headers['X-MisakaNet-Version'], 'string',
    'the installer knows its own version and writes it as a hint');
  assert.ok(headers['X-MisakaNet-Version'].length > 0, 'and it is not empty');
  assert.match(headers['X-MisakaNet-Os'], /^[a-z0-9]+\/[a-z0-9]+$/,
    'platform/arch, which is what the endpoint records');
});

test('a machine with no agents gets told what to do, and reports failure', () => {
  // The name was right and the assertion was wrong: this test pinned `status === 0`, i.e. exactly
  // the silent success it claims to prevent. Install mode had no `process.exit` at all, so
  // "nothing to install", "registration failed" and a clean install were indistinguishable, and
  // `npx … && echo ok` asserted a success that had not happened (reproduced 2026-09-17).
  const home = mkdtempSync(join(tmpdir(), 'mn-empty-'));
  try {
    const result = runOffline(home);
    assert.equal(result.status, 1, 'installing nothing must not report success');
    assert.match(result.stdout, /没检测到/, result.stdout);
    assert.match(result.stderr, /没有装上任何助手/, result.stderr);
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
      const payload = JSON.parse(body || '{}');
      const result = payload.method === 'tools/list'
        ? { tools: [{ name: 'misakanet_search' }] }
        : { results: [{ id: 'stub', type: 'lesson' }] };
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

// The precheck ("may I write here?") used to ask about `dirname(path)` exactly once, so a target
// whose *parent* did not exist yet — the normal state on a first install, because the installer is
// about to create that parent — came back ENOENT and was reported to the user as "这些文件改不了
// （只读或权限不足）". The agent was then skipped entirely (`continue`), so the MCP registration —
// which needs no workspace at all — never happened either, and the message blamed the user's
// permissions. `makeOpenclawHome()` always pre-creates `workspace/`, which is why no test caught it.
// Reproduced 2026-09-18 against the published 0.5.4 tarball.
test('openclaw: a home without a workspace directory is not reported as a permissions problem', () => {
  const home = mkdtempSync(join(tmpdir(), 'mn-openclaw-fresh-'));
  try {
    mkdirSync(join(home, '.openclaw'), { recursive: true });
    writeFileSync(join(home, '.openclaw', 'openclaw.json'),
      JSON.stringify({ mcp: { servers: {} } }, null, 2));

    const result = runOffline(home, '--only', 'openclaw');
    assert.doesNotMatch(result.stdout, /改不了/,
      'a directory the installer is about to create is not a permission problem');
    assert.equal(result.status, 0, result.stdout + result.stderr);

    // The truth about the missing workspace, and no invented one: the MCP entry lands, the rules
    // block waits for openclaw to create its own workspace.
    assert.match(result.stdout, /找不到 workspace/, result.stdout);
    const cfg = JSON.parse(readFileSync(join(home, '.openclaw', 'openclaw.json'), 'utf8'));
    assert.equal(cfg.mcp.servers.misakanet.url, 'https://misakanet.org/mcp');
    assert.ok(!existsSync(join(home, '.openclaw', 'workspace')),
      'the installer must not fabricate a workspace it did not find');
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

// The counter-proof for the test above: the walk-up must not turn the precheck into a rubber stamp.
// A genuinely unwritable directory is still reported, and the file it protects is untouched.
test('openclaw: an unwritable config directory is still refused, and left untouched',
  { skip: process.platform === 'win32' || process.getuid?.() === 0 }, () => {
    const home = mkdtempSync(join(tmpdir(), 'mn-openclaw-ro-'));
    const cfg = join(home, '.openclaw', 'openclaw.json');
    try {
      mkdirSync(join(home, '.openclaw'), { recursive: true });
      writeFileSync(cfg, JSON.stringify({ mcp: { servers: {} } }, null, 2));
      const before = readFileSync(cfg, 'utf8');
      chmodSync(join(home, '.openclaw'), 0o500);
      try {
        const result = runOffline(home, '--only', 'openclaw');
        assert.match(result.stdout, /这些文件改不了/, result.stdout);
        assert.equal(result.status, 1, 'nothing was installed, so this is not success');
        assert.equal(readFileSync(cfg, 'utf8'), before, 'the refusal must come before any write');
        assert.ok(!existsSync(join(home, '.openclaw', 'openclaw.json.misakanet-tmp')),
          'and it must not leave a temp file behind');
      } finally {
        chmodSync(join(home, '.openclaw'), 0o700);
      }
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

test('cursor: writes the entry Cursor documents, and claims no behaviour layer', () => {
  const home = makeCursorHome();
  try {
    const result = runOffline(home, '--only', 'cursor');
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.match(result.stdout, /Cursor：注册 MCP/, result.stdout);

    const cfg = JSON.parse(readFileSync(join(home, '.cursor', 'mcp.json'), 'utf8'));
    // Cursor's documented remote shape: url + headers, and deliberately no type/transport key
    // (that is the Claude Code entry's shape, not Cursor's — copying it is a silent no-op there).
    assert.equal(cfg.mcpServers.misakanet.url, 'https://misakanet.org/mcp');
    assert.equal(cfg.mcpServers.misakanet.type, undefined);
    assert.equal(cfg.mcpServers.misakanet.transport, undefined);
    assert.equal(cfg.mcpServers.misakanet.headers['X-MisakaNet-Agent'], 'cursor');
    assert.ok(cfg.mcpServers.existing, 'existing servers must survive');

    // The honesty half: no rules block exists for Cursor, and nothing may imply one was written.
    assert.match(result.stdout, /Cursor：没有规则块与钩子/, result.stdout);

    const report = runOffline(home, '--only', 'cursor', '--report');
    assert.match(report.stdout, /^detected-agents: \[cursor\]$/m, report.stdout);
    assert.match(report.stdout, /^install-scope: mcp-only$/m,
      `a Cursor install is an endpoint, not a behaviour layer: ${report.stdout}`);
    assert.match(report.stdout, /^hook: absent$/m,
      `no hook may be written for a machine whose agents cannot consume it: ${report.stdout}`);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('cursor: idempotent — a second run changes nothing', () => {
  const home = makeCursorHome();
  try {
    runOffline(home, '--only', 'cursor');
    const afterFirst = readFileSync(join(home, '.cursor', 'mcp.json'), 'utf8');
    const second = runOffline(home, '--only', 'cursor');
    assert.match(second.stdout, /Cursor：MCP 已注册（无改动）/, second.stdout);
    assert.equal(readFileSync(join(home, '.cursor', 'mcp.json'), 'utf8'), afterFirst,
      'a second run must not rewrite the file (byte drift is invisible to every other check)');
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('a machine without Claude Code is not told its hook is missing', () => {
  // The verify block used to run the Claude Code hook checks whenever the hook file existed, so a
  // Codex-only or Cursor-only install reported NOT READY with two complaints about a target that was
  // never selected. This is the same lie the OpenClaw and Hermes checks already refused to tell.
  const home = makeCursorHome();
  try {
    const install = runOffline(home, '--only', 'cursor');
    assert.equal(install.status, 0, install.stdout + install.stderr);
    const verify = run(home, '--verify');
    assert.doesNotMatch(verify.stdout, /Claude Code/,
      `a Cursor-only machine must never be told about Claude Code: ${verify.stdout}`);
    assert.match(verify.stdout, /Cursor：MCP 已注册/, verify.stdout);
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
    // The path is absolute now: OpenClaw's rules file is located through its config, which may
    // name a workspace anywhere on the machine.
    // Flatten separators first: the line prints an OS path, so it is `openclaw\workspace\AGENTS.md`
    // on Windows. This assertion was POSIX-only until the suite first ran on Windows (2026-09-18).
    assert.match(result.stdout.replace(/\\/g, '/'),
      /移除规则块 → .*openclaw\/workspace\/AGENTS\.md/, result.stdout);
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
  assert.equal(declared, '0.5.6', 'bump this test when the package version moves');
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
    // The block gained a `headers:` list with the self-declared hints (2026-09-18); the neighbouring
    // `rag:` entry must still survive, which is what this regex is really about.
    assert.match(cfg, /^mcp_servers:\n  misakanet:  # misakanet:start\n    url: https:\/\/misakanet\.org\/mcp\n    headers:\n(?:      \S+: .*\n)*  # misakanet:end\n  rag:/m,
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
    // The `.env` did not exist before the install and held nothing but our token line, so the
    // honest restore is to take the file with it (an empty file carries no user state, and the
    // token must not stay behind — deleting the line and keeping a blank file is the halfway
    // version this used to do).
    assert.ok(!existsSync(join(home, '.hermes', '.env')),
      'a .env that held only our token line must go with the entry');
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

test('a rate-limited search answer is not reported as an unreachable endpoint', async () => {
  // The production shape that started this (2026-09-15): the endpoint answers HTTP 200 with the
  // error *inside* the JSON-RPC result, so the old probe — a search, which spends one of the five
  // free anonymous reads per run — told a user whose quota was spent that their network was down,
  // and made --verify report NOT READY for a working install.
  const { createServer } = await import('node:http');
  const seen = [];
  const server = createServer((req, res) => {
    let body = '';
    req.on('data', (c) => { body += c; });
    req.on('end', () => {
      const payload = JSON.parse(body || '{}');
      seen.push(payload.method);
      const result = payload.method === 'tools/list'
        ? { tools: [{ name: 'misakanet_search' }] }
        : { error: 'Rate limit: 5 free reads per day (searches and lesson reads share one quota) exceeded', hint: 'misakanet_register' };
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ jsonrpc: '2.0', id: 1, result: {
        content: [{ type: 'text', text: JSON.stringify(result) }], structuredContent: result } }));
    });
  });
  await new Promise((done) => server.listen(0, '127.0.0.1', done));
  const url = `http://127.0.0.1:${server.address().port}/mcp`;

  try {
    const home = makeHome();
    try {
      await runAsync(home, { ...process.env, MISAKANET_ENDPOINT: url });
      // Only the verify phase is under test: installing legitimately makes one tools/call
      // (misakanet_register), which is not a read and does not spend the read quota.
      seen.length = 0;
      const verify = await runAsync(home, { ...process.env, MISAKANET_ENDPOINT: url }, '--verify');
      assert.ok(seen.includes('tools/list'),
        `the probe must be a handshake, not a search: saw ${JSON.stringify(seen)}`);
      assert.ok(!seen.includes('tools/call'),
        `a reachability probe must not spend the anonymous read quota: saw ${JSON.stringify(seen)}`);
      assert.doesNotMatch(verify.stdout, /端点不可达/, verify.stdout);
      assert.match(verify.stdout, /端点可达.*握手成功/, verify.stdout);
      assert.equal(verify.status, 0, verify.stdout + verify.stderr);
      assert.match(verify.stdout, /READY/);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  } finally {
    server.close();
  }
});

// ── OpenClaw's real workspace (chain test, 2026-09-15) ──────────────────────
// `~/.openclaw/workspace` is a guess. The agent reads its rules from
// `agents.defaults.workspace` in ~/.openclaw/openclaw.json, and on this machine that is
// /mnt/c/Users/Eric Jia. Writing to the guessed path looked like success — the file existed
// and --verify found its own marker — while the model never saw the rules, so the chain test's
// question came back answered from memory with toolSummary {calls: 2, tools: ["exec"]}.

test('openclaw: rules go to the workspace its config names', () => {
  const home = mkdtempSync(join(tmpdir(), 'mn-oc-ws-'));
  try {
    const real = join(home, 'windows-home');
    const guessed = join(home, '.openclaw', 'workspace');
    mkdirSync(real, { recursive: true });
    mkdirSync(guessed, { recursive: true });
    writeFileSync(join(home, '.openclaw', 'openclaw.json'), JSON.stringify({
      agents: { defaults: { workspace: real } }, mcp: { servers: {} },
    }, null, 2));

    const result = runOffline(home, '--only', 'openclaw');
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.match(result.stdout, new RegExp(`OpenClaw：规则块 added → .*windows-home`), result.stdout);
    assert.match(readFileSync(join(real, 'AGENTS.md'), 'utf8'), /misakanet:start/,
      'the workspace the agent actually reads must carry the rules');
    assert.ok(!existsSync(join(guessed, 'AGENTS.md')),
      'the guessed path must not be written when the config names another workspace');

    const verify = run(home, '--verify');
    assert.match(verify.stdout, /OpenClaw：规则块已装/, verify.stdout);

    runOffline(home, '--uninstall');
    assert.ok(!existsSync(join(real, 'AGENTS.md')), 'uninstall must take it from the same place');
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test('openclaw: a configured workspace that no longer exists falls back to the default path', () => {
  const home = mkdtempSync(join(tmpdir(), 'mn-oc-ws-'));
  try {
    mkdirSync(join(home, '.openclaw', 'workspace'), { recursive: true });
    writeFileSync(join(home, '.openclaw', 'openclaw.json'), JSON.stringify({
      agents: { defaults: { workspace: join(home, 'gone') } }, mcp: { servers: {} },
    }, null, 2));
    const result = runOffline(home, '--only', 'openclaw');
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.match(readFileSync(join(home, '.openclaw', 'workspace', 'AGENTS.md'), 'utf8'),
      /misakanet:start/);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

// ── the Codex copy must state what was verified, and how to re-check it ───────
// Until 2026-09-15 the installer told the user that Codex's user-level hook "could not
// be confirmed". That was checked against codex-cli 0.154.0 and both halves hold:
//   $ codex mcp list            → misakanet | https://misakanet.org/mcp | enabled | Bearer token
//   $ codex doctor             → config.toml parse ok · MCP servers 1 · 1 streamable_http · 0 disabled
//   $ codex debug prompt-input → a `# AGENTS.md instructions` item carrying the rule block
// What remains open is the *hook* (0.154.0's lifecycle hooks are admin-managed via
// requirements.toml), so the checkpoint is rule-driven. This test keeps both halves in
// the copy — and keeps the commands there, so the claim can be re-checked rather than
// believed.
test('the Codex checkout note names the commands that verify it', () => {
  const src = readFileSync(CLI, 'utf8');
  for (const cmd of ['codex mcp list', 'codex doctor', 'codex debug prompt-input']) {
    assert.ok(src.includes(cmd), `the installer should tell the user to run \`${cmd}\``);
  }
  assert.ok(!src.includes('我没能确证'), 'the old "could not confirm" note must stay gone');
  assert.ok(src.includes('没有用户级 lifecycle hook'),
    'the limitation that does remain (no user-level hook → rule-driven checkpoint) must stay stated');
});

// ── a stale hook must be refreshed, not skipped ───────────────────────────────
// The installer returned early for any hook.mjs containing "MisakaNet", so a hook fix
// could never reach an existing install: the 14-day upgrade nudge shipped in 0.4.0, but
// a machine installed before it kept a hook without it, and re-running the installer —
// exactly what the nudge asks the user to do — reported success and changed nothing
// (found 2026-09-15 on a real install: the hook predated the nudge while `npx @latest`
// said "已存在"). Now a hook of ours that differs from the bundled copy is refreshed,
// with the previous file kept beside it.
test('a stale hook of ours is refreshed and backed up, not skipped', () => {
  const home = makeHome();
  mkdirSync(join(home, '.misakanet-agent'), { recursive: true });
  const hookPath = join(home, '.misakanet-agent', 'hook.mjs');
  const stale = '// MisakaNet checkpoint hook — an older build, from before the upgrade nudge\n';
  writeFileSync(hookPath, stale);

  const result = runOffline(home);
  assert.equal(result.status, 0, result.stderr);

  const refreshed = readFileSync(hookPath, 'utf8');
  assert.notEqual(refreshed, stale, 'a stale hook of ours must be refreshed');
  assert.match(refreshed, /UPDATE_AFTER_DAYS/,
    'the refreshed hook must carry the current logic (the upgrade nudge)');
  assert.equal(readFileSync(`${hookPath}.misakanet.bak`, 'utf8'), stale,
    'the previous hook must be kept next to the new one');
  assert.match(result.stdout, /已更新/, result.stdout);
});

// ── codewhale: a fifth target, wired the way its own CLI writes it ─────────────
// Verified live on codewhale 0.9.7 (docs/field-reports/agent-integration-matrix-2026-09-16.md):
// MCP servers live in ~/.codewhale/mcp.json, workspace rules are a plain AGENTS.md that only
// applies to a *trusted* project, and the token can only be handed over through an environment
// variable. So this target writes both surfaces file-to-file and then says the one thing the
// user still has to do (`export MISAKANET_TOKEN`), instead of reporting a clean install that
// cannot connect.
test('the codewhale target writes mcp.json and the rules of trusted projects', () => {
  const home = makeHome({ claude: false, codex: false });
  const project = join(home, 'work', 'proj');
  mkdirSync(project, { recursive: true });
  mkdirSync(join(home, '.codewhale'), { recursive: true });
  writeFileSync(join(home, '.codewhale', 'config.toml'),
    `api_key = "seed"\n\n[projects."${project}"]\ntrust_level = "trusted"\n`);

  const result = runOffline(home, '--only', 'codewhale');
  assert.equal(result.status, 0, result.stderr);

  const mcp = JSON.parse(readFileSync(join(home, '.codewhale', 'mcp.json'), 'utf8'));
  const entry = mcp.servers.misakanet;
  assert.equal(entry.url, 'https://misakanet.org/mcp');
  assert.equal(entry.enabled, true);
  assert.equal(entry.disabled, false);
  assert.equal(entry.bearer_token_env_var, 'MISAKANET_TOKEN');
  assert.deepEqual(entry.enabled_tools, []);

  const rules = readFileSync(join(project, 'AGENTS.md'), 'utf8');
  assert.match(rules, /misakanet:start/);
  assert.match(rules, /misakanet_search/);
  assert.match(result.stdout, /MISAKANET_TOKEN/, 'the env-var step must be stated, not hidden');
});

test('codewhale without a trusted project says so instead of writing nowhere', () => {
  const home = makeHome({ claude: false, codex: false });
  mkdirSync(join(home, '.codewhale'), { recursive: true });
  writeFileSync(join(home, '.codewhale', 'config.toml'), 'api_key = "seed"\n');

  const result = runOffline(home, '--only', 'codewhale');
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /没有受信任的项目目录/, result.stdout);
  assert.ok(existsSync(join(home, '.codewhale', 'mcp.json')), 'MCP registration still lands');
});

test('uninstall removes the codewhale registration and rules block', () => {
  const home = makeHome({ claude: false, codex: false });
  const project = join(home, 'work', 'proj');
  mkdirSync(project, { recursive: true });
  mkdirSync(join(home, '.codewhale'), { recursive: true });
  writeFileSync(join(home, '.codewhale', 'config.toml'),
    `[projects."${project}"]\ntrust_level = "trusted"\n`);
  runOffline(home, '--only', 'codewhale');
  assert.ok(existsSync(join(project, 'AGENTS.md')));

  const removed = runOffline(home, '--uninstall');
  assert.equal(removed.status, 0, removed.stderr);
  const mcpText = readFileSync(join(home, '.codewhale', 'mcp.json'), 'utf8');
  assert.ok(!mcpText.includes('misakanet'), `no trace of ours may remain: ${mcpText}`);
  // This home had no `mcp.json` at all, so the install created it with its own defaults. The file
  // stays (it may hold settings the user added since), but nothing of ours does: the entry is gone
  // and the container it lived in is pruned once it is empty.
  assert.equal(JSON.parse(mcpText).servers, undefined, 'the emptied servers container goes too');
});

// ── the voice hook is opt-in (and needs a matcher to fire at all) ─────────────
// Two things were measured on a real machine rather than assumed (2026-09-16):
//  * a PostToolUse entry **without** `matcher` never fired, while `matcher: '*'` did — so the
//    installer must write the matcher, or it ships a hook that silently never runs;
//  * the host passes the MCP result as `tool_response`, and for MCP tools that value is a JSON
//    *string* — hence the player parses nested JSON (covered in agent-autostart-hook.test.mjs).
test('the voice hook is off by default and switched on with --voice', () => {
  const home = makeHome();
  const off = runOffline(home);
  assert.equal(off.status, 0, off.stderr);
  const settingsOff = JSON.parse(readFileSync(join(home, '.claude', 'settings.json'), 'utf8'));
  assert.equal(settingsOff.hooks.PostToolUse, undefined, 'default install must stay silent');
  assert.match(off.stdout, /语音钩子：未开启/, off.stdout);

  const on = runOffline(home, '--voice');
  assert.equal(on.status, 0, on.stderr);
  const settings = JSON.parse(readFileSync(join(home, '.claude', 'settings.json'), 'utf8'));
  const entry = (settings.hooks.PostToolUse || []).find((e) => JSON.stringify(e).includes('voice-hook'));
  assert.ok(entry, `PostToolUse missing the voice hook: ${JSON.stringify(settings.hooks)}`);
  assert.equal(entry.matcher, '*', 'without a matcher the host never fires the hook');
  assert.ok(existsSync(join(home, '.misakanet-agent', 'voice', 'voice-hook.mjs')),
    'the player must be copied into the state dir (an npx cache is not a home for a hook)');
  const cues = readdirSync(join(home, '.misakanet-agent', 'voice')).filter((f) => f.endsWith('.mp3'));
  assert.ok(cues.length >= 4, `expected the cues to be copied, got ${cues.join(',')}`);
});

test('uninstall removes the voice hook entry and its files', () => {
  const home = makeHome();
  runOffline(home, '--voice');
  assert.ok(existsSync(join(home, '.misakanet-agent', 'voice')));

  const removed = runOffline(home, '--uninstall');
  assert.equal(removed.status, 0, removed.stderr);
  const settings = JSON.parse(readFileSync(join(home, '.claude', 'settings.json'), 'utf8'));
  const leftovers = JSON.stringify(settings.hooks.PostToolUse || []);
  assert.ok(!leftovers.includes('voice-hook'), leftovers);
  assert.ok(!existsSync(join(home, '.misakanet-agent', 'voice')), 'the player and cues must go too');
});

test('a voice entry left by 0.4.2 (no matcher) is upgraded, not kept', () => {
  // 0.4.2 wrote the PostToolUse entry without `matcher`, and such an entry never fires. A
  // re-run must fix it rather than conclude "voice hook already present" and leave it mute.
  const home = makeHome();
  const settingsPath = join(home, '.claude', 'settings.json');
  const seeded = JSON.parse(readFileSync(settingsPath, 'utf8'));
  seeded.hooks.PostToolUse = [{ hooks: [{ type: 'command', command: '"/usr/bin/node" "/home/u/.misakanet-agent/voice/voice-hook.mjs"' }] }];
  writeFileSync(settingsPath, JSON.stringify(seeded));

  const result = runOffline(home, '--voice');
  assert.equal(result.status, 0, result.stderr);
  const after = JSON.parse(readFileSync(settingsPath, 'utf8'));
  const entries = after.hooks.PostToolUse.filter((e) => JSON.stringify(e).includes('voice-hook'));
  assert.equal(entries.length, 1, `expected exactly one entry: ${JSON.stringify(after.hooks.PostToolUse)}`);
  assert.equal(entries[0].matcher, '*', 'the stale entry must gain the matcher');
});

// ── --report: evidence a stranger can paste in public ─────────────────────────
// The bounty asks other machines to install and report back. A report assembled by hand arrives
// rarely and usually contains a token, so the installer prints its own — redacted by
// construction: the token value never appears (only present/absent), home paths are written as
// `~`, and the banner (which names the home directory) is suppressed in this mode.
function reportLines(out) {
  const fields = {};
  for (const line of out.split('\n')) {
    const m = /^([a-z-]+):\s*(.*)$/.exec(line.trim());
    if (m) fields[m[1]] = m[2];
  }
  return fields;
}

test('--report prints a redacted, machine-parsable report', () => {
  const home = makeHome();
  runOffline(home);
  const result = runOffline(home, '--report');
  assert.equal(result.status, 0, result.stderr);

  const fields = reportLines(result.stdout);
  assert.equal(fields.schema, 'misakanet-setup-report/1');
  assert.match(fields['setup-version'], /^\d+\.\d+\.\d+$/);
  assert.match(fields.os, /^(linux|macos|windows|wsl2)$/);
  assert.match(fields.node, /^v\d+\./);
  assert.ok(fields['detected-agents'].includes('claude'), fields['detected-agents']);
  assert.match(fields.verify, /^(READY|NOT READY)$/);
  assert.match(fields.token, /^(present|absent)$/);
  assert.match(fields.voice, /^(on|off|absent|stale|unknown)$/);
  assert.ok('tools-visible' in fields && 'live-call-evidence' in fields,
    'the two fields only the reporter can fill must be present as blanks');
});

test('--report leaks neither the token nor the home path', () => {
  const home = makeHome();
  runOffline(home);                       // installs the config surfaces
  // runOffline passes --no-register, so no token is minted: seed one, because a report that
  // leaks it is the failure this test exists for.
  mkdirSync(join(home, '.misakanet-agent'), { recursive: true });
  writeFileSync(join(home, '.misakanet-agent', 'token'), `${STUB_TOKEN}\n`);
  const token = STUB_TOKEN;
  assert.ok(token.length > 8, 'the fixture should have a token to leak');

  const result = runOffline(home, '--report');
  assert.ok(!result.stdout.includes(token), 'the token value must never be printed');
  assert.ok(!result.stdout.includes(home), `the home path must not appear: ${result.stdout}`);
  assert.ok(!/Bearer [A-Za-z0-9_.-]{8,}/.test(result.stdout), result.stdout);
  assert.equal(reportLines(result.stdout).token, 'present', 'presence is reported, not the value');
});

// ── --report --strict: the same YAML as a CI gate (issue #1782) ───────────────
// One report, two contracts. The default form must stay exit-0 (people paste it into issues and
// pipe it into logs); the strict form is the gate: 0 = READY, 1 = NOT READY (including
// `open-items > 0`), 2 = the report could not be produced at all. That is deliberately the same
// 0/1/2 convention as scripts/check_workflow_scripts.py ("0 = fine, 1 = found problems,
// 2 = could not run"). `run()` points the endpoint at a dead port, so NOT READY here is a
// property of the fixture, not of the network.
test('--report exits 0 even when the machine is NOT READY (the paste-safe default)', () => {
  const home = makeHome();
  // The same home, judged the two ways: --verify is already a gate (exit 1) and must stay one,
  // while --report prints the identical verdict as evidence and still exits 0.
  const verdict = run(home, '--verify');
  assert.equal(verdict.status, 1, verdict.stdout + verdict.stderr);

  const result = run(home, '--report');
  assert.equal(result.status, 0,
    `the default report must stay exit-0 or every existing use breaks: ${result.stderr}`);
  assert.equal(reportLines(result.stdout).verify, 'NOT READY',
    'exit 0 must not be achieved by pretending the machine is ready');
  assert.ok(Number(reportLines(result.stdout)['open-items']) > 0, result.stdout);
});

test('--report --strict exits 1 when the report says NOT READY', () => {
  const home = makeHome();
  const result = run(home, '--report', '--strict');
  assert.equal(result.status, 1, result.stdout + result.stderr);

  const fields = reportLines(result.stdout);
  assert.equal(fields.verify, 'NOT READY');
  assert.ok(Number(fields['open-items']) > 0, `open-items must be positive: ${result.stdout}`);
  // The evidence still has to come out: CI appends this YAML to the job summary *and* fails the
  // step, so a gate that printed nothing would be unusable.
  assert.equal(fields.schema, 'misakanet-setup-report/1');
  assert.match(result.stderr, /退出码 1/, result.stderr);
});

test('--ci is the same gate as --report --strict', () => {
  const home = makeHome();
  const ci = run(home, '--ci');
  const explicit = run(home, '--report', '--strict');
  assert.equal(ci.status, explicit.status, `--ci and --report --strict must agree: ${ci.stdout}`);
  assert.equal(ci.status, 1, ci.stdout + ci.stderr);
  assert.equal(reportLines(ci.stdout).schema, 'misakanet-setup-report/1',
    '--ci alone must select report mode (not install mode)');
});

test('--report --strict exits 2 when the report cannot be produced at all', () => {
  // "Could not run" needs a real construction, not a mock: verify() reads the Claude hooks to
  // find the hook command, and an event entry whose `hooks` is not an array (a hand-edited
  // settings.json shape this tool cannot interpret) throws before any verdict exists. Before
  // #1782 that exit code was 1 with a stack trace — indistinguishable from a genuine NOT READY.
  const home = makeHome();
  run(home);                              // offline install, so ~/.misakanet-agent/hook.mjs exists
  assert.ok(existsSync(join(home, '.misakanet-agent', 'hook.mjs')), 'fixture: hook must be installed');
  writeFileSync(join(home, '.claude', 'settings.json'),
    JSON.stringify({ hooks: { Stop: [{ hooks: 5 }] } }));

  const result = run(home, '--report', '--strict');
  assert.equal(result.status, 2, result.stdout + result.stderr);
  assert.equal(result.stdout.trim(), '',
    'nothing may be printed as a report when there is no report: a half YAML would be pasted');
  assert.match(result.stderr, /退出码 2/, result.stderr);
  assert.match(result.stderr, /退出码 2[\s\S]*map is not a function/, result.stderr);
  // and the crash must not be dressed up as a verdict
  assert.ok(!/NOT READY/.test(result.stderr), result.stderr);
});

test('--report --strict exits 0 on a READY machine, and the human fields never gate it', async () => {
  // The two blank fields (`tools-visible`, `live-call-evidence`) are filled in by a person after
  // the fact. A gate that depends on the reporter remembering to do that is not a gate, so a
  // READY machine with both fields still empty must pass.
  const { createServer } = await import('node:http');
  const server = createServer((req, res) => {
    let body = '';
    req.on('data', (c) => { body += c; });
    req.on('end', () => {
      const payload = JSON.parse(body || '{}');
      const result = payload.method === 'tools/list'
        ? { tools: [{ name: 'misakanet_search' }, { name: 'misakanet_get_lesson' }] }
        : payload.params?.name === 'misakanet_register'
          ? { node_id: 'MisakaTEST', token: TOKEN_SHAPE_OK }
          : { results: [{ id: 'stub', type: 'lesson' }] };
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ jsonrpc: '2.0', id: 1, result: {
        content: [{ type: 'text', text: JSON.stringify(result) }], structuredContent: result } }));
    });
  });
  await new Promise((done) => server.listen(0, '127.0.0.1', done));
  const url = `http://127.0.0.1:${server.address().port}/mcp`;
  // The registry lookup stays inside the stub too, so the test never needs the real network.
  const env = { ...process.env, MISAKANET_ENDPOINT: url, MISAKANET_REGISTRY_URL: url };

  try {
    const home = makeHome();
    const install = await runAsync(home, env);
    assert.equal(install.status, 0, install.stdout + install.stderr);

    const result = await runAsync(home, env, '--report', '--strict');
    assert.equal(result.status, 0, result.stdout + result.stderr);
    const fields = reportLines(result.stdout);
    assert.equal(fields.verify, 'READY');
    assert.equal(fields['open-items'], '0');
    assert.match(fields['tools-visible'], /^\{\}/, fields['tools-visible']);
    assert.match(fields['live-call-evidence'], /^""/, fields['live-call-evidence']);
  } finally {
    server.close();
  }
});

// ── --silent + --report-json: the enterprise/MDM form (issue #1784) ───────────
// The audience here is not the person who reads the docs, it is the IT department that pushes the
// installer through GPO / Intune / Jamf / Ansible (docs/maintainer/enterprise-deployment.md). Two
// things follow, and both are pinned below:
//
//   * `--silent` removes *progress*, not information. The ✓/· narration, the banner (which names
//     the local home directory) and the closing guidance go; the `!` lines, the report and the
//     exit codes stay. An installer that failed quietly would be undebuggable in the field.
//   * `--report-json` is the *same* report in the other encoding, and it is the entire stdout —
//     an MDM does JSON.parse on that stream, so one stray banner line breaks it. It is printed
//     even when the machine is NOT READY, because that is the machine they are collecting data
//     about.

/** How the YAML encoder writes a value — used to prove the two encodings carry the same data. */
function yamlEncoded(value) {
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (Array.isArray(value)) return `[${value.join(', ')}]`;
  if (value && typeof value === 'object') return '{}';
  if (value === '') return '""';
  return String(value);
}

/** `reportLines` keeps the trailing `# comment` of the two human fields; the value is what precedes it. */
function yamlValue(raw) {
  return String(raw).replace(/\s+#.*$/, '').trim();
}

test('--silent drops the progress narration, and keeps the exit code working', () => {
  const home = makeHome();
  const loud = runOffline(home, '--dry-run');
  assert.equal(loud.status, 0, loud.stdout + loud.stderr);
  // The baseline really does narrate, or the assertions below would prove nothing.
  assert.match(loud.stdout, /已完成/);
  assert.match(loud.stdout, /接下来：/);
  assert.match(loud.stdout, /家目录：/);

  const home2 = makeHome();
  const quiet = runOffline(home2, '--dry-run', '--silent');
  assert.equal(quiet.status, 0, quiet.stdout + quiet.stderr);
  assert.ok(!/已完成/.test(quiet.stdout), quiet.stdout);
  assert.ok(!/接下来：/.test(quiet.stdout), quiet.stdout);
  assert.ok(!/✓|·/.test(quiet.stdout), `no ✓/· narration may survive: ${quiet.stdout}`);
  assert.ok(!/家目录：/.test(quiet.stdout),
    `the banner names the local home path, which a GPO log should not collect: ${quiet.stdout}`);
});

test('--silent is not mute: the errors and the "a human must do this" lines still print', () => {
  // A config the installer itself cannot parse: the run cannot fix it, so it has to say so. This is
  // the line a deployment log exists for, and it must survive --silent.
  const home = makeHome();
  writeFileSync(join(home, '.claude.json'), '{ this is not json');
  const quiet = run(home, '--silent');
  assert.equal(quiet.status, 0, quiet.stdout + quiet.stderr);
  assert.match(quiet.stdout, /! /, `an error must survive --silent: ${quiet.stdout}`);
  assert.match(quiet.stdout, /不是合法 JSON/);
  assert.ok(!/✓/.test(quiet.stdout), `but the narration must not come back with it: ${quiet.stdout}`);
});

test('--silent still prints the report — that is the one thing it must never mute', () => {
  // Both encodings, because a deployment picks one and has to be able to trust the other.
  const home = makeHome();
  runOffline(home);
  const yaml = run(home, '--silent', '--report');
  assert.equal(yaml.status, 0, yaml.stdout + yaml.stderr);
  assert.match(yaml.stdout, /schema: misakanet-setup-report\/1/, yaml.stdout);
  assert.ok(!/已完成|接下来：|家目录：/.test(yaml.stdout), yaml.stdout);

  const json = run(home, '--silent', '--report-json');
  assert.equal(json.status, 0, json.stdout + json.stderr);
  assert.equal(JSON.parse(json.stdout).schema, 'misakanet-setup-report/1');
});

test('--silent --report-json leaves exactly one JSON document on stdout', () => {
  const home = makeHome();
  runOffline(home);                       // a real install, so the report has facts to carry
  const result = run(home, '--silent', '--report-json');
  assert.equal(result.status, 0, result.stdout + result.stderr);
  // JSON.parse over the WHOLE stdout is the assertion: a banner line or a second document would
  // throw here, which is exactly what it would do in an MDM's parser.
  const payload = JSON.parse(result.stdout);
  assert.equal(payload.schema, 'misakanet-setup-report/1');
  assert.equal(payload.verify, 'NOT READY', 'a NOT READY machine still gets its JSON (#1784)');
  assert.ok(payload['open-items'] > 0, result.stdout);
  assert.ok(Array.isArray(payload['open-items-detail']), result.stdout);
  assert.deepEqual(payload['detected-agents'], ['claude', 'codex'], JSON.stringify(payload));
});

test('--report-json is valid JSON to a non-JS parser too (json.load)', (t) => {
  // The issue's wording is "an MDM can parse it", and an MDM may well be Python. `JSON.parse` and
  // `json.load` agree on everything this report can contain, but that is an argument, not a test —
  // the repo runs both runtimes, so the cheap thing is to actually hand it to Python.
  const python = spawnSync('python3', ['-c', 'import sys'], { encoding: 'utf8' });
  if (python.error || python.status !== 0) return t.skip('no python3 on this machine');

  const home = makeHome();
  runOffline(home);
  const result = run(home, '--silent', '--report-json');
  assert.equal(result.status, 0, result.stdout + result.stderr);

  const loaded = spawnSync('python3', ['-c',
    'import json,sys; d=json.load(sys.stdin); print(d["schema"], d["open-items"])',
  ], { input: result.stdout, encoding: 'utf8' });
  assert.equal(loaded.status, 0, `python could not load the report: ${loaded.stderr}`);
  const [schema, openItems] = loaded.stdout.trim().split(' ');
  assert.equal(schema, 'misakanet-setup-report/1');
  assert.equal(Number(openItems), Number(JSON.parse(result.stdout)['open-items']),
    'the two parsers must read the same report');
  return undefined;
});

test('--report-json is the same data as --report, field by field', () => {
  // "The JSON encoding of the same report" is only true if both encodings are printed from one
  // object. This compares every field of the JSON against the YAML line of the same name.
  const home = makeHome();
  runOffline(home);
  const yaml = run(home, '--report');
  const json = run(home, '--report-json');
  assert.equal(yaml.status, json.status, yaml.stdout + json.stdout);
  assert.equal(yaml.status, 0);

  const fields = reportLines(yaml.stdout);
  const payload = JSON.parse(json.stdout);
  for (const [key, value] of Object.entries(payload)) {
    if (key === 'open-items-detail') continue;
    assert.ok(key in fields, `${key} is in the JSON but has no YAML line`);
    assert.equal(yamlValue(fields[key]), yamlEncoded(value),
      `${key} disagrees between the two encodings: YAML "${fields[key]}" / JSON ${JSON.stringify(value)}`);
  }
  for (const key of Object.keys(fields)) {
    assert.ok(key in payload, `${key} is in the YAML but missing from the JSON`);
  }
  // The open items are the one field with a different shape (YAML block list, JSON array), so they
  // get their own check — including the count, which is what the strict gate reads.
  const blocks = yaml.stdout.split('\n').filter((l) => /^ {2}- /.test(l)).map((l) => l.slice(4));
  assert.deepEqual(blocks, payload['open-items-detail']);
  assert.equal(blocks.length, payload['open-items']);
  assert.ok(blocks.length > 0, 'the fixture must have open items, or this proves nothing');
});

test('--silent --report-json --strict returns 1 on a NOT READY home, JSON and all', () => {
  const home = makeHome();
  const result = run(home, '--silent', '--report-json', '--strict');
  assert.equal(result.status, 1, result.stdout + result.stderr);
  // The gate prints its evidence before it fails: an MDM that only kept the exit code would have
  // nothing to show, which is why the JSON is not replaced by the stderr line.
  const payload = JSON.parse(result.stdout);
  assert.equal(payload.verify, 'NOT READY');
  assert.ok(payload['open-items'] > 0);
  assert.match(result.stderr, /退出码 1/, result.stderr);
  assert.match(result.stderr, /JSON 就是证据/, 'the verdict line must name the encoding it printed');
});

test('--silent --report-json --strict returns 0 on a READY machine, silently', async () => {
  const { createServer } = await import('node:http');
  const server = createServer((req, res) => {
    let body = '';
    req.on('data', (c) => { body += c; });
    req.on('end', () => {
      const payload = JSON.parse(body || '{}');
      const result = payload.method === 'tools/list'
        ? { tools: [{ name: 'misakanet_search' }, { name: 'misakanet_get_lesson' }] }
        : payload.params?.name === 'misakanet_register'
          ? { node_id: 'MisakaTEST', token: TOKEN_SHAPE_OK }
          : { results: [] };
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ jsonrpc: '2.0', id: 1, result: {
        content: [{ type: 'text', text: JSON.stringify(result) }], structuredContent: result } }));
    });
  });
  await new Promise((done) => server.listen(0, '127.0.0.1', done));
  const url = `http://127.0.0.1:${server.address().port}/mcp`;
  const env = { ...process.env, MISAKANET_ENDPOINT: url, MISAKANET_REGISTRY_URL: url };

  try {
    const home = makeHome();
    const install = await runAsync(home, env);
    assert.equal(install.status, 0, install.stdout + install.stderr);

    const result = await runAsync(home, env, '--silent', '--report-json', '--strict');
    assert.equal(result.status, 0, result.stdout + result.stderr);
    const payload = JSON.parse(result.stdout);
    assert.equal(payload.verify, 'READY');
    assert.equal(payload['open-items'], 0);
    assert.deepEqual(payload['open-items-detail'], []);
    assert.equal(result.stderr, '', 'a healthy silent run must say nothing at all on stderr');
  } finally {
    server.close();
  }
});

test('--silent --report-json --strict returns 2, and prints no half a JSON document', () => {
  // Same construction as the YAML case: a settings.json shape this tool cannot interpret makes the
  // report impossible. 2 is "could not run", and an MDM must not be handed `{}` for it — that would
  // parse, and would be read as a clean machine.
  const home = makeHome();
  run(home);
  writeFileSync(join(home, '.claude', 'settings.json'),
    JSON.stringify({ hooks: { Stop: [{ hooks: 5 }] } }));

  const result = run(home, '--silent', '--report-json', '--strict');
  assert.equal(result.status, 2, result.stdout + result.stderr);
  assert.equal(result.stdout.trim(), '', `no partial JSON may be printed: ${result.stdout}`);
  assert.match(result.stderr, /退出码 2/, result.stderr);
});

test('--silent composes with --only: one agent, and nothing to say on success', () => {
  const home = makeHome();
  const result = runOffline(home, '--silent', '--only', 'claude');
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.equal(result.stdout.trim(), '',
    `a clean silent run is an empty log: ${result.stdout}`);
  const claude = JSON.parse(readFileSync(join(home, '.claude.json'), 'utf8'));
  assert.equal(claude.mcpServers.misakanet.url, 'https://misakanet.org/mcp');
  assert.ok(!existsSync(join(home, '.codex', 'AGENTS.md')), '--only claude must not touch codex');
});

test('--silent + --report-json + --only do not conflict (and --only does not narrow the report)', () => {
  // `--only` is an install-time selector; the report describes the *machine*. Asserting the
  // distinction keeps a future "let --only filter the report" change from silently making a
  // Codex-only machine look like a Claude-only one.
  const home = makeHome();
  const result = run(home, '--silent', '--report-json', '--only', 'claude', '--strict');
  assert.equal(result.status, 1, result.stdout + result.stderr);
  const payload = JSON.parse(result.stdout);
  assert.deepEqual(payload['detected-agents'], ['claude', 'codex'], JSON.stringify(payload));
});

test('--silent composes with --uninstall, which still removes everything', () => {
  const home = makeHome();
  runOffline(home);
  const result = runOffline(home, '--silent', '--uninstall');
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.ok(!/✓/.test(result.stdout), `uninstall's narration must be hidden: ${result.stdout}`);
  assert.ok(!/已恢复原状/.test(result.stdout), result.stdout);
  // Hermes' hook is not ours to remove, so that one `!` line is information, not progress.
  assert.match(result.stdout, /! /, `the manual note must survive: ${result.stdout}`);
  assert.ok(!existsSync(join(home, '.claude', 'CLAUDE.md'))
    || !readFileSync(join(home, '.claude', 'CLAUDE.md'), 'utf8').includes('misakanet:start'),
  'the rules block must still be gone under --silent');
});

// ── pre-allowed read tools: the first search must not be denied ───────────────
// Reported from a macOS field test and reproduced here: with only the built-in tools allowed,
// Claude Code answers the first `misakanet_search` with "you haven't granted it yet", and the new
// user's first experience of the product is a permission refusal. The installer now grants the
// read-only tools (search/get_lesson/me_events/preflight/submit_intake) and deliberately not
// write_lesson, which is the Bearer-gated authoring path.
test('the installer pre-allows the read-only MCP tools, and only those', () => {
  const home = makeHome();
  // The fixture gets the shape a real user has (the macOS field report showed exactly this:
  // defaultMode + a hand-kept list of built-ins), so "merge, never overwrite" is actually tested.
  const seeded = JSON.parse(readFileSync(join(home, '.claude', 'settings.json'), 'utf8'));
  seeded.permissions = { defaultMode: 'acceptEdits', allow: ['Bash', 'Read'] };
  writeFileSync(join(home, '.claude', 'settings.json'), JSON.stringify(seeded));
  const result = runOffline(home);
  assert.equal(result.status, 0, result.stderr);

  const settings = JSON.parse(readFileSync(join(home, '.claude', 'settings.json'), 'utf8'));
  const allow = settings.permissions.allow;
  for (const tool of ['mcp__misakanet__misakanet_search', 'mcp__misakanet__misakanet_get_lesson',
    'mcp__misakanet__misakanet_me_events', 'mcp__misakanet__misakanet_preflight',
    'mcp__misakanet__misakanet_submit_intake']) {
    assert.ok(allow.includes(tool), `${tool} must be allowed: ${JSON.stringify(allow)}`);
  }
  assert.ok(!allow.includes('mcp__misakanet__misakanet_write_lesson'),
    'a tool that writes must still ask');
  assert.ok(allow.includes('Bash') && allow.includes('Read'),
    `the user's own allow-list must survive: ${JSON.stringify(allow)}`);
  const after = JSON.parse(readFileSync(join(home, '.claude', 'settings.json'), 'utf8'));
  assert.equal(after.permissions.defaultMode, 'acceptEdits', 'the user permission mode must survive');
});

test('a second run does not duplicate the grants, and uninstall removes them', () => {
  const home = makeHome();
  const seeded = JSON.parse(readFileSync(join(home, '.claude', 'settings.json'), 'utf8'));
  seeded.permissions = { allow: ['Bash'] };
  writeFileSync(join(home, '.claude', 'settings.json'), JSON.stringify(seeded));
  runOffline(home);
  const first = JSON.parse(readFileSync(join(home, '.claude', 'settings.json'), 'utf8')).permissions.allow;
  runOffline(home);
  const second = JSON.parse(readFileSync(join(home, '.claude', 'settings.json'), 'utf8')).permissions.allow;
  assert.deepEqual(second, first, 're-running must not append duplicates');

  runOffline(home, '--uninstall');
  const after = JSON.parse(readFileSync(join(home, '.claude', 'settings.json'), 'utf8')).permissions.allow;
  assert.ok(!after.some((tool) => tool.startsWith('mcp__misakanet__')),
    `uninstall must drop our grants: ${JSON.stringify(after)}`);
  assert.ok(after.includes('Bash'), "the user's own entries must stay");
});

// ── findings from the open-code-review scan of this installer (2026-09-16) ────
test('the first backup is never overwritten by a later run', () => {
  // Keep-the-first semantics: after a regression the user re-runs the installer, and that second
  // run used to overwrite the only known-good copy of their config.
  const home = makeHome();
  const bak = join(home, '.claude', 'CLAUDE.md.misakanet.bak');
  mkdirSync(join(home, '.claude'), { recursive: true });
  writeFileSync(bak, 'SENTINEL: the user\'s original config\n');
  writeFileSync(join(home, '.claude', 'CLAUDE.md'), 'user rules\n');

  const first = runOffline(home);
  assert.equal(first.status, 0, first.stdout + first.stderr);
  assert.match(readFileSync(bak, 'utf8'), /SENTINEL/, 'the pre-existing backup must survive run 1');

  const second = runOffline(home);
  assert.equal(second.status, 0, second.stdout + second.stderr);
  assert.match(readFileSync(bak, 'utf8'), /SENTINEL/, 'and run 2 must not clobber it either');
});

test('a config whose keys are reordered is not rewritten', () => {
  // `JSON.stringify(a) === JSON.stringify(b)` is key-order-sensitive, so an editor that reordered
  // keys made the installer rewrite an unchanged file and take a pointless backup.
  const home = makeHome();
  const cfg = join(home, '.claude.json');
  // Seed from what the installer itself writes, then reorder the entry's keys: hardcoding the entry
  // shape made this test fail the moment the shape grew headers, which is not what it is about.
  runOffline(home);
  const doc = JSON.parse(readFileSync(cfg, 'utf8'));
  const reorderedEntry = Object.fromEntries(Object.entries(doc.mcpServers.misakanet).reverse());
  const seeded = JSON.stringify({ mcpServers: { misakanet: reorderedEntry, existing: doc.mcpServers.existing } });
  writeFileSync(cfg, seeded);

  const result = runOffline(home);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.equal(readFileSync(cfg, 'utf8'), seeded,
    'same fields in another key order must count as "no change"');
});

test('the Hermes token file is not world-readable', { skip: process.platform === 'win32' }, async () => {
  const { createServer } = await import('node:http');
  const { statSync } = await import('node:fs');
  const server = createServer((req, res) => {
    let body = '';
    req.on('data', (c) => { body += c; });
    req.on('end', () => {
      const payload = JSON.parse(body || '{}');
      const result = payload.params?.name === 'misakanet_register'
        ? { node_id: 'MisakaTEST', token: TOKEN_SHAPE_OK }
        : { tools: [{ name: 'misakanet_search' }] };
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ jsonrpc: '2.0', id: 1, result: {
        content: [{ type: 'text', text: JSON.stringify(result) }], structuredContent: result } }));
    });
  });
  await new Promise((done) => server.listen(0, '127.0.0.1', done));
  const url = `http://127.0.0.1:${server.address().port}/mcp`;
  try {
    const home = makeHome();
    mkdirSync(join(home, '.hermes'), { recursive: true });
    writeFileSync(join(home, '.hermes', 'config.yaml'), 'model:\n  default: MiniMax-M3\n');
    const install = await runAsync(home, { ...process.env, MISAKANET_ENDPOINT: url });
    assert.equal(install.status, 0, install.stdout + install.stderr);

    const envPath = join(home, '.hermes', '.env');
    assert.ok(existsSync(envPath), 'the token should reach the Hermes env file');
    assert.match(readFileSync(envPath, 'utf8'), /MCP_MISAKANET_API_KEY/);
    assert.equal(statSync(envPath).mode & 0o777, 0o600,
      'the standalone token file is 600; the copy pasted into .env must not be world-readable');
  } finally {
    server.close();
  }
});

test('verify names the reason the endpoint probe failed', () => {
  // Returning bare {} made a timeout, a TLS failure and an empty result identical, so the user was
  // told "endpoint unreachable" whatever actually happened.
  const home = makeHome();
  const result = run(home, '--verify');
  assert.equal(result.status, 1);
  assert.match(result.stdout, /端点不可达/);
  assert.match(result.stdout, /最近一次失败原因/, 'the failure reason must reach the user');
});

// ── hook ownership ───────────────────────────────────────────────────────────
// Until 2026-09-17 install/uninstall/verify decided "is this our hook?" by searching the
// entry for the substring `hook.mjs`. A user's own `my-hook.mjs` therefore looked like ours:
// `--uninstall` deleted it (reproduced on a real HOME) while
// packages/misakanet-setup/README.md promised "leaves your own hooks alone (covered by
// tests)" — the fixture above only ever used a hook named `echo hi`, so the case was never
// exercised. Ownership is now the state directory every command of ours points into.
test("uninstall keeps the user's own hook when its command mentions a *-hook.mjs file", () => {
  const home = makeHome();
  const settingsPath = join(home, '.claude', 'settings.json');
  const settings = JSON.parse(readFileSync(settingsPath, 'utf8'));
  settings.hooks.UserPromptSubmit = [
    { hooks: [{ type: 'command', command: 'node /home/me/.my-tools/my-hook.mjs prompt' }] },
  ];
  writeFileSync(settingsPath, JSON.stringify(settings, null, 2));

  runOffline(home);
  const afterInstall = JSON.parse(readFileSync(settingsPath, 'utf8'));
  const installed = Object.values(afterInstall.hooks).flat()
    .flatMap((e) => (e.hooks || []).map((h) => h.command));
  assert.ok(
    installed.some((c) => c.includes('.misakanet-agent')),
    'a foreign hook must not make install believe ours is already there',
  );
  assert.ok(installed.some((c) => c.includes('my-hook.mjs')), 'the foreign hook stays');

  runOffline(home, '--uninstall');
  const afterUninstall = JSON.parse(readFileSync(settingsPath, 'utf8'));
  const commands = Object.values(afterUninstall.hooks || {}).flat()
    .flatMap((e) => (e.hooks || []).map((h) => h.command));
  assert.ok(
    commands.some((c) => c.includes('my-hook.mjs')),
    "uninstall deleted the user's own hook — ownership must be the state dir, not the file name",
  );
  assert.ok(!commands.some((c) => c.includes('.misakanet-agent')), 'our own hooks are removed');
});

test('uninstall restores a user rule file byte for byte (no stray newline)', () => {
  const home = makeHome();
  const rulePath = join(home, '.claude', 'CLAUDE.md');
  const original = '# 我的配置\n\n我自己的规则。\n';
  writeFileSync(rulePath, original);

  runOffline(home);
  assert.ok(readFileSync(rulePath, 'utf8').includes('misakanet:start'), 'install adds our block');

  runOffline(home, '--uninstall');
  assert.equal(
    readFileSync(rulePath, 'utf8'),
    original,
    'uninstall left the file longer than it was: the claim "已恢复原状" must hold',
  );
});

test('verify does not credit a foreign hook that merely mentions hook.mjs', () => {
  const home = makeHome();
  runOffline(home);
  // Our state hook exists, but settings.json now holds only somebody else's hook.
  writeFileSync(
    join(home, '.claude', 'settings.json'),
    JSON.stringify({ hooks: { UserPromptSubmit: [{ hooks: [{ type: 'command', command: 'node /home/me/my-hook.mjs' }] }] } }),
  );
  const result = runOffline(home, '--verify');
  assert.match(
    result.stdout,
    /钩子没装|没有本安装器写入的命令/,
    'a foreign hook must not make --verify report our hook as installed',
  );
  assert.doesNotMatch(result.stdout, /钩子已装且解释器存在/);
});

// ── exit codes and the argument surface ──────────────────────────────────────
// Install mode used to end without any `process.exit`: every outcome returned 0. A script
// (`npx … && echo ok`, a GPO/MDM wrapper, CI) therefore could not tell a real install from a
// run that changed nothing. The contract is now 0 = at least one agent configured,
// 1 = nothing installed, 2 = the installer could not run.
test('a successful install exits 0', () => {
  const home = makeHome();
  const result = runOffline(home);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test('a target that cannot be written is reported and does not skip the others', () => {
  const home = makeHome();
  // Claude's settings.json is made unwritable by turning it into a directory, so that target
  // must fail while codex still gets configured. Before, an uncaught throw aborted the loop.
  const settingsPath = join(home, '.claude', 'settings.json');
  rmSync(settingsPath, { force: true });
  mkdirSync(settingsPath);

  const result = runOffline(home);
  assert.match(result.stdout, /写入配置失败/, result.stdout);
  assert.match(result.stdout, /claude/, result.stdout);
  assert.ok(
    readFileSync(join(home, '.codex', 'config.toml'), 'utf8').includes('misakanet'),
    'the remaining targets must still be installed',
  );
  assert.equal(result.status, 0, 'one target failing is not a failed install');
});

test('--help prints usage and writes nothing', () => {
  const home = makeHome();
  const before = snapshot(home);
  const result = runOffline(home, '--help');
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout, /用法：npx @misaka-net\/misakanet-setup/);
  assert.match(result.stdout, /--version/);
  assert.deepEqual(snapshot(home), before, '--help must not install anything');
});

test('--version prints the version and writes nothing', () => {
  const home = makeHome();
  const before = snapshot(home);
  const result = runOffline(home, '--version');
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const pkg = JSON.parse(readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), '..', 'packages', 'misakanet-setup', 'package.json'), 'utf8'));
  assert.equal(result.stdout.trim(), pkg.version, 'the printed version must match the manifest');
  assert.deepEqual(snapshot(home), before);
});

test('an unknown flag stops with exit 2 and writes nothing', () => {
  const home = makeHome();
  const before = snapshot(home);
  const result = runOffline(home, '--bogus');
  assert.equal(result.status, 2, 'an unrecognised flag must not be silently ignored');
  assert.match(result.stderr, /无法识别的选项/);
  assert.deepEqual(snapshot(home), before);
});

test('a value flag with no value stops instead of installing into a directory named like the flag', () => {
  const home = makeHome();
  const before = snapshot(home);
  // Not runOffline(): this one deliberately omits the standard `--home <home>` prefix.
  const result = spawnSync(process.execPath, [CLI, '--home', '--voice'], { encoding: 'utf8' });
  assert.equal(result.status, 2, '--home must not fall back to the real HOME');
  assert.match(result.stderr, /--home 需要一个值/);
  assert.ok(!existsSync(join(process.cwd(), '--voice')), 'no directory named after the flag');
  assert.deepEqual(snapshot(home), before);
});

// ── config writes: atomic, permission-checked, and honest about consequences ──────────────
// A direct `writeFileSync` is not atomic, and the files here are the user's assistant config: a
// half-written ~/.claude.json or settings.json can stop the assistant from starting. The inode
// test below is the mechanism proof — a rename changes the inode, an in-place write does not.
/**
 * The inode of `path`, read from a descriptor this process opened.
 *
 * `statSync(path)` and then writing the same path is a check-then-use pair — the file can be
 * replaced in between, so the number might not belong to the file that gets written, and CodeQL
 * reports the shape as `js/file-system-race` (alert #273, 2026-09-18). A descriptor cannot be
 * swapped underneath us, so this is both the quiet and the stronger way to ask.
 */
function inodeOf(path) {
  const fd = openSync(path, 'r');
  try {
    return fstatSync(fd).ino;
  } finally {
    closeSync(fd);
  }
}

test('a config write is atomic (the file is replaced, not rewritten in place)', () => {
  const home = makeHome();
  const rulePath = join(home, '.claude', 'CLAUDE.md');
  writeFileSync(rulePath, '# mine\n');
  runOffline(home);
  const first = inodeOf(rulePath);

  writeFileSync(rulePath, '# mine\n\nand a line\n');
  runOffline(home);
  const second = inodeOf(rulePath);

  assert.notEqual(
    first, second,
    'the inode is unchanged, so the file was written in place — an interrupted run can truncate it',
  );
  assert.ok(!existsSync(`${rulePath}.misakanet-tmp`), 'the temp file must not be left behind');
});

test('a read-only config file is refused with a readable message, and left untouched', () => {
  const home = makeHome();
  const rulePath = join(home, '.claude', 'CLAUDE.md');
  writeFileSync(rulePath, '# mine\n');
  chmodSync(rulePath, 0o400);
  try {
    // `--only claude`: makeHome() also fabricates a codex config, and installing *that* would
    // legitimately be a success. The claim here is about claude alone.
    const result = runOffline(home, '--only', 'claude');
    assert.equal(result.status, 1, 'nothing was installed, so this is not success');
    assert.match(result.stdout, /这些文件改不了/, result.stdout);
    assert.match(result.stdout, /CLAUDE\.md/, result.stdout);
    assert.equal(readFileSync(rulePath, 'utf8'), '# mine\n', 'the original must not be touched');
  } finally {
    chmodSync(rulePath, 0o600);
  }
});

test('--dry-run reports a path it could not write (it used to report nothing)', () => {
  const home = makeHome();
  const rulePath = join(home, '.claude', 'CLAUDE.md');
  writeFileSync(rulePath, '# mine\n');
  chmodSync(rulePath, 0o400);
  try {
    const result = runOffline(home, '--dry-run');
    assert.match(result.stdout, /这些文件改不了/, result.stdout);
  } finally {
    chmodSync(rulePath, 0o600);
  }
});

test('--client-id is a real flag, and a missing value is refused', () => {
  const home = makeHome();
  // The closing guidance tells users to keep an identity; before this flag the only way to supply
  // one was a shell export — an instruction a non-technical user cannot follow.
  const withFlag = run(home, '--client-id', 'stable-identity-0123');
  assert.notEqual(withFlag.status, 2, `--client-id must be a known flag: ${withFlag.stderr}`);
  assert.doesNotMatch(withFlag.stderr, /无法识别的选项/);

  const missing = spawnSync(process.execPath, [CLI, '--client-id'], { encoding: 'utf8' });
  assert.equal(missing.status, 2);
  assert.match(missing.stderr, /--client-id 需要一个值/);

  const invalid = run(home, '--client-id', 'x');
  assert.match(invalid.stdout, /ignored --client-id/, invalid.stdout);
});

test('a corrupt client_id file cannot break the configs we write', () => {
  // The id we declare can come from `~/.misakanet-agent/client_id`, which another installer (or
  // anything else on the box) can write, and it is interpolated into a TOML inline table, a YAML
  // mapping and JSON. A value carrying a quote and a newline is the interesting case: without the
  // shape check it closes the TOML string and appends a table of its choosing.
  const home = makeHome();
  mkdirSync(join(home, '.misakanet-agent'), { recursive: true });
  writeFileSync(join(home, '.misakanet-agent', 'client_id'),
    'evil"\n[mcp_servers.pwned]\nurl = "http://example.invalid"\n#');
  const result = runOffline(home);
  assert.equal(result.status, 0, result.stdout + result.stderr);

  const codex = readFileSync(join(home, '.codex', 'config.toml'), 'utf8');
  assert.doesNotMatch(codex, /pwned/, 'a value from a file must not become TOML structure:\n' + codex);
  assert.doesNotMatch(codex, /example\.invalid/, 'no injected content in the codex config:\n' + codex);
  const headerLine = codex.split('\n').find((l) => /^\s*http_headers\s*=/.test(l)) || '';
  assert.ok(headerLine.startsWith('http_headers = { ') && headerLine.trimEnd().endsWith(' }'),
    'the inline table must still be one closed table:\n' + headerLine);
  assert.doesNotMatch(headerLine, /X-MisakaNet-Client/, 'an id that is not id-shaped is not a hint');

  const claude = JSON.parse(readFileSync(join(home, '.claude.json'), 'utf8'));
  assert.equal(claude.mcpServers.misakanet.headers['X-MisakaNet-Client'], undefined);
  assert.equal(claude.mcpServers.misakanet.headers['X-MisakaNet-Agent'], 'claude-code',
    'the other hints are unaffected');
});

test('an id the user supplies is the identity their config declares', async () => {
  // The gap this closes: `X-MisakaNet-Client` was fed only by the id this run *minted*, so a user
  // who passed `--client-id` — the very user who took the trouble to have a stable identity — got
  // a config that declared no identity at all (found 2026-09-19, while writing the e2e check).
  const { createServer } = await import('node:http');
  const server = createServer((req, res) => {
    let body = '';
    req.on('data', (chunk) => { body += chunk; });
    req.on('end', () => {
      const payload = JSON.parse(body || '{}');
      const result = payload.method === 'tools/list'
        ? { tools: [{ name: 'misakanet_search' }] }
        : { node_id: 'MisakaTEST', token: TOKEN_SHAPE_OK };
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ jsonrpc: '2.0', id: 1, result: {
        content: [{ type: 'text', text: JSON.stringify(result) }], structuredContent: result } }));
    });
  });
  await new Promise((done) => server.listen(0, '127.0.0.1', done));

  try {
    const home = makeHome();
    const result = await runAsync(home, {
      ...process.env, MISAKANET_ENDPOINT: `http://127.0.0.1:${server.address().port}/mcp`,
    }, '--client-id', 'stable-identity-0123');
    assert.equal(result.status, 0, result.stdout + result.stderr);
    const claude = JSON.parse(readFileSync(join(home, '.claude.json'), 'utf8'));
    assert.equal(claude.mcpServers.misakanet.headers['X-MisakaNet-Client'], 'stable-identity-0123');
    // And the user is not told to "keep" a number they supplied themselves.
    assert.doesNotMatch(result.stdout, /记不记都行/, result.stdout);
  } finally {
    server.close();
  }
});

// Node 18 has no global `crypto` (Web Crypto became a bare global in Node 19), so minting a
// client id with `crypto.randomUUID()` made every registration on Node 18 die with
// `crypto is not defined` and "安装没能跑完 —— 退出码 2". The matrix leg found it on 2026-09-18;
// this test finds it on *any* Node, by preloading a module that deletes the global before the
// installer's first line runs — the same world a Node 18 user is in.
test('registration works without the global crypto object (Node 18 has none)', async () => {
  const home = makeHome();
  const preload = join(home, 'no-global-crypto.mjs');
  writeFileSync(preload, "delete globalThis.crypto;\nif (globalThis.crypto !== undefined) throw new Error('crypto is still here');\n");
  const { pathToFileURL } = await import('node:url');

  const { createServer } = await import('node:http');
  const server = createServer((req, res) => {
    let body = '';
    req.on('data', (chunk) => { body += chunk; });
    req.on('end', () => {
      const payload = JSON.parse(body || '{}');
      const result = payload.method === 'tools/list'
        ? { tools: [{ name: 'misakanet_search' }] }
        : { node_id: 'MisakaTEST', token: TOKEN_SHAPE_OK };
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ jsonrpc: '2.0', id: 1, result: {
        content: [{ type: 'text', text: JSON.stringify(result) }], structuredContent: result } }));
    });
  });
  await new Promise((done) => server.listen(0, '127.0.0.1', done));

  try {
    const result = await new Promise((done) => {
      const child = spawn(process.execPath,
        ['--import', pathToFileURL(preload).href, CLI, '--home', home],
        { env: { ...process.env, MISAKANET_ENDPOINT: `http://127.0.0.1:${server.address().port}/mcp` } });
      let stdout = '';
      let stderr = '';
      child.stdout.on('data', (c) => { stdout += c; });
      child.stderr.on('data', (c) => { stderr += c; });
      child.on('close', (status) => done({ status, stdout, stderr }));
    });
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.doesNotMatch(result.stdout, /crypto is not defined/, result.stdout);
    assert.equal(readFileSync(join(home, '.misakanet-agent', 'token'), 'utf8').trim(), TOKEN_SHAPE_OK,
      'the token must still be persisted without the global crypto object');
  } finally {
    server.close();
  }
});

test('a failed registration says what it costs, not just that it failed', () => {
  const home = makeHome();
  // run(): registration is *attempted* against a dead endpoint, which is the case whose wording
  // matters. runOffline() passes --no-register and never reaches that branch.
  const result = run(home);
  // The cost is the write path now. Saying "读课程不受影响" used to be *false* (reads were capped at
  // 5/day) and it is true again since 2026-09-18 (reads are unmetered), so the message must not
  // resurrect the old quota to sound serious.
  assert.match(result.stdout, /读课程不受影响/, result.stdout);
  assert.match(result.stdout, /写入类工具/, result.stdout);
  assert.doesNotMatch(result.stdout, /5 次|凭据形状不对/, 'no stale quota, no jargon');
});

// ── permission tiers (2026-09-18) ─────────────────────────────────────────────────────────
// Issue #1753 hit the real cost of one-command-installs-everything: a machine whose operator must
// approve changes to `~/.hermes/SOUL.md` could only answer "no", so we got a T2 report and no T1.
// The installer now says which tier each write belongs to, and can be asked for tier ① alone.
test('--mcp-only registers the endpoint and touches nothing behavioural', () => {
  const home = makeHome({
    claude: true, codex: false,
  });
  mkdirSync(join(home, '.hermes'), { recursive: true });
  writeFileSync(join(home, '.hermes', 'config.yaml'), 'model: x\n');
  const settingsBefore = JSON.parse(readFileSync(join(home, '.claude', 'settings.json'), 'utf8'));

  const result = runOffline(home, '--mcp-only', '--only', 'claude,hermes');
  assert.equal(result.status, 0, result.stdout + result.stderr);

  // ① happened: both agents have the endpoint.
  const claude = JSON.parse(readFileSync(join(home, '.claude.json'), 'utf8'));
  assert.equal(claude.mcpServers.misakanet.url, 'https://misakanet.org/mcp');
  assert.ok(readFileSync(join(home, '.hermes', 'config.yaml'), 'utf8').includes('misakanet'),
    'the hermes MCP entry is tier ① and must still be written');

  // ② did not: no rules block anywhere, and the identity file was not created.
  assert.ok(!existsSync(join(home, '.claude', 'CLAUDE.md')), 'tier ② must not run');
  assert.ok(!existsSync(join(home, '.hermes', 'SOUL.md')),
    'tier ② must not touch the agent identity file');
  // `settings.json` holds both the read-only grants (tier ①, so the tool can actually be called)
  // and the hooks (tier ③). Only the hooks must be missing here.
  const settingsAfter = JSON.parse(readFileSync(join(home, '.claude', 'settings.json'), 'utf8'));
  assert.deepEqual(settingsAfter.hooks, settingsBefore.hooks, 'tier ③ hooks must not be written');
  assert.equal(settingsAfter.permissions.allow.length, 5,
    'the read-only grants belong to tier ①: without them the first search is denied');

  // ③ did not: no hook, no version stamp.
  assert.ok(!existsSync(join(home, '.misakanet-agent', 'hook.mjs')), 'tier ③ must not run');
  assert.ok(!existsSync(join(home, '.misakanet-agent', 'version')), 'tier ③ must not run');
  assert.match(result.stdout, /--mcp-only/, 'the run must say what it did not do');
});

test('--list-writes shows every write with its tier and writes nothing', () => {
  const home = makeHome();
  const before = snapshot(home);
  const result = runOffline(home, '--list-writes', '--only', 'claude');
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.deepEqual(snapshot(home), before, '--list-writes must be a pure read');

  const rows = result.stdout.split('\n').filter((l) => l.startsWith('tier'));
  assert.ok(rows.length >= 3, `expected a manifest, got:\n${result.stdout}`);
  const tiers = new Set(rows.map((r) => r.split('\t')[0]));
  assert.deepEqual([...tiers].sort(), ['tier1', 'tier2', 'tier3'],
    'a manifest that hides the tiers is not something an operator can approve');
  assert.match(result.stdout, /① 注册 MCP 端点/);
  assert.match(result.stdout, /--mcp-only/, 'it must name the way to request less');
});

test('--list-writes --mcp-only asks for tier ① only', () => {
  const home = makeHome();
  const result = runOffline(home, '--list-writes', '--mcp-only', '--only', 'claude');
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const rows = result.stdout.split('\n').filter((l) => l.startsWith('tier'));
  assert.ok(rows.length, result.stdout);
  assert.ok(rows.every((r) => r.startsWith('tier1')), `only tier ① may be requested:\n${rows.join('\n')}`);
});

test('--mcp-only says out loud that the agent will not search by itself', () => {
  const home = makeHome();
  const result = runOffline(home, '--mcp-only', '--only', 'claude');
  assert.equal(result.status, 0, result.stdout + result.stderr);
  // Tier ① is a capability, not a behaviour: the rules block (②) and the hook-injected first-turn
  // announcement (③) are what make an agent look things up on its own. Saying it only in the docs
  // means the user who needs it most never reads it.
  assert.match(result.stdout, /不会自己想到去查/, result.stdout);
  assert.match(result.stdout, /去掉 --mcp-only/, 'it must name the way to get the full install');
});

test('--report tells "only tier ①" apart from "nothing installed"', () => {
  const onlyMcp = makeHome();
  runOffline(onlyMcp, '--mcp-only', '--only', 'claude');
  const scoped = runOffline(onlyMcp, '--report', '--only', 'claude');
  assert.match(scoped.stdout, /^install-scope: mcp-only$/m, scoped.stdout);

  const untouched = makeHome();
  const plain = runOffline(untouched, '--report', '--only', 'claude');
  assert.match(plain.stdout, /^install-scope: none$/m, plain.stdout);

  const full = makeHome();
  runOffline(full, '--only', 'claude');
  const fullReport = runOffline(full, '--report', '--only', 'claude');
  assert.match(fullReport.stdout, /^install-scope: full$/m, fullReport.stdout);
});
