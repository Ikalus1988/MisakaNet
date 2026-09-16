#!/usr/bin/env node
/**
 * MisakaNet attention hook — route the cue a tool result asked for to a sound and/or a
 * desktop notification.
 *
 * The MCP server already answers with a `voice` field (`lesson-found` when a search hit,
 * `failure-warning` when it did not, `connect-success` for a lesson, `pair-success` for a
 * usage receipt). This hook turns that field into attention: a sound, and — because the
 * *model* cannot see that a tool ran and neither can the human watching — a short desktop
 * notification. It is registered as a Claude Code `PostToolUse` hook by
 * `npx @misaka-net/misakanet-setup --voice`, and it is *opt-in*: nobody wants an assistant
 * that starts talking on its own.
 *
 * Why Node and not the older shell script: that one parses stdin with `python`, and `python`
 * is not on PATH on many Linux/WSL boxes (`python3` is) — this repo has that exact bug on
 * record. Node is guaranteed here: the installer itself runs on it.
 *
 * Rules it must never break:
 * - **never block the agent**: players and notifiers are spawned detached and the process
 *   exits immediately, with a hard timeout as a backstop;
 * - **never fail loudly**: a missing player, a missing notification binary, a missing MP3,
 *   an unwritable state file or unparsable stdin all end in exit 0 with no output, because a
 *   hook that prints to stderr can show up as a tool error;
 * - **be silent when asked**: `MISAKANET_VOICE=0` mutes sound *and* notifications even after
 *   it is installed, and `MISAKANET_NOTIFY=0` turns off only the notifications;
 * - **never execute anything derived from server input**: see the table below.
 *
 * Test/debug affordances:
 * - `MISAKANET_VOICE_DRY_RUN=1` prints the cue name and what the hook *would* do — sound and
 *   notification — while executing nothing (that is what the test suite uses, so CI never
 *   needs an audio device or a desktop session);
 * - `MISAKANET_VOICE_DEBUG=1` prints one line per real run: cue, player, file, notification;
 * - `MISAKANET_VOICE_DIR` overrides where the MP3s live;
 * - `MISAKANET_HOOK_STATE` (shared with `checkpoint_reminder.mjs`) overrides the state
 *   directory that holds the "already notified once" ledger.
 */
import { spawn } from 'node:child_process';
import { accessSync, constants, existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { delimiter, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));

/**
 * THE TABLE — the single place a cue name turns into something this process does.
 *
 * ─── HARD SECURITY RULE (issue #1785) ──────────────────────────────────────────────────
 * The cue is **server-supplied** and is used for exactly one thing: as a *key* into this
 * table. It is never concatenated into a command line, never concatenated into a path,
 * never handed to a shell, and never passed as an argument to any process. Every executable
 * name, every argument, every MP3 file name and every notification text executed by this
 * hook is a literal written in this file.
 *
 * An unknown cue — including `rm -rf /`, a cue full of `;`/`$()`/backticks, or a 5000
 * character cue — matches no key, so there is no action: the hook exits 0 having done
 * nothing at all, and reaches no binary. `workers/agent-autostart-hook.test.mjs` asserts
 * this by running the hook with a stubbed PATH (every player and notifier replaced by a
 * recording stub) and requiring the recording to stay empty.
 * ──────────────────────────────────────────────────────────────────────────────────────
 *
 * Three more decisions worth stating:
 * - `sound` is the MP3 **file name, spelled out**, rather than `${cue}.mp3`: the file name is
 *   then not built out of server input either, so there is no interpolation left to argue
 *   about.
 * - `once: true` means "notify only the first time this cue is seen on this machine". Both
 *   success cues repeat on every single call (a lesson fetch, a receipt), and a toast per
 *   call is exactly the noise that makes people mute the whole feature; the ledger that
 *   remembers this lives in the state directory (see `ledgerMark`).
 * - `notify: ''` for `failure-warning` is deliberate: "no lesson found" is a *negative*
 *   result the agent is already telling the user about, and it happens on every empty
 *   search — a notification there buys nothing and costs attention. Sound only, as the
 *   issue's acceptance criteria require. The issue drafted 「MisakaNet：未找到相关经验，已记录」
 *   for it; that string is deliberately not wired to anything, and is recorded here only so
 *   a future translation pass knows it was considered and dropped.
 */
const CUE_ACTIONS = Object.freeze({
  'lesson-found': Object.freeze({
    sound: 'lesson-found.mp3',
    notify: 'MisakaNet：找到一条相关经验',
    once: false,
  }),
  'failure-warning': Object.freeze({
    sound: 'failure-warning.mp3',
    notify: '',                                   // sound only — see above
    once: false,
  }),
  'connect-success': Object.freeze({
    sound: 'connect-success.mp3',
    notify: 'MisakaNet：已连接',
    once: true,
  }),
  'pair-success': Object.freeze({
    sound: 'pair-success.mp3',
    notify: 'MisakaNet：已连接',
    once: true,
  }),
});

