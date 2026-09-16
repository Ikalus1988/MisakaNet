#!/usr/bin/env node
/**
 * MisakaNet voice hook — play the cue a tool result asked for.
 *
 * The MCP server already answers with a `voice` field (`lesson-found` when a search hit,
 * `failure-warning` when it did not, `connect-success` for a lesson, `pair-success` for a
 * usage receipt). This hook turns that field into a sound. It is registered as a Claude Code
 * `PostToolUse` hook by `npx @misaka-net/misakanet-setup --voice`, and it is *opt-in*: nobody
 * wants an assistant that starts talking on its own.
 *
 * Why Node and not the older shell script: that one parses stdin with `python`, and `python`
 * is not on PATH on many Linux/WSL boxes (`python3` is) — this repo has that exact bug on
 * record. Node is guaranteed here: the installer itself runs on it.
 *
 * Rules it must never break:
 * - **never block the agent**: the player is spawned detached and the process exits
 *   immediately, with a hard timeout as a backstop;
 * - **never fail loudly**: a missing player, a missing MP3 or unparsable stdin all end in
 *   exit 0 with no output, because a hook that prints to stderr can show up as a tool error;
 * - **be silent when asked**: `MISAKANET_VOICE=0` mutes it even after it is installed.
 *
 * Test/debug affordances:
 * - `MISAKANET_VOICE_DRY_RUN=1` prints the cue name instead of playing it (that is what the
 *   test suite uses, so CI never needs an audio device);
 * - `MISAKANET_VOICE_DIR` overrides where the MP3s live.
 */
import { spawn } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const CUES = ['connect-success', 'pair-success', 'lesson-found', 'failure-warning'];

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
  // Last resort: a bare cue name on the line, so a hand-rolled hook still works.
  const bare = trimmed.match(new RegExp(`\\b(${CUES.join('|')})\\b`));
  return bare ? bare[1] : '';
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

function main() {
  if (process.env.MISAKANET_VOICE === '0') return;
  const cue = parseCue(readStdin());
  if (!cue) return;

  if (process.env.MISAKANET_VOICE_DRY_RUN === '1') {
    process.stdout.write(`${cue}\n`);
    return;
  }

  // The cues sit next to the player when it is installed (…/voice/), next to the canonical
  // copy in a repo checkout, or under docs/assets/voice/ there. Getting this wrong is silent
  // by design — which is exactly how the first version of this file shipped mute.
  const dirs = [
    process.env.MISAKANET_VOICE_DIR,
    HERE,
    join(HERE, 'voice'),
    join(HERE, '..', '..', 'docs', 'assets', 'voice'),
  ].filter(Boolean);
  const file = dirs.map((dir) => join(dir, `${cue}.mp3`)).find((candidate) => existsSync(candidate));
  if (!file) return;
  const used = play(file);
  if (process.env.MISAKANET_VOICE_DEBUG === '1') {
    // Synchronous write: process.exit(0) below would truncate an async stdout write, and a
    // hook that prints on the normal path can look like a tool failure.
    writeFileSync(1, `cue=${cue} player=${used || 'none'} file=${file}\n`);
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
