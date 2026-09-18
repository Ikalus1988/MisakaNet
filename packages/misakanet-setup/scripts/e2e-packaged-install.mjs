#!/usr/bin/env node
/**
 * End-to-end test of the *published artifact*: the tarball `npm pack` produces, installed
 * globally the way a user installs it (`npm i -g @misaka-net/misakanet-setup`).
 *
 * Why this file exists, and why it is not another unit test
 * --------------------------------------------------------
 * `workers/misakanet-setup.test.mjs` runs the source tree: `node packages/misakanet-setup/bin/…`.
 * Everything that can differ between "the checkout" and "what the user gets" is therefore
 * untested by it — the `files` allowlist in package.json, the `prepack` hook copy, the global bin
 * shim, the platform's install layout, and whether the copy of the hook inside the tarball is the
 * one the installer wires into the assistant's config. The benchmark for this job is uv's
 * `test-smoke.yml`, which tests a *packaged* artifact (`download-artifact`) instead of the working
 * tree; the reasoning applies with more force here, because this package's audience cannot debug
 * anything and never sees a checkout.
 *
 * The second job is honesty about the checks themselves: `--inject <name>` perturbs the world so
 * that one named check *must* go red, and the run FAILS if it does not. A check that cannot fail on
 * a known-bad input is decoration, and the cheapest way to prove otherwise is to make it fail on
 * purpose, in CI, on every run.
 *
 * Usage (CI passes --prefix; --live adds production-endpoint checks):
 *   npm install -g --prefix "$PREFIX" ./misakanet-setup-0.5.4.tgz
 *   node packages/misakanet-setup/scripts/e2e-packaged-install.mjs \
 *     --prefix "$PREFIX" --expect-version 0.5.4 --live
 *   node …/e2e-packaged-install.mjs --prefix "$PREFIX" --inject leftover-temp
 *   node …/e2e-packaged-install.mjs --list-checks
 *
 * Exit codes: 0 all checks held (or the injected check went red as required) / 1 otherwise
 * / 2 misuse (bad arguments, or an injection whose check is skipped on this platform).
 */
import { spawn } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import {
  closeSync, cpSync, existsSync, fstatSync, mkdirSync, mkdtempSync, openSync, readFileSync,
  readdirSync, realpathSync, rmSync, writeFileSync,
} from 'node:fs';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import { dirname, join, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

// ── arguments ────────────────────────────────────────────────────────────────────────────
const argv = process.argv.slice(2);
const valueOf = (flag, fallback = '') => {
  const i = argv.indexOf(flag);
  return i >= 0 && argv[i + 1] ? argv[i + 1] : fallback;
};
const has = (flag) => argv.includes(flag);

const PREFIX = valueOf('--prefix');
const EXPECT_VERSION = valueOf('--expect-version');
const INJECT = valueOf('--inject');
const LIVE = has('--live');
const PKG_NAME = '@misaka-net/misakanet-setup';
// Node 18 has no `import.meta.dirname`, and this script runs on the Node 18 leg of the matrix.
const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');
const CANONICAL_ENDPOINT = 'https://misakanet.org/mcp';

const PREFIX_ABS = PREFIX ? resolve(PREFIX) : '';
/**
 * Locate the installed package.
 *
 * Two layouts, and guessing wrong would silently test the wrong thing: `npm i -g --prefix <dir>`
 * on Unix puts packages in `<dir>/lib/node_modules` with a symlink in `<dir>/bin`, while on Windows
 * the same command installs into `<dir>/node_modules` with a `.cmd` shim directly in `<dir>`. The
 * symlink is the only one that tells the truth about what `npx`/PATH will execute, so it is tried
 * first; `--bin` overrides everything for a caller that already knows.
 */
function locateInstalledBin() {
  const explicit = valueOf('--bin');
  if (explicit) return resolve(explicit);
  const candidates = [];
  if (process.platform !== 'win32') candidates.push(join(PREFIX_ABS, 'bin', 'misakanet-setup'));
  for (const lib of ['lib/node_modules', 'node_modules']) {
    candidates.push(join(PREFIX_ABS, ...lib.split('/'), ...PKG_NAME.split('/'), 'bin', 'misakanet-setup.mjs'));
  }
  for (const candidate of candidates) {
    try {
      return realpathSync(candidate);
    } catch { /* try the next layout */ }
  }
  return join(PREFIX_ABS, 'bin', 'misakanet-setup');
}

const INSTALLED_BIN = PREFIX_ABS ? locateInstalledBin() : '';
const PKG_DIR = INSTALLED_BIN ? resolve(INSTALLED_BIN, '..', '..') : '';
const HOOK_IN_PKG = PKG_DIR ? join(PKG_DIR, 'hook', 'checkpoint_reminder.mjs') : '';
/** The subject under test. `--inject` swaps in a shim that wraps this binary. */
let ACTIVE_BIN = INSTALLED_BIN;

// The production tool contract (AGENTS.md §3.2). Pinned here because this is the only check that
// asks the *live* endpoint: if the server grows a tool without the docs, the two disagree in CI
// rather than inside a user's session.
const DOCUMENTED_REMOTE_TOOLS = [
  'misakanet_search', 'misakanet_get_lesson', 'misakanet_submit_intake',
  'misakanet_write_lesson', 'misakanet_preflight', 'misakanet_register', 'misakanet_me_events',
];

if (!argv.includes('--list-checks') && !PREFIX) {
  console.error('usage: e2e-packaged-install.mjs --prefix <npm global prefix> [--expect-version v]'
    + ' [--live] [--inject <check>] [--list-checks] [--keep]');
  process.exit(2);
}

// ── tiny harness ─────────────────────────────────────────────────────────────────────────
const results = [];
const notes = [];
const log = (line) => notes.push(line);
const fail = (msg) => { throw new Error(msg); };
const need = (cond, msg) => { if (!cond) fail(msg); };

async function check(name, fn) {
  const started = Date.now();
  try {
    const outcome = await fn();
    if (outcome && typeof outcome === 'object' && outcome.skip) {
      results.push({ name, status: 'skip', detail: outcome.skip, ms: Date.now() - started });
      return;
    }
    results.push({ name, status: 'pass', detail: outcome || '', ms: Date.now() - started });
  } catch (err) {
    results.push({ name, status: 'fail', detail: (err && err.message) || String(err), ms: Date.now() - started });
  }
}

const scratchDirs = [];
function scratch(prefix) {
  const dir = mkdtempSync(join(tmpdir(), `mn-e2e-${prefix}-`));
  scratchDirs.push(dir);
  return dir;
}

/** Run a command asynchronously (an in-process stub endpoint cannot answer a spawnSync child). */
function run(cmd, args, { env = {}, unset = [], input, timeoutMs = 90_000 } = {}) {
  const merged = { ...process.env, ...env };
  for (const key of unset) delete merged[key];
  return new Promise((done) => {
    const child = spawn(cmd, args, { env: merged, stdio: [input === undefined ? 'ignore' : 'pipe', 'pipe', 'pipe'] });
    let stdout = '';
    let stderr = '';
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; child.kill('SIGKILL'); }, timeoutMs);
    child.stdout.setEncoding('utf8');
    child.stderr.setEncoding('utf8');
    child.stdout.on('data', (chunk) => { stdout += chunk; });
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    if (input !== undefined) child.stdin.end(input);
    child.on('error', (err) => {
      clearTimeout(timer);
      done({ status: -1, stdout, stderr: `${stderr}${err.message}`, timedOut });
    });
    child.on('close', (status) => {
      clearTimeout(timer);
      done({ status, stdout, stderr, timedOut });
    });
  });
}

