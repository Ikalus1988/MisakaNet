// Tests for the agent auto-start hook (integrations/agent-autostart/checkpoint_reminder.mjs).
//
// This file is not a worker; it lives in workers/ because that is the glob CI runs
// (`node --test workers/*.test.mjs` in mcp-stress.yml), and an untested hook is how the
// Python version shipped a silent no-op for anyone without Python.
//
// The hook is exercised as a subprocess, exactly as Claude Code runs it: JSON on stdin,
// text to inject on stdout. Run: node --test workers/agent-autostart-hook.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

const HOOK = resolve(import.meta.dirname, '..', 'integrations', 'agent-autostart', 'checkpoint_reminder.mjs');

function runHook(payload, mode = 'prompt', env = {}) {
  const state = env.MISAKANET_HOOK_STATE || mkdtempSync(join(tmpdir(), 'mn-hook-'));
  // Never read the developer's own ~/.misakanet-agent: a version stamp sitting there (this
  // machine has one after installing) would make the upgrade nudge appear in unrelated tests.
  const agentDir = env.MISAKANET_AGENT_DIR || mkdtempSync(join(tmpdir(), 'mn-agent-'));
  const result = spawnSync(process.execPath, [HOOK, mode], {
    input: typeof payload === 'string' ? payload : JSON.stringify(payload),
    encoding: 'utf8',
    env: {
      ...process.env,
      MISAKANET_HOOK_STATE: state,
      MISAKANET_AGENT_DIR: agentDir,
      ...env,
    },
  });
  assert.equal(result.status, 0, `hooks must never break the session: ${result.stderr}`);
  return { stdout: result.stdout, state, agentDir };
}

test('announces itself on the first turn, then stays silent until the checkpoint', () => {
  const state = mkdtempSync(join(tmpdir(), 'mn-hook-'));
  const env = { MISAKANET_HOOK_STATE: state };
  // Turn 1 carries the self-announcement: a user who cannot inspect any config file learns
  // the install worked only if the assistant says so.
  const first = runHook({ session_id: 's' }, 'prompt', env).stdout;
  assert.match(first, /已接入失败经验库/, 'the first turn must carry the announcement');
  assert.match(first, /把 MisakaNet 关掉/, 'and how to undo it, in plain words');
  for (let turn = 2; turn < 20; turn += 1) {
    assert.equal(runHook({ session_id: 's' }, 'prompt', env).stdout, '', `turn ${turn} should be silent`);
  }
  const at20 = runHook({ session_id: 's' }, 'prompt', env).stdout;
  assert.match(at20, /检查点/);
  assert.match(at20, /20/);
  for (let turn = 21; turn < 30; turn += 1) {
    assert.equal(runHook({ session_id: 's' }, 'prompt', env).stdout, '', `turn ${turn} should be silent`);
  }
  assert.match(runHook({ session_id: 's' }, 'prompt', env).stdout, /30/, 'must fire again at 30');
  assert.equal(JSON.parse(readFileSync(join(state, 's.json'), 'utf8')).turn, 30);
});

test('sessions are counted independently', () => {
  const state = mkdtempSync(join(tmpdir(), 'mn-hook-'));
  runHook({ session_id: 'a' }, 'prompt', { MISAKANET_HOOK_STATE: state });
  runHook({ session_id: 'b' }, 'prompt', { MISAKANET_HOOK_STATE: state });
  assert.equal(JSON.parse(readFileSync(join(state, 'a.json'), 'utf8')).turn, 1);
  assert.equal(JSON.parse(readFileSync(join(state, 'b.json'), 'utf8')).turn, 1);
});

test('the threshold is configurable', () => {
  // Share one state dir: a fresh one per call would reset the counter to turn 1 and the
  // checkpoint could never be reached (that is how this test failed the first time).
  const state = mkdtempSync(join(tmpdir(), 'mn-hook-'));
  const env = { MISAKANET_HOOK_STATE: state, MISAKANET_CHECKPOINT_AT: '2', MISAKANET_CHECKPOINT_EVERY: '0' };
  assert.doesNotMatch(runHook({ session_id: 's' }, 'prompt', env).stdout, /检查点/, 'turn 1 is below the threshold');
  assert.match(runHook({ session_id: 's' }, 'prompt', env).stdout, /检查点/);
});

test('failure mode searches the error text, not the command', () => {
  const { stdout } = runHook(
    { tool_input: { command: 'docker compose up' }, error: 'Error response from daemon: exit code 137' },
    'failure',
  );
  assert.match(stdout, /exit code 137/);
  assert.doesNotMatch(stdout, /docker compose up/);
});

test('failure mode falls back to the command when there is no error text', () => {
  const { stdout } = runHook({ tool_input: { command: 'npm run build' } }, 'failure');
  assert.match(stdout, /npm run build/);
});

test('junk input never crashes, and garbage produces nothing', () => {
  for (const payload of ['', 'not json', '[1,2,3]']) {
    for (const mode of ['prompt', 'failure']) {
      assert.equal(runHook(payload, mode).stdout, '', `${mode} must ignore ${JSON.stringify(payload)}`);
    }
  }
  // '{}' is a valid empty payload on the default session, so turn 1 legitimately announces;
  // the property under test is "no crash, nothing but our own text".
  const empty = runHook('{}', 'prompt').stdout;
  assert.doesNotMatch(empty, /Error|Traceback|undefined/, empty);
});