const CUES = Object.keys(CUE_ACTIONS);

/**
 * Find the first cue name anywhere in the payload.
 *
 * Two nests are real, not hypothetical (both observed on 2026-09-16 with Claude Code):
 *  * `tool_response` is the MCP result, so the cue is one level down;
 *  * for an MCP tool that value is a **JSON string**, not an object — the whole response is
 *    escaped inside it. Descending only into objects therefore found nothing even when the
 *    server had sent the cue.
 */
function findCue(value, depth = 0) {
  if (depth > 8) return '';
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) return '';
    try {
      return findCue(JSON.parse(trimmed), depth + 1);
    } catch {
      return '';
    }
  }
  if (value === null || typeof value !== 'object') return '';
  if (typeof value.voice === 'string' && CUES.includes(value.voice)) return value.voice;
  for (const child of Array.isArray(value) ? value : Object.values(value)) {
    const found = findCue(child, depth + 1);
    if (found) return found;
  }
  return '';
}

function readStdin() {
  try {
    return readFileSync(0, 'utf8');
  } catch {
    return '';
  }
}

function parseCue(raw) {
  if (!raw) return '';
  const trimmed = raw.trim();
  // Claude Code writes one JSON object per line; the CLI sends the whole document.
  for (const candidate of [trimmed, ...trimmed.split('\n')]) {
    try {
      const cue = findCue(JSON.parse(candidate));
      if (cue) return cue;
    } catch {
      /* try the next shape */
    }
  }
  // Last resort: a bare cue name on its own line, so a hand-rolled hook still works.
  //
  // The whole line must *be* the cue name. A fuzzy "contains a cue name" match would mean a
  // hostile string like `lesson-found; notify-send pwned` routes to the legitimately-tabled
  // `lesson-found` action: no injection happens either way (the action comes from the table),
  // but "a cue we did not send triggers an action" is not a contract worth keeping. An exact
  // match is also what lets the security test below demand *no* action for hostile input.
  for (const line of trimmed.split('\n')) {
    const bare = line.trim();
    if (CUES.includes(bare)) return bare;
  }
  return '';
}

/** The path Windows needs, for the WSL case. */
function windowsPathFor(file) {
  const drive = file.match(/^\/mnt\/([a-z])\/(.*)$/);
  if (drive) return `${drive[1].toUpperCase()}:\\${drive[2].replace(/\//g, '\\')}`;
  const distro = process.env.WSL_DISTRO_NAME;
  if (distro && file.startsWith('/')) {
    return `\\\\wsl.localhost\\${distro}${file.replace(/\//g, '\\')}`;
  }
  return '';
}

function isWsl() {
  return Boolean(process.env.WSL_DISTRO_NAME || process.env.WSL_INTEROP);
}

/**
 * Players in preference order, with the reason each one is where it is.
 *
 * `aplay` is deliberately absent: the assets are MP3 and aplay only plays raw/WAV, so the
 * older shell script's ALSA branch was silent on exactly the machines that reached it.
 *
 * On WSL the Windows side comes **first**, and that is not a detail: measured on this
 * machine, `ffplay` cannot open an ALSA card at all in WSL ("cannot find card '0'"), so the
 * local-player branch installs a hook that never makes a sound. PowerShell's
 * presentationCore plays the same file by URI through Windows audio — verified by asking it
 * for the duration it had loaded (4.2s for `lesson-found`).
 */
function players(file) {
  const winPath = windowsPathFor(file);
  const powershell = winPath
    ? [
        'powershell.exe',
        [
          '-NoProfile',
          '-Command',
          'Add-Type -AssemblyName presentationCore;'
            + '$p = New-Object System.Windows.Media.MediaPlayer;'
            + `$p.Open([uri]'${winPath}'); $p.Play(); Start-Sleep -Seconds 6`,
        ],
      ]
    : null;
  const local = [
    ['afplay', [file]], // macOS
    ['paplay', [file]], // Linux (PulseAudio)
    ['ffplay', ['-nodisp', '-autoexit', '-loglevel', 'quiet', file]],
    ['mpv', ['--no-video', '--really-quiet', file]],
    ['mpg123', ['-q', file]],
    ['cvlc', ['--play-and-exit', '--intf', 'dummy', file]],
  ];
  return powershell && isWsl() ? [powershell, ...local] : [...local, ...(powershell ? [powershell] : [])];
}

function play(file) {
  for (const [cmd, args] of players(file)) {
    try {
      const child = spawn(cmd, args, { detached: true, stdio: 'ignore' });
      child.on('error', () => {});
      child.unref();
      return cmd;
    } catch {
      /* try the next player */
    }
  }
  return '';
}