/**
 * The CLI call every check goes through. The endpoint is *always* decided here: a run either asks
 * the published endpoint or an in-process stub, and never inherits `MISAKANET_ENDPOINT` from the
 * environment — otherwise "the install worked" could mean "the dead port in my shell made it
 * look offline".
 */
function cli(args, { home, endpoint = CANONICAL_ENDPOINT } = {}) {
  const env = { MISAKANET_ENDPOINT: endpoint };
  if (home) {
    env.HOME = home;
    env.USERPROFILE = home;                 // Windows has no HOME; homedir() reads USERPROFILE
    env.MN_E2E_HOME = home;                 // read by the --inject shim
  }
  // MISAKANET_CLIENT_ID would change which node the register call reuses, so a check that cares
  // about identity must pass --client-id itself rather than inherit one from the shell.
  return run(process.execPath, [ACTIVE_BIN, ...args], { env, unset: ['MISAKANET_CLIENT_ID'] });
}

/** {relative path → {hash, size, mode}} over a tree: byte equality plus permission bits. */
function snapshot(dir) {
  const out = {};
  const walk = (base, rel) => {
    let entries;
    try {
      entries = readdirSync(base, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      const full = join(base, entry.name);
      const key = rel ? `${rel}/${entry.name}` : entry.name;
      if (entry.isDirectory()) {
        walk(full, key);
        continue;
      }
      // Read through one descriptor: `readFileSync(path)` followed by `statSync(path)` is a
      // check-then-use pair on a path, which is exactly what CodeQL js/file-system-race reports.
      const fd = openSync(full, 'r');
      try {
        const st = fstatSync(fd);
        const bytes = readFileSync(fd);
        out[key] = {
          hash: createHash('sha256').update(bytes).digest('hex'),
          size: bytes.length,
          mode: st.mode & 0o777,
        };
      } finally {
        closeSync(fd);
      }
    }
  };
  walk(dir, '');
  return out;
}

/** The mode bits of `path`, read from a descriptor (see snapshot for why not `statSync`). */
function modeOf(path) {
  const fd = openSync(path, 'r');
  try {
    return fstatSync(fd).mode & 0o777;
  } finally {
    closeSync(fd);
  }
}

const readJson = (path) => JSON.parse(readFileSync(path, 'utf8'));
const show = (r) => `exit=${r.status}${r.timedOut ? ' (timeout)' : ''}`
  + ` stdout=${JSON.stringify(r.stdout.slice(-600))} stderr=${JSON.stringify(r.stderr.slice(-400))}`;
const sleep = (ms) => new Promise((done) => setTimeout(done, ms));

function assertInside(child, parent, what) {
  const inside = resolve(child).startsWith(resolve(parent) + sep) || resolve(child) === resolve(parent);
  need(inside, `${what} (${child}) must live under ${parent}`);
}

// ── homes ────────────────────────────────────────────────────────────────────────────────
/** A machine that looks like a real user: their own hooks, rules and other MCP servers. */
function makeUserHome({ claude = true, codex = true, openclaw = false, hermes = false } = {}) {
  const home = scratch('home');
  if (claude) {
    mkdirSync(join(home, '.claude'), { recursive: true });
    writeFileSync(join(home, '.claude.json'), `${JSON.stringify({
      mcpServers: { existing: { type: 'http', url: 'https://example.invalid/mcp' } },
      myOwnKey: { keep: true },
    }, null, 2)}\n`);
    writeFileSync(join(home, '.claude', 'settings.json'), `${JSON.stringify({
      hooks: {
        // The user's own hook. `--uninstall` once matched hook entries by *file name*
        // (`…includes('hook.mjs')`) and deleted this one, while README.md promises it never
        // touches hooks it did not write.
        Stop: [{ hooks: [{ type: 'command', command: 'node ~/my-hook.mjs' }] }],
      },
      permissions: { allow: ['Bash(git status)'] },
    }, null, 2)}\n`);
    writeFileSync(join(home, '.claude', 'CLAUDE.md'), '# My own rules\n\nDo not touch the header.\n');
  }
  if (codex) {
    mkdirSync(join(home, '.codex'), { recursive: true });
    writeFileSync(join(home, '.codex', 'config.toml'), 'model = "gpt-5"\n\n[mcp_servers.context7]\ncommand = "npx"\n');
  }
  if (openclaw) {
    mkdirSync(join(home, '.openclaw', 'workspace'), { recursive: true });
    writeFileSync(join(home, '.openclaw', 'openclaw.json'),
      `${JSON.stringify({ meta: { keep: true }, mcp: { servers: { other: { url: 'https://x' } } } }, null, 2)}\n`);
  }
  if (hermes) {
    mkdirSync(join(home, '.hermes'), { recursive: true });
    writeFileSync(join(home, '.hermes', 'config.yaml'), 'model: x\n');
  }
  return home;
}

/**
 * A stand-in for the MisakaNet MCP endpoint, in this process.
 *
 * Deterministic registration is what makes the token checks possible at all: without it, testing
 * "the token reaches the config with mode 600" would mean registering real production nodes from
 * CI on every run. It also fails loudly if the installer stops calling the endpoint — the checks
 * below assert `registerCalls`, so a green token check cannot mean "nothing ever happened".
 *
 * The stub's token is derived at runtime, never written as a literal. A literal of the shape the
 * installer itself accepts is indistinguishable from a real credential to a scanner that cannot know
 * it is fake — HOL Guard's plugin scanner reported exactly that (error-severity `HARDCODED_SECRET`,
 * #276 on 2026-09-18, the same class as #252/#253/#254 which produced `workers/_test-token.mjs`).
 * Deriving it also means the fixture cannot accidentally match a real token, and the value stays
 * valid for the installer's own shape check (`mcp_` followed by 20+ [A-Za-z0-9_-]).
 */
async function stubEndpoint() {
  const token = `mcp_e2e_${randomUUID().replace(/-/g, '')}`;
  const state = { registerCalls: 0, toolsCalls: 0, authSeen: [], token };
  const server = createServer((req, res) => {
    let body = '';
    req.on('data', (chunk) => { body += chunk; });
    req.on('end', () => {
      let payload = {};
      try {
        payload = JSON.parse(body || '{}');
      } catch { /* answered as an error below */ }
      const tool = payload.params?.name;
      if (tool === 'misakanet_register') state.registerCalls += 1;
      if (payload.method === 'tools/list') state.toolsCalls += 1;
      if (req.headers.authorization) state.authSeen.push(String(req.headers.authorization));
      const result = payload.method === 'tools/list'
        ? { tools: DOCUMENTED_REMOTE_TOOLS.map((name) => ({ name })) }
        : tool === 'misakanet_register'
          ? { node_id: 'MisakaE2E', token: state.token, reused: false }
          : { results: [] };
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        jsonrpc: '2.0',
        id: payload.id ?? 1,
        result: { content: [{ type: 'text', text: JSON.stringify(result) }], structuredContent: result },
      }));
    });
  });
  await new Promise((done) => server.listen(0, '127.0.0.1', done));
  return { state, url: `http://127.0.0.1:${server.address().port}/mcp`, close: () => server.close() };
}