test('an unknown mode does not crash', () => {
  assert.equal(runHook({ session_id: 's' }, 'wat').stdout, '');
});

test('the injected text is valid UTF-8 Chinese, not mojibake', () => {
  const env = { MISAKANET_CHECKPOINT_AT: '1', MISAKANET_CHECKPOINT_EVERY: '0' };
  const { stdout } = runHook({ session_id: 's' }, 'prompt', env);
  assert.match(stdout, /脱敏/, 'the reminder must reach the agent as readable text');
  assert.ok(!stdout.includes('\uFFFD'), 'no replacement characters in the output');
});

// ── the upgrade nudge (issue #1682) ─────────────────────────────────────────
// The installer stamps ~/.misakanet-agent/version; the hook decides whether to mention an
// upgrade at most once every 14 days. The hook never asks the registry itself — that is the
// agent's one cheap call — so what these tests pin is the *cadence*, which is the whole point:
// every session would be noise, and never would let users forget the tool is installed.

function agentDirWithStamp(daysAgo) {
  const dir = mkdtempSync(join(tmpdir(), 'mn-agent-'));
  const when = new Date(Date.now() - daysAgo * 24 * 60 * 60 * 1000).toISOString();
  writeFileSync(join(dir, 'version'), JSON.stringify({
    package: '@misaka-net/misakanet-setup', version: '0.3.0', installed_at: when,
  }));
  return dir;
}

test('a fresh install is not nudged', () => {
  const agentDir = agentDirWithStamp(1);
  const env = { MISAKANET_AGENT_DIR: agentDir, MISAKANET_HOOK_STATE: mkdtempSync(join(tmpdir(), 'mn-hook-')) };
  runHook({ session_id: 's' }, 'prompt', env);            // turn 1 (announcement only)
  const { stdout } = runHook({ session_id: 's' }, 'prompt', env);
  assert.equal(stdout, '', `nothing to say one day after installing: ${stdout}`);
});

test('an install older than the interval is nudged once, then quiet again', () => {
  const agentDir = agentDirWithStamp(15);
  // The throttle rides with the session state dir (same machine state, one place a user who
  // set MISAKANET_HOOK_STATE has to look).
  const hookState = mkdtempSync(join(tmpdir(), 'mn-hook-'));
  const env = { MISAKANET_AGENT_DIR: agentDir, MISAKANET_HOOK_STATE: hookState };
  const first = runHook({ session_id: 's' }, 'prompt', env).stdout;   // turn 1
  assert.match(first, /距上次确认已超过 14 天/, first);
  assert.match(first, /npm view @misaka-net\/misakanet-setup version/, 'the agent needs the exact command');
  assert.match(first, /npx @misaka-net\/misakanet-setup@latest/, 'and the upgrade command verbatim');

  for (const turn of [2, 3, 4]) {
    const { stdout } = runHook({ session_id: 's' }, 'prompt', env);
    assert.equal(stdout, '', `turn ${turn} must not repeat the nudge`);
  }
  assert.match(readFileSync(join(hookState, 'update-check.json'), 'utf8'), /last_asked/,
    'the throttle state is what makes the next 14 days quiet');
});

test('the nudge honours the opt-out, and stays silent when there is no stamp', () => {
  const old = agentDirWithStamp(15);
  const optedStateDir = mkdtempSync(join(tmpdir(), 'mn-hook-'));
  const opted = runHook({ session_id: 's' }, 'prompt',
    { MISAKANET_AGENT_DIR: old, MISAKANET_HOOK_STATE: optedStateDir, MISAKANET_NO_UPDATE_NOTICE: '1' }).stdout;
  assert.doesNotMatch(opted, /距上次确认/, opted);
  assert.ok(!existsSync(join(optedStateDir, 'update-check.json')),
    'an opted-out user must not accumulate throttle state either');

  const unstamped = mkdtempSync(join(tmpdir(), 'mn-agent-'));   // installed before stamping
  const legacy = runHook({ session_id: 's' }, 'prompt', { MISAKANET_AGENT_DIR: unstamped }).stdout;
  assert.doesNotMatch(legacy, /距上次确认/, legacy);
});

test('the interval is configurable, and upgrading resets the clock', () => {
  const dir = agentDirWithStamp(3);
  const env = { MISAKANET_AGENT_DIR: dir, MISAKANET_UPDATE_AFTER_DAYS: '2' };
  const { stdout } = runHook({ session_id: 's' }, 'prompt', env);
  assert.match(stdout, /超过 2 天/, stdout);

  // A re-install of a NEWER version moves installed_at forward; the timer restarts from there
  // even though the throttle file is still recent.
  const fresh = agentDirWithStamp(0);
  const reset = runHook({ session_id: 's' }, 'prompt',
    { MISAKANET_AGENT_DIR: fresh, MISAKANET_UPDATE_AFTER_DAYS: '1' }).stdout;
  assert.doesNotMatch(reset, /距上次确认/, reset);
});
