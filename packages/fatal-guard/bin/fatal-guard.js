#!/usr/bin/env node
/**
 * @misaka-net/fatal-guard — CLI wrapper mode
 *
 * Usage:
 *   npx @misaka-net/fatal-guard -- <command> [args...]
 *   FATAL_HANDLER=/usr/bin/logger npx @misaka-net/fatal-guard -- node app.js
 *
 * Spawns the command as a child process, monitors stderr and exit code,
 * fires the external handler on non-zero exit with crash signal.
 */

const { spawn } = require('node:child_process');

const args = process.argv.slice(2);

if (args.length === 0 || args[0] === '--help' || args[0] === '-h') {
  console.error(`
Usage:
  FATAL_HANDLER=/usr/bin/logger npx @misaka-net/fatal-guard -- <command> [args...]

Examples:
  npx @misaka-net/fatal-guard -- node app.js
  FATAL_HANDLER=/usr/bin/logger npx @misaka-net/fatal-guard -- ./node_modules/.bin/vite build

Wraps any Node.js CLI with fatal error monitoring — zero source code changes.
`);
  process.exit(args.length === 0 ? 1 : 0);
}

// Remove leading `--` if present (allows `fatal-guard -- cmd` syntax)
let cmdArgs = args;
if (cmdArgs[0] === '--') {
  cmdArgs = cmdArgs.slice(1);
}

if (cmdArgs.length === 0) {
  console.error('fatal-guard: missing command after --');
  process.exit(1);
}

const { buildPayload, runHandler } = require('../index');
const { redact } = require('../src/lib/redact');

// ── TTY detection ────────────────────────────────────────────────
// If parent stderr is a TTY, inherit it so child processes see a real TTY
// (preserves ANSI colors and interactive behavior).  Otherwise pipe stderr
// to capture error output for crash detection + snippet.
const stderrIsTTY = !!process.stderr.isTTY;

const child = spawn(cmdArgs[0], cmdArgs.slice(1), {
  stdio: ['inherit', 'inherit', stderrIsTTY ? 'inherit' : 'pipe'],
  shell: false,
});

// ── stderr capture (only when piping, i.e. non-TTY) ─────────────
let stderrBuffer = '';
if (!stderrIsTTY && child.stderr) {
  child.stderr.on('data', (chunk) => {
    stderrBuffer += chunk.toString();
    process.stderr.write(chunk); // pass through to user terminal
  });
}

// ── Crash detection ─────────────────────────────────────────────
// Signals that indicate a fatal/crash condition (not graceful shutdown).
// SIGKILL = OOM killer / force kill; SIGSEGV = segfault; SIGABRT = abort
const FATAL_SIGNALS = new Set(['SIGKILL', 'SIGSEGV', 'SIGABRT', 'SIGBUS', 'SIGFPE', 'SIGILL', 'SIGTRAP', 'SIGSYS']);

child.on('exit', (code, signal) => {
  // Crashed if: non-zero exit code  OR  killed by a fatal signal
  const crashed = Boolean((code !== 0 && code !== null) || (signal && FATAL_SIGNALS.has(signal)));
  // When killed by a fatal signal (OOM/SIGSEGV/etc.), skip text check —
  // the signal itself is evidence of a crash, and the process may have died
  // before writing any error output to stderr.
  const killedByFatalSignal = signal && FATAL_SIGNALS.has(signal);
  const hasError = killedByFatalSignal || stderrIsTTY
    ? true
    : /error|exception|traceback|failed|fatal|killed/i.test(stderrBuffer);

  if (crashed && hasError) {
    const reason = signal ? `killed_by_${signal}` : 'process_crash';
    try {
      const rawSnippet = stderrBuffer
        ? stderrBuffer.split('\n').filter(Boolean).slice(-4).join('\n').trim()
        : `[fatal-guard] process crashed (exit code: ${code}, signal: ${signal})`;
      const snippet = redact(rawSnippet).slice(0, 1000);
      const payload = JSON.stringify({
        ...JSON.parse(buildPayload(reason)),
        errorName: signal ? `Signal:${signal}` : 'ProcessCrash',
        message: `exit code: ${code}, signal: ${signal}`,
        stackSnippet: snippet,
      });
      runHandler(reason, null, payload);
    } catch (_) {}
  }

  process.exit(code ?? 1);
});

child.on('error', () => {
  process.exit(1);
});