/** One MCP call over HTTP, with the headers a real client sends. */
async function mcpCall(url, method, params, { token = '', origin = 'https://misakanet.org' } = {}) {
  const headers = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    'MCP-Protocol-Version': '2025-06-18',
  };
  if (origin) headers.Origin = origin;
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }),
    signal: AbortSignal.timeout(20_000),
  });
  return { status: response.status, text: await response.text() };
}

// ── checks ───────────────────────────────────────────────────────────────────────────────
const CHECKS = [
  ['installed-artifact-is-the-tarball', async () => {
    need(existsSync(INSTALLED_BIN), `no installed bin at ${INSTALLED_BIN} — did the global install run?`);
    need(!resolve(INSTALLED_BIN).startsWith(resolve(REPO_ROOT) + sep),
      'the binary under test is inside the repo checkout, so this run tested the source tree');
    assertInside(INSTALLED_BIN, PREFIX_ABS, 'the installed package');
    // The shim is what `npx`/PATH actually executes; its absence is a broken install even when the
    // package files are present.
    const shims = process.platform === 'win32'
      ? [join(PREFIX_ABS, 'misakanet-setup.cmd'), join(PREFIX_ABS, 'misakanet-setup.ps1')]
      : [join(PREFIX_ABS, 'bin', 'misakanet-setup')];
    const found = shims.filter((p) => existsSync(p));
    need(found.length > 0, `no global bin shim among: ${shims.join(', ')}`);
    need(existsSync(HOOK_IN_PKG), `the tarball must ship the hook at ${HOOK_IN_PKG}`);
    const voice = readdirSync(join(PKG_DIR, 'voice'));
    need(voice.includes('voice-hook.mjs'), 'the tarball must ship the voice player');
    need(voice.some((f) => f.endsWith('.mp3')), 'the tarball must ship the voice cues');
    return `bin=${INSTALLED_BIN}, shim=${found[0]}, voice files=${voice.length}`;
  }],

  ['version-matches-expectation', async () => {
    const result = await cli(['--version']);
    need(result.status === 0, `--version must exit 0: ${show(result)}`);
    const printed = result.stdout.trim();
    const inTarball = readJson(join(PKG_DIR, 'package.json')).version;
    need(printed === inTarball, `--version printed ${printed} but the installed package.json says ${inTarball}`);
    if (EXPECT_VERSION) need(printed === EXPECT_VERSION, `the artifact is ${printed}, CI expected ${EXPECT_VERSION}`);
    return `${printed} (--version agrees with the installed package.json)`;
  }],

  ['help-and-version-write-nothing', async () => {
    const home = makeUserHome();
    const before = snapshot(home);
    for (const flag of ['--help', '-h', '--version']) {
      const result = await cli([flag, '--home', home], { home });
      need(result.status === 0, `${flag} must exit 0: ${show(result)}`);
    }
    const help = await cli(['--help', '--home', home], { home });
    for (const must of ['--dry-run', '--report', '--uninstall', '--client-id', '退出码']) {
      need(help.stdout.includes(must), `--help must document ${must}`);
    }
    need(JSON.stringify(snapshot(home)) === JSON.stringify(before),
      'asking for help must not touch a single file');
    return 'exit 0 for --help/-h/--version, flags documented, zero writes';
  }],

  ['unknown-flag-is-refused-without-writing', async () => {
    const home = makeUserHome();
    const before = snapshot(home);
    const result = await cli(['--home', home, '--frobnicate'], { home });
    need(result.status === 2, `an unknown flag must stop with exit 2: ${show(result)}`);
    need(result.stderr.includes('--frobnicate'), 'the message must name the flag it did not understand');
    need(JSON.stringify(snapshot(home)) === JSON.stringify(before), 'an unknown flag must write nothing');
    return 'exit 2, flag named, nothing written';
  }],

  ['dry-run-writes-nothing-but-reports-paths', async () => {
    const home = makeUserHome();
    const before = snapshot(home);
    const result = await cli(['--home', home, '--dry-run', '--no-register'], { home });
    need(result.status === 0, `--dry-run must exit 0: ${show(result)}`);
    need(/CLAUDE\.md|\.claude\.json/.test(result.stdout),
      `--dry-run must name the files it would write: ${result.stdout.slice(-500)}`);
    need(JSON.stringify(snapshot(home)) === JSON.stringify(before), 'a dry run that writes is a lie');
    return 'exit 0, paths named, zero writes';
  }],

  ['install-writes-configs-the-assistants-read', async () => {
    const home = makeUserHome({ openclaw: true, hermes: true });
    const result = await cli(['--home', home, '--no-register'], { home });
    need(result.status === 0, `install must succeed: ${show(result)}`);

    const claude = readJson(join(home, '.claude.json'));
    need(claude.mcpServers?.misakanet?.url === CANONICAL_ENDPOINT,
      `Claude Code MCP entry missing: ${JSON.stringify(claude.mcpServers)}`);
    need(claude.mcpServers.misakanet.type === 'http', 'the Claude Code entry must be an http MCP server');
    need(claude.myOwnKey?.keep === true, "the user's own top-level keys must survive");
    need(claude.mcpServers.existing?.url === 'https://example.invalid/mcp',
      "the user's other MCP servers must survive");

    const settings = readJson(join(home, '.claude', 'settings.json'));
    need(JSON.stringify(settings.hooks || {}).includes('.misakanet-agent'),
      'the Stop hook must point into our own namespace directory');
    need(JSON.stringify(settings).includes('my-hook.mjs'), "the user's own hook must be left in place");

    const claudeMd = readFileSync(join(home, '.claude', 'CLAUDE.md'), 'utf8');
    need(claudeMd.includes('Do not touch the header'), "the user's own rules must survive");
    need(claudeMd.includes('misakanet:start'), 'the rules block must be injected');

    const codex = readFileSync(join(home, '.codex', 'config.toml'), 'utf8');
    need(codex.includes('experimental_use_rmcp_client = true'), 'codex needs the top-level rmcp flag');
    need(codex.includes('[mcp_servers.misakanet]'), 'the codex MCP table is missing');
    need(codex.includes(`url = "${CANONICAL_ENDPOINT}"`), 'the codex url must be the canonical endpoint');
    need(codex.includes('[mcp_servers.context7]'), "the user's other codex servers must survive");
    need(readFileSync(join(home, '.codex', 'AGENTS.md'), 'utf8').includes('misakanet:start'),
      'the codex rules block is missing');

    need(readFileSync(join(home, '.openclaw', 'openclaw.json'), 'utf8').includes('misakanet'),
      'the openclaw registration is missing');
    need(readFileSync(join(home, '.hermes', 'config.yaml'), 'utf8').includes('misakanet'),
      'the hermes registration is missing');
    return 'claude + codex + openclaw + hermes configured, every piece of user content preserved';
  }],

  ['the-hook-we-installed-actually-runs', async () => {
    const home = makeUserHome();
    await cli(['--home', home, '--no-register'], { home });
    const installed = join(home, '.misakanet-agent', 'hook.mjs');
    need(existsSync(installed), `the installer must place the hook at ${installed}`);
    // Byte-identical to the copy inside the tarball: a stale or half-written hook would make every
    // later turn behave differently from what was published.
    const digest = (bytes) => createHash('sha256').update(bytes).digest('hex');
    need(digest(readFileSync(HOOK_IN_PKG)) === digest(readFileSync(installed)),
      'the installed hook differs from the hook shipped in the tarball');

    const env = { HOME: home, USERPROFILE: home };
    const payload = JSON.stringify({ session_id: 'e2e', transcript_path: join(home, 'transcript.jsonl') });
    const first = await run(process.execPath, [installed, 'prompt'], { env, input: payload });
    need(first.status === 0, `the hook must never break the session (exit 0): ${show(first)}`);
    need(first.stdout.includes('MisakaNet'), `the first turn must announce the library: ${show(first)}`);

    // A payload the assistant might really send on a bad day: still exit 0, still no output.
    const bad = await run(process.execPath, [installed, 'prompt'], { env, input: 'not json at all' });
    need(bad.status === 0, `a bad payload must still exit 0: ${show(bad)}`);
    need(bad.stdout.trim() === '', `a bad payload must produce no output: ${show(bad)}`);
    log('hook run end-to-end as the assistant would: announced on turn 1, silent on malformed input');
    return 'matches the tarball copy, announces on turn 1, silent on malformed input';
  }],

  ['a-no-op-run-does-not-touch-your-files', async () => {
    const home = makeUserHome();
    await cli(['--home', home, '--no-register'], { home });
    const rules = join(home, '.claude', 'CLAUDE.md');
    const settings = join(home, '.claude', 'settings.json');
    // mtime, not inode: an in-place rewrite of identical bytes changes the mtime, a skipped write
    // changes nothing, and mtime behaves the same on all three platforms. The gap is there so the
    // two timestamps cannot collide inside the filesystem's clock granularity.
    const stamp = { rules: statMtime(rules), settings: statMtime(settings) };
    await sleep(1100);

    const second = await cli(['--home', home, '--no-register'], { home });
    need(second.status === 0, `a second run must still exit 0: ${show(second)}`);
    need(statMtime(rules) === stamp.rules,
      'the rules file was rewritten by a run that had nothing to change');
    need(statMtime(settings) === stamp.settings,
      'settings.json was rewritten by a run that had nothing to change');
    return 're-running the installer leaves the config files untouched (mtime unchanged)';
  }],

  // The byte-level version of the promise above, and the one that matters to a user whose editor or
  // assistant has the file open: a second run must leave a *byte-identical* tree. mtime cannot see
  // an in-place write that lands in the same clock tick, and it cannot see a file appearing either.
  ['a-second-run-is-byte-identical', async () => {
    const home = makeUserHome({ openclaw: true, hermes: true });
    const first = await cli(['--home', home, '--no-register'], { home });
    need(first.status === 0, `install must succeed: ${show(first)}`);
    const afterFirst = snapshot(home);
    need(Object.keys(afterFirst).length > 6, 'the first run must have written something to compare');

    const second = await cli(['--home', home, '--no-register'], { home });
    need(second.status === 0, `a second run must still exit 0: ${show(second)}`);
    const afterSecond = snapshot(home);

    const added = Object.keys(afterSecond).filter((rel) => !afterFirst[rel]);
    const removed = Object.keys(afterFirst).filter((rel) => !afterSecond[rel]);
    need(added.length === 0, `a second run created files: ${added.join(', ')}`);
    need(removed.length === 0, `a second run deleted files: ${removed.join(', ')}`);
    const changed = Object.keys(afterFirst).filter((rel) => afterFirst[rel].hash !== afterSecond[rel].hash);
    need(changed.length === 0, `a second run changed the bytes of: ${changed.join(', ')}`);
    // "It reported success" and "it changed nothing" are two separate claims, so the second one is
    // read off the tree, not off the summary line — which is checked separately, as prose.
    need(/无改动|已是最新|已存在/.test(second.stdout),
      `a no-op run should say so: ${second.stdout.slice(-400)}`);
    return `${Object.keys(afterFirst).length} files, byte-identical across two runs`;
  }],

  ['no-temp-files-left-behind', async () => {
    const home = makeUserHome({ openclaw: true, hermes: true });
    await cli(['--home', home, '--no-register'], { home });
    const strays = Object.keys(snapshot(home)).filter((rel) => rel.includes('.misakanet-tmp'));
    need(strays.length === 0, `temp files left behind: ${strays.join(', ')}`);
    return 'no *.misakanet-tmp anywhere in the home';
  }],

  ['token-file-is-not-world-readable', async () => {
    if (process.platform === 'win32') return { skip: 'Windows has no POSIX mode bits to assert' };
    const stub = await stubEndpoint();
    try {
      const home = makeUserHome();
      const result = await cli(['--home', home, '--only', 'claude', '--client-id', 'e2e-token-check'],
        { home, endpoint: stub.url });
      need(result.status === 0, `install must succeed: ${show(result)}`);
      need(stub.state.registerCalls >= 1,
        'the installer never called misakanet_register, so this check would have been vacuous');
      const token = join(home, '.misakanet-agent', 'token');
      need(existsSync(token), 'the returned token must be persisted (the read quota depends on it)');
      const mode = modeOf(token);
      need(mode === 0o600, `the token file must be 0600, found 0${mode.toString(8)}`);
      need(readFileSync(token, 'utf8').trim() === stub.state.token,
        'the persisted token must be the one the server returned');
      return `mode=0600, token persisted, ${stub.state.registerCalls} register call(s)`;
    } finally {
      stub.close();
    }
  }],

  ['the-token-never-reaches-the-log', async () => {
    const stub = await stubEndpoint();
    try {
      const home = makeUserHome({ hermes: true });
      const registered = await cli(['--home', home, '--client-id', 'e2e-token-log'], { home, endpoint: stub.url });
      const reported = await cli(['--home', home, '--report'], { home, endpoint: stub.url });
      for (const r of [registered, reported]) {
        need(!(r.stdout + r.stderr).includes(stub.state.token),
          'a credential must never appear in output a user is expected to paste into an issue');
      }
      // Positive control: the report still has to describe the credential state, or "never printed"
      // could be satisfied by printing nothing at all. (The `--report` token line is a file
      // *existence* fact, which is why it is safe to print and why it is pinned here.)
      need(/token/.test(reported.stdout),
        `--report must describe the token state: ${reported.stdout.slice(-400)}`);
      return 'token absent from stdout and stderr, while --report still describes the token state';
    } finally {
      stub.close();
    }
  }],

  ['the-registration-reaches-every-configured-assistant', async () => {
    const stub = await stubEndpoint();
    try {
      const home = makeUserHome({ openclaw: true, hermes: true });
      const result = await cli(['--home', home, '--client-id', 'e2e-register-all'], { home, endpoint: stub.url });
      need(result.status === 0, `install must succeed: ${show(result)}`);
      const bearer = `Bearer ${stub.state.token}`;
      need(readJson(join(home, '.claude.json')).mcpServers.misakanet.headers?.Authorization === bearer,
        'the Claude Code config did not receive the bearer token');
      need(readFileSync(join(home, '.codex', 'config.toml'), 'utf8').includes(bearer),
        'the Codex config did not receive the bearer token');
      need(readFileSync(join(home, '.openclaw', 'openclaw.json'), 'utf8').includes(stub.state.token),
        'the OpenClaw config did not receive the bearer token');
      const env = readFileSync(join(home, '.hermes', '.env'), 'utf8');
      need(env.includes(stub.state.token), 'the Hermes .env did not receive the bearer token');
      if (process.platform !== 'win32') {
        need(modeOf(join(home, '.hermes', '.env')) === 0o600,
          'the Hermes .env carries a credential and must not be world-readable');
      }
      return `${stub.state.registerCalls} register call(s); token in claude/codex/openclaw/hermes configs`;
    } finally {
      stub.close();
    }
  }],

  ['uninstall-gives-the-config-back', async () => {
    const home = makeUserHome({ openclaw: true, hermes: true });
    const pristine = scratch('pristine');
    cpSync(home, pristine, { recursive: true });
    const before = snapshot(home);
    const installed = await cli(['--home', home, '--client-id', 'e2e-uninstall'], { home });
    need(installed.status === 0, `install must succeed: ${show(installed)}`);
    const after = await cli(['--home', home, '--uninstall'], { home });
    need(after.status === 0, `--uninstall must exit 0: ${show(after)}`);

    const now = snapshot(home);
    const isBak = (rel) => rel.includes('.misakanet.bak');
    const kept = Object.keys(now).filter((rel) => !isBak(rel));

    // 1. Nothing of ours is left anywhere. The blunt text scan catches a partial uninstall in any
    //    file, including ones this check does not know about.
    const residue = kept.filter((rel) => /misakanet/i.test(readFileSync(join(home, rel), 'utf8')));
    need(residue.length === 0, `these files still mention misakanet: ${residue.join(', ')}`);
    need(!existsSync(join(home, '.misakanet-agent')), 'the state directory must be removed');

    // 2. Files we created are gone; files that existed before are still there. Together with (1)
    //    this is "the config came back", without pretending the bytes are ours to choose.
    const created = kept.filter((rel) => !before[rel]);
    need(created.length === 0, `files we created are still there: ${created.join(', ')}`);
    const missing = Object.keys(before).filter((rel) => !now[rel]);
    need(missing.length === 0, `files that existed before were deleted: ${missing.join(', ')}`);

    // 3. Line-based formats come back byte-exact — the uninstall only removes lines there.
    const lineFiles = Object.keys(before).filter((rel) => !rel.endsWith('.json'));
    const drifted = lineFiles.filter((rel) => before[rel].hash !== now[rel].hash);
    need(drifted.length === 0, `these line-based files did not come back byte-exact: ${drifted.join(', ')}`);

    // 4. JSON configs come back *semantically*. The install re-serializes them, so byte equality is
    //    not the promise; "your servers, keys and permissions are exactly as they were, with no
    //    empty container we created left behind" is — and until 2026-09-18 that last part was
    //    false (a bare ~/.claude.json came back as {"mcpServers": {}}).
    const jsonFiles = Object.keys(before).filter((rel) => rel.endsWith('.json'));
    need(jsonFiles.length >= 2, 'this check needs JSON configs to be meaningful');
    for (const rel of jsonFiles) {
      const original = pruneEmpties(JSON.parse(readFileSync(join(pristine, rel), 'utf8')));
      const current = pruneEmpties(JSON.parse(readFileSync(join(home, rel), 'utf8')));
      need(JSON.stringify(current) === JSON.stringify(original),
        `${rel} did not come back semantically: before=${JSON.stringify(original)} after=${JSON.stringify(current)}`);
      if (before[rel].hash !== now[rel].hash) log(`${rel}: bytes differ (re-serialized), content identical`);
    }
    const settings = readJson(join(home, '.claude', 'settings.json'));
    need(JSON.stringify(settings).includes('my-hook.mjs'), "the user's own hook must survive --uninstall");
    return `${jsonFiles.length} JSON configs semantically restored, ${lineFiles.length} line files byte-exact, no residue`;
  }],

  ['nothing-installed-exits-1-with-a-reason', async () => {
    const home = scratch('empty');
    const result = await cli(['--home', home, '--only', 'claude', '--no-register'], { home });
    need(result.status === 1, `an install that installed nothing must not exit 0: ${show(result)}`);
    // The reason is on stderr: on a non-zero exit the explanation belongs in the stream a wrapper
    // reads, not only in the one a human happens to be watching.
    need(result.stderr.includes('没有装上任何助手'),
      `the reason must be in plain words on stderr: ${result.stderr.slice(-400)}`);
    return 'exit 1 with the reason on stderr';
  }],
];