/**
 * Where the "already notified once" ledger lives.
 *
 * The installer already owns `~/.misakanet-agent/` (it writes the version stamp and
 * checkpoints state there), so the voice hook writes its one small file in the same place
 * instead of inventing a second home-directory convention. `MISAKANET_HOOK_STATE` is the
 * same override `checkpoint_reminder.mjs` honours, which is also how the test suite keeps
 * these files out of a developer's real home.
 */
const AGENT_DIR = process.env.MISAKANET_AGENT_DIR || join(homedir(), '.misakanet-agent');
const STATE_DIR = process.env.MISAKANET_HOOK_STATE || join(AGENT_DIR, 'state');
const NOTIFY_LEDGER = join(STATE_DIR, 'voice-notified.json');

function ledgerRead() {
  try {
    const raw = JSON.parse(readFileSync(NOTIFY_LEDGER, 'utf8'));
    return raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : {};
  } catch {
    return {};                            // missing or unreadable: nothing has been announced
  }
}

/**
 * Remember that `cue` has been announced, atomically (temp file + rename, so a hook killed
 * mid-write cannot leave half a JSON file behind).
 *
 * Every failure here is swallowed on purpose: this is bookkeeping for a courtesy, and a
 * read-only home directory must not be able to turn a desktop notification into a tool
 * error. The worst case of a lost write is one extra toast after a reboot.
 *
 * The key is always a key of `CUE_ACTIONS` (see the security rule there) — never raw input.
 */
function ledgerMark(cue) {
  try {
    mkdirSync(dirname(NOTIFY_LEDGER), { recursive: true });
    const next = { ...ledgerRead(), [cue]: new Date().toISOString() };
    const tmp = `${NOTIFY_LEDGER}.tmp`;
    writeFileSync(tmp, JSON.stringify(next));
    renameSync(tmp, NOTIFY_LEDGER);
  } catch {
    /* never break the agent over bookkeeping */
  }
}

/**
 * Is `name` an executable we can actually run? (A plain PATH walk — never `which`, because
 * spawning a shell to answer "does X exist" is the execution surface this hook must not
 * have.)
 *
 * Deliberate, rather than spawn-and-swallow-the-ENOENT: a machine with no notifier at all
 * then forks nothing on every tool call, and the debug/dry-run line can name the notifier it
 * really would use instead of guessing. `name` always comes from the code table below.
 */
function findExecutable(name) {
  const path = process.env.PATH || '/usr/local/bin:/usr/bin:/bin';
  for (const entry of path.split(delimiter)) {
    const dir = entry.trim().replace(/^"(.*)"$/, '$1');
    if (!dir) continue;
    try {
      accessSync(join(dir, name), constants.X_OK);
      return join(dir, name);
    } catch {
      /* keep looking */
    }
  }
  return '';
}

/**
 * The notifier candidates for *this* platform, in preference order.
 *
 * Every binary name and every argument below is a literal; the only thing that varies is the
 * message text, which is a literal in `CUE_ACTIONS`. Nothing in this function looks at the
 * cue — that is the whole point of the table.
 *
 * - **macOS**: `osascript -e 'display notification "…" with title "MisakaNet"'`.
 * - **Linux**: `notify-send -a MisakaNet <text>` (the freedesktop notifier every desktop
 *   environment ships).
 * - **Windows / WSL**: PowerShell. The real WinRT toast API
 *   (`Windows.UI.Notifications.ToastNotificationManager`) needs a registered AppID — a
 *   Start-menu shortcut with the right AUMID — and on a clean machine it fails with
 *   "Element not found", which a hook can only swallow. The dependency-free call that does
 *   work from a bare `powershell.exe` is a `NotifyIcon` balloon, which Windows 10/11 renders
 *   through the same Action Center; that is the documented fallback. On WSL the Windows side
 *   goes **first**, exactly like the player, because the Linux side of WSL usually has no
 *   notification daemon to talk to (and, as `players` records, no usable audio card either).
 *
 * `powershell.exe` over argv carries the message text; PowerShell single quotes are escaped
 * by doubling, and the string itself is a constant from the table.
 */