/** Recursively drop empty objects/arrays, so "semantically the same config" is one comparison. */
function pruneEmpties(value) {
  if (Array.isArray(value)) {
    value.forEach(pruneEmpties);
  } else if (value && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) {
      pruneEmpties(child);
      if (child && typeof child === 'object' && Object.keys(child).length === 0) delete value[key];
    }
  }
  return value;
}

/** mtime in ms, so "was this file touched?" is one comparison on any platform. */
function statMtime(path) {
  const fd = openSync(path, 'r');
  try {
    return fstatSync(fd).mtimeMs;
  } finally {
    closeSync(fd);
  }
}

// ── live checks (the published endpoint) ─────────────────────────────────────────────────
const LIVE_CHECKS = [
  ['live-endpoint-serves-the-documented-tools', async () => {
    const init = await mcpCall(CANONICAL_ENDPOINT, 'initialize', {
      protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'misakanet-setup-e2e', version: '1' },
    });
    need(init.status === 200, `initialize returned HTTP ${init.status}: ${init.text.slice(0, 200)}`);
    const listed = await mcpCall(CANONICAL_ENDPOINT, 'tools/list', {});
    need(listed.status === 200, `tools/list returned HTTP ${listed.status}: ${listed.text.slice(0, 200)}`);
    const payload = JSON.parse(listed.text);
    const tools = (payload.result?.structuredContent?.tools || payload.result?.tools || [])
      .map((t) => t.name).sort();
    const documented = [...DOCUMENTED_REMOTE_TOOLS].sort();
    need(JSON.stringify(tools) === JSON.stringify(documented),
      `the live endpoint and AGENTS.md §3.2 disagree: live=[${tools.join(', ')}] documented=[${documented.join(', ')}]`);
    // The documented Origin rule: a wrong value is refused. If that stops being true, the
    // `-H 'Origin: …'` in every published example is decoration.
    const evil = await mcpCall(CANONICAL_ENDPOINT, 'tools/list', {}, { origin: 'https://evil.example.com' });
    need(evil.status === 403, `a foreign Origin must be refused, got HTTP ${evil.status}`);
    log('live endpoint: 7 documented tools, foreign Origin → 403');
    return `${tools.length} tools, foreign Origin refused`;
  }],

  ['live-the-config-we-wrote-actually-works', async () => {
    const home = makeUserHome();
    // A stable --client-id per platform+arch: every CI run reuses one node instead of minting a new
    // one each time, which is what makes registering from CI acceptable in the first place — and
    // the reuse it depends on is the feature, so this check also exercises `--client-id` live.
    const clientId = `e2e-ci-${process.platform}-${process.arch}`;
    const install = await cli(['--home', home, '--only', 'claude', '--client-id', clientId], { home });
    need(install.status === 0, `live install must succeed: ${show(install)}`);
    const entry = readJson(join(home, '.claude.json')).mcpServers.misakanet;
    const token = (entry.headers?.Authorization || '').replace(/^Bearer /, '');
    need(token.startsWith('mcp_'), 'a live install must obtain a token, otherwise the 5/day quota applies');
    need(!install.stdout.includes(token), 'the installer must not print the token');

    const listed = await mcpCall(entry.url, 'tools/list', {}, { token });
    need(listed.status === 200,
      `tools/list with our own token returned HTTP ${listed.status}: ${listed.text.slice(0, 200)}`);
    // An authenticated tool, to prove the token is *accepted* and not merely ignored.
    const preflight = await mcpCall(entry.url, 'tools/call',
      { name: 'misakanet_preflight', arguments: { intent: 'rm -rf build/' } }, { token });
    need(preflight.status === 200, `preflight returned HTTP ${preflight.status}: ${preflight.text.slice(0, 200)}`);
    need(!/unauthor|invalid token|401/i.test(preflight.text),
      `the token written into the config was rejected: ${preflight.text.slice(0, 300)}`);
    log(`live: the config the tarball wrote answers, with its bearer token accepted (client_id=${clientId})`);
    return 'the endpoint written into ~/.claude.json answers and its bearer token is accepted';
  }],
];