function notifiers(text) {
  const winText = `'${text.replace(/'/g, "''")}'`;
  const powershell = [
    'powershell.exe',
    [
      '-NoProfile',
      '-NonInteractive',
      '-Command',
      'Add-Type -AssemblyName System.Windows.Forms;'
        + 'Add-Type -AssemblyName System.Drawing;'
        + '$n = New-Object System.Windows.Forms.NotifyIcon;'
        + '$n.Icon = [System.Drawing.SystemIcons]::Information;'
        + "$n.BalloonTipTitle = 'MisakaNet';"
        + `$n.BalloonTipText = ${winText};`
        + '$n.Visible = $true; $n.ShowBalloonTip(5000);'
        + 'Start-Sleep -Seconds 6; $n.Dispose()',
    ],
  ];
  const candidates = [];
  if (isWsl() || process.platform === 'win32') candidates.push(powershell);
  if (process.platform === 'darwin') {
    const escaped = text.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
    candidates.push(['osascript', ['-e', `display notification "${escaped}" with title "MisakaNet"`]]);
  }
  if (process.platform === 'linux') candidates.push(['notify-send', ['-a', 'MisakaNet', text]]);
  return candidates;
}

/**
 * Best-effort desktop notification. Returns the binary that was used, or ''.
 *
 * Missing binary, missing platform, denied dbus, a `spawn` throw — all of them mean "no
 * notification happened", which is a silent outcome by design: this hook must never print an
 * error that surfaces as a tool failure in the middle of someone's session.
 */
function notify(text) {
  for (const [cmd, args] of notifiers(text)) {
    if (!findExecutable(cmd)) continue;
    try {
      const child = spawn(cmd, args, { detached: true, stdio: 'ignore' });
      child.on('error', () => {});
      child.unref();
      return cmd;
    } catch {
      /* try the next notifier */
    }
  }
  return '';
}

/**
 * The MP3 for a table entry, or ''.
 *
 * The cues sit next to the player when it is installed (…/voice/), next to the canonical
 * copy in a repo checkout, or under docs/assets/voice/ there. Getting this wrong is silent
 * by design — which is exactly how the first version of this file shipped mute. `name` is a
 * literal from `CUE_ACTIONS`, never the cue.
 */
function cueFile(name) {
  const dirs = [
    process.env.MISAKANET_VOICE_DIR,
    HERE,
    join(HERE, 'voice'),
    join(HERE, '..', '..', 'docs', 'assets', 'voice'),
  ].filter(Boolean);
  return dirs.map((dir) => join(dir, name)).find((candidate) => existsSync(candidate)) || '';
}

function main() {
  // One switch silences both halves: sound *and* notifications.
  if (process.env.MISAKANET_VOICE === '0') return;
  const cue = parseCue(readStdin());
  if (!cue) return;

  // ── the cue's only use, right here: a table lookup ────────────────────────────────
  const action = CUE_ACTIONS[cue];
  if (!action) return;               // unreachable (parseCue only returns table keys), and
                                     // keeping it explicit is what makes the rule total:
                                     // no table entry ⇒ no action, no process, no path.
  const dryRun = process.env.MISAKANET_VOICE_DRY_RUN === '1';
  const notifyAllowed = process.env.MISAKANET_NOTIFY !== '0';
  const debug = process.env.MISAKANET_VOICE_DEBUG === '1';

  // ── sound ────────────────────────────────────────────────────────────────────────
  const file = cueFile(action.sound);
  const would = file ? `sound=${action.sound} (would play)` : `sound=${action.sound} (missing — would be silent)`;
  const player = dryRun || !file ? '' : play(file);

  // ── notification ─────────────────────────────────────────────────────────────────
  let note;
  if (!action.notify) {
    note = 'none (this cue does not notify)';
  } else if (!notifyAllowed) {
    note = 'disabled (MISAKANET_NOTIFY=0)';
  } else {
    const seen = action.once ? ledgerRead()[cue] : '';
    if (seen) {
      note = `already sent at ${seen} (first time only)`;
    } else if (dryRun) {
      note = `would send "${action.notify}"${action.once ? ' (first time only)' : ''}`;
    } else {
      const used = notify(action.notify);
      // Marked even when no notifier was available: otherwise a machine without one would
      // retry the lookup on every single tool call forever, for a toast nobody can see.
      if (action.once) ledgerMark(cue);
      note = used ? `${used} "${action.notify}"` : 'none (no notifier available on this platform)';
    }
  }

  if (dryRun) {
    // Reports both halves and executes neither. Read-only on purpose: a preview must not
    // consume the one-time notification or write a ledger a real run would then trust.
    process.stdout.write(`${cue}\n${would}\nnotify=${note}\n`);
    return;
  }
  if (debug) {
    // Synchronous write: process.exit(0) below would truncate an async stdout write, and a
    // hook that prints on the normal path can look like a tool failure.
    writeFileSync(1, `cue=${cue} player=${player || 'none'} file=${file || 'none'} notify=${note}\n`);
  }
}

try {
  main();
} catch {
  /* a hook must never surface as a tool failure */
} finally {
  process.exit(0);
}

// Backstop: if a detached player leaves this process alive (some players keep a handle),
// leave anyway. The sound is best-effort by design.
setTimeout(() => process.exit(0), 3000).unref();