// ── injections: make one named check go red on purpose ───────────────────────────────────
/**
 * Each injection wraps the real CLI in a shim that runs it and then breaks exactly one promise the
 * checks depend on. The harness requires that check to fail — so every CI run also demonstrates
 * that these checks are not vacuous.
 */
const INJECTIONS = {
  'inplace-write': {
    breaks: 'a-no-op-run-does-not-touch-your-files',
    why: 'the shim rewrites the rules file in place after every run, the way a regression back to '
      + 'writeFileSync would',
    body: `
const target = join(home, '.claude', 'CLAUDE.md');
if (existsSync(target)) writeFileSync(target, readFileSync(target, 'utf8'));
`,
  },
  'leftover-temp': {
    breaks: 'no-temp-files-left-behind',
    why: 'the shim leaves a rename temp file behind, which is what an interrupted write looks like',
    body: `
const target = join(home, '.claude', 'CLAUDE.md');
if (existsSync(target)) writeFileSync(target + '.misakanet-tmp', 'half a write');
`,
  },
  'loose-secret-mode': {
    breaks: 'token-file-is-not-world-readable',
    why: 'the shim makes the token world-readable after the run',
    body: `
const token = join(home, '.misakanet-agent', 'token');
if (existsSync(token)) chmodSync(token, 0o644);
`,
  },
  'uninstall-leaves-ours': {
    breaks: 'uninstall-gives-the-config-back',
    why: 'the shim recreates the state directory after an uninstall, so the uninstall was partial',
    body: `
if (process.argv.slice(2).includes('--uninstall')) {
  mkdirSync(join(home, '.misakanet-agent'), { recursive: true });
  writeFileSync(join(home, '.misakanet-agent', 'hook.mjs'), '// left behind');
}
`,
  },
  // Semantic-equality is what the config needs; byte-equality is what the *user's file* needs. A
  // rewrite that produces the same JSON with a different trailing byte is invisible to every check
  // except a hash — and it is exactly what an "idempotent" run must not do.
  'byte-drift': {
    breaks: 'a-second-run-is-byte-identical',
    why: 'the shim appends one byte to a config after every run: same meaning, different bytes',
    body: `
const target = join(home, '.claude', 'settings.json');
if (existsSync(target)) writeFileSync(target, readFileSync(target, 'utf8') + '\\n');
`,
  },
};

function makeShim(realBin, injection) {
  const dir = scratch('shim');
  const shim = join(dir, 'shim.mjs');
  const indented = injection.body.trimEnd().split('\n').map((line) => `  ${line}`).join('\n');
  writeFileSync(shim, `// Generated by e2e-packaged-install.mjs --inject ${INJECT}.
import { spawnSync } from 'node:child_process';
import { chmodSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const home = process.env.MN_E2E_HOME || '';
const child = spawnSync(process.execPath, [${JSON.stringify(realBin)}, ...process.argv.slice(2)], {
  stdio: 'inherit',
  env: process.env,
});
// The perturbation, after the CLI has done its work.
try {
${indented}
} catch {
  // If the injection cannot apply, the check stays green and the harness reports it as broken.
}
process.exit(child.status === null ? 1 : child.status);
`);
  return shim;
}

// ── main ─────────────────────────────────────────────────────────────────────────────────
async function main() {
  if (INJECT && !INJECTIONS[INJECT]) {
    console.error(`unknown injection "${INJECT}"; known: ${Object.keys(INJECTIONS).join(', ')}`);
    return 2;
  }
  const target = INJECT ? INJECTIONS[INJECT] : null;
  if (target) ACTIVE_BIN = makeShim(INSTALLED_BIN, target);
  const list = target
    ? CHECKS.filter(([name]) => name === target.breaks)
    : [...CHECKS, ...(LIVE ? LIVE_CHECKS : [])];

  console.log(`# packaged-install e2e — prefix=${PREFIX_ABS}`);
  console.log(`# subject: ${ACTIVE_BIN}`);
  console.log(target
    ? `# injection mode: "${target.breaks}" must go red (${target.why})`
    : `# ${CHECKS.length} offline checks${LIVE ? ` + ${LIVE_CHECKS.length} live checks` : ''}`);

  for (const [name, fn] of list) await check(name, fn);

  for (const r of results) {
    const mark = r.status === 'pass' ? 'ok  ' : r.status === 'skip' ? 'skip' : 'FAIL';
    console.log(`${mark} ${r.name} — ${r.detail}`);
  }
  const failed = results.filter((r) => r.status === 'fail');
  console.log(`SETUP_E2E_METRIC ${JSON.stringify({
    prefix: PREFIX_ABS,
    injection: INJECT || null,
    live: LIVE,
    checks: results.length,
    passed: results.filter((r) => r.status === 'pass').length,
    skipped: results.filter((r) => r.status === 'skip').length,
    failed: failed.length,
    ms: results.reduce((sum, r) => sum + (r.ms || 0), 0),
  })}`);
  if (notes.length) console.log(notes.map((n) => `note: ${n}`).join('\n'));

  if (target) {
    if (results.some((r) => r.name === target.breaks && r.status === 'skip')) {
      console.error(`INJECTION NOT APPLICABLE — "${target.breaks}" is skipped on ${process.platform}, `
        + 'so it cannot be shown to have teeth here. Run this injection on a platform where it runs.');
      return 2;
    }
    if (failed.length === 1 && failed[0].name === target.breaks) {
      console.log(`INJECTION OK — "${target.breaks}" went red as required: ${failed[0].detail}`);
      return 0;
    }
    if (failed.length === 0) {
      console.error(`INJECTION BROKEN — "${target.breaks}" stayed green while the world was broken `
        + `(${target.why}). A check that cannot fail on a known-bad input is not a check.`);
      return 1;
    }
    console.error(`INJECTION UNEXPECTED — expected only "${target.breaks}" to fail, got: `
      + failed.map((r) => `${r.name}: ${r.detail}`).join(' | '));
    return 1;
  }
  if (failed.length) {
    console.error(`${failed.length} check(s) failed.`);
    return 1;
  }
  console.log(`all ${results.length} checks held.`);
  return 0;
}

if (argv.includes('--list-checks')) {
  console.log(JSON.stringify({
    checks: CHECKS.map(([name]) => name),
    live_checks: LIVE_CHECKS.map(([name]) => name),
    injections: Object.fromEntries(Object.entries(INJECTIONS).map(([k, v]) => [k, v.breaks])),
  }, null, 2));
  process.exit(0);
}

let code = 1;
try {
  code = await main();
} catch (err) {
  console.error(`e2e harness error: ${(err && err.stack) || err}`);
  code = 1;
} finally {
  if (has('--keep')) {
    console.log(`kept: ${scratchDirs.join(' ')}`);
  } else {
    for (const dir of scratchDirs) {
      try {
        rmSync(dir, { recursive: true, force: true });
      } catch { /* best effort */ }
    }
  }
}
process.exit(code);
