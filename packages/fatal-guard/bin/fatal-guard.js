#!/usr/bin/env node
/**
 * @misaka-net/fatal-guard — CLI wrapper mode
 *
 * Usage:
 *   fatal-guard [--timeout <ms>] -- <command> [args...]
 *
 * Exit codes:
 *   0  wrapped command completed successfully
 *   1  wrapped command failed or could not be started
 *   2  invalid CLI usage
 *   3  wrapped command exceeded --timeout
 */

const { spawn, spawnSync, execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { buildPayload } = require('../index');
const { redact } = require('../src/lib/redact');
const { buildSpawnSpec } = require('../src/lib/spawn-command');

const EXIT = Object.freeze({ OK: 0, ERROR: 1, USAGE: 2, TIMEOUT: 3 });
const FATAL_SIGNALS = new Set([
  'SIGKILL', 'SIGSEGV', 'SIGABRT', 'SIGBUS',
  'SIGFPE', 'SIGILL', 'SIGTRAP', 'SIGSYS',
]);
const HANDLER_TIMEOUT_MS = 1000;

function version() {
  try {
    return JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'package.json'), 'utf8')).version;
  } catch (_) {
    return 'unknown';
  }
}

function printHelp(stream = process.stdout) {
  stream.write(`Usage:
  fatal-guard [options] -- <command> [args...]

Options:
  --timeout <ms>  Stop a hung command after <ms> milliseconds (default: 0, no timeout)
  --help, -h      Show this help text
  --version, -v   Show the package version

Exit codes:
  0  command completed successfully
  1  command failed or could not be started
  2  invalid usage
  3  command timed out

Examples:
  fatal-guard -- node app.js
  fatal-guard --timeout 5000 -- node app.js
  FATAL_HANDLER=/usr/bin/logger fatal-guard -- node app.js
`);
}

function usageError(message) {
  process.stderr.write(`fatal-guard: ${message}\n`);
  process.stderr.write('Run `fatal-guard --help` for usage.\n');
  process.exit(EXIT.USAGE);
}

function parseArgs(args) {
  const options = { timeout: 0 };
  let index = 0;
  let commandStart = -1;

  while (index < args.length) {
    const arg = args[index];
    if (arg === '--') {
      commandStart = index + 1;
      break;
    }
    if (arg === '--help' || arg === '-h') {
      if (args.length !== 1) usageError('--help cannot be combined with a command');
      printHelp();
      process.exit(EXIT.OK);
    }
    if (arg === '--version' || arg === '-v') {
      if (args.length !== 1) usageError('--version cannot be combined with a command');
      process.stdout.write(`${version()}\n`);
      process.exit(EXIT.OK);
    }

    let value;
    if (arg === '--timeout') {
      if (index + 1 >= args.length) usageError('--timeout requires a value in milliseconds');
      value = args[++index];
    } else if (arg.startsWith('--timeout=')) {
      value = arg.slice('--timeout='.length);
    } else if (arg.startsWith('-')) {
      usageError(`unknown option: ${arg}`);
    } else {
      // Preserve the original wrapper syntax: `fatal-guard node app.js`.
      commandStart = index;
      break;
    }

    if (!/^\d+$/.test(value)) usageError(`invalid timeout: ${value}`);
    options.timeout = Number(value);
    if (!Number.isSafeInteger(options.timeout)) usageError(`timeout is too large: ${value}`);
    index += 1;
  }

  if (args.length === 0) usageError('missing command');
  if (commandStart < 0 || commandStart >= args.length) usageError('missing command after --');
  options.command = args.slice(commandStart);
  return options;
}

function handlerSpec() {
  return (
    process.env.FATAL_HANDLER ||
    process.env.MISAKANET_ERROR_HANDLER ||
    process.env.VITE_ERROR_HANDLER ||
    process.env.E2B_ERROR_HANDLER ||
    process.env.OPENCLAW_ERROR_HANDLER ||
    ''
  ).trim();
}

// Parse a handler command without invoking a shell. This supports the documented
// `/path/to/handler` form and simple quoted paths while keeping payloads argv-safe.
function splitCommand(value) {
  const parts = [];
  let part = '';
  let quote = '';
  let escaped = false;
  for (const char of value) {
    if (escaped) {
      part += char;
      escaped = false;
    } else if (char === '\\') {
      escaped = true;
    } else if (quote) {
      if (char === quote) quote = '';
      else part += char;
    } else if (char === '"' || char === "'") {
      quote = char;
    } else if (/\s/.test(char)) {
      if (part) {
        parts.push(part);
        part = '';
      }
    } else {
      part += char;
    }
  }
  if (escaped) part += '\\';
  if (quote) throw new Error('unterminated quote in FATAL_HANDLER');
  if (part) parts.push(part);
  return parts;
}

function reportCrash(reason, error, stderrBuffer, exitCode) {
  const handler = handlerSpec();
  const rawSnippet = stderrBuffer
    ? stderrBuffer.split('\n').filter(Boolean).slice(-4).join('\n').trim()
    : `[fatal-guard] process crashed (${reason})`;
  const payloadObj = {
    ...JSON.parse(buildPayload(reason, error)),
    errorName: error?.name || 'ProcessCrash',
    message: redact(error?.message || reason).slice(0, 500),
    stackSnippet: redact(rawSnippet).slice(0, 1000),
  };
  if (exitCode !== undefined) {
    payloadObj.exit_code = exitCode;
  }
  const payload = JSON.stringify(payloadObj);

  if (!handler) {
    process.stderr.write('fatal-guard: FATAL_HANDLER is not set; crash report was not sent.\n');
    return;
  }

  let command;
  try {
    command = splitCommand(handler);
  } catch (error) {
    process.stderr.write(`fatal-guard: invalid FATAL_HANDLER: ${error.message}\n`);
    return;
  }
  if (!command.length) {
    process.stderr.write('fatal-guard: FATAL_HANDLER is empty; crash report was not sent.\n');
    return;
  }

  let handlerArgs = [];
  if (process.env.FATAL_HANDLER_ARGS) {
    try {
      const parsed = JSON.parse(process.env.FATAL_HANDLER_ARGS);
      if (Array.isArray(parsed) && parsed.every((arg) => typeof arg === 'string')) {
        handlerArgs = parsed;
      }
    } catch (_) {}
  }
  const spawnOpts = {
    stdio: 'ignore',
    shell: false,
    windowsHide: true,
  };
  if (process.platform === 'win32') {
    // On Windows, detached processes die when the parent exits via process.exit().
    // Use execFileSync which routes through cmd.exe and reliably waits for completion.
    const payloadTmp = path.join(os.tmpdir(), `fatal-guard-${process.pid}.json`);
    try { fs.writeFileSync(payloadTmp, payload); } catch (_) {}
    const invocation = buildSpawnSpec(command[0], [...command.slice(1), ...handlerArgs]);
    try {
      execFileSync(invocation.command, invocation.args, {
        timeout: HANDLER_TIMEOUT_MS,
        stdio: 'ignore',
        env: { ...process.env, FATAL_PAYLOAD_FILE: payloadTmp },
        windowsHide: true,
      });
    } catch (_) {}
  } else {
    const invocation = buildSpawnSpec(command[0], [...command.slice(1), ...handlerArgs, payload]);
    const reporter = spawn(invocation.command, invocation.args, {
      ...spawnOpts,
      ...invocation.options,
      detached: true,
    });
    reporter.on('error', () => {});
    reporter.unref();
  }
}

function main() {
  const { command, timeout } = parseArgs(process.argv.slice(2));
  const stderrIsTTY = !!process.stderr.isTTY;
  const child = spawn(command[0], command.slice(1), {
    stdio: ['inherit', 'inherit', stderrIsTTY ? 'inherit' : 'pipe'],
    shell: false,
  });

  let stderrBuffer = '';
  let spawnError = null;
  let timedOut = false;
  let finished = false;
  let timeoutTimer;
  if (!stderrIsTTY && child.stderr) {
    child.stderr.on('data', (chunk) => {
      stderrBuffer += chunk.toString();
      process.stderr.write(chunk);
    });
  }
  if (timeout > 0) {
    timeoutTimer = setTimeout(() => {
      timedOut = true;
      process.stderr.write(`fatal-guard: command timed out after ${timeout}ms: ${command.join(' ')}\n`);
      child.kill('SIGTERM');
      setTimeout(() => {
        if (!finished) child.kill('SIGKILL');
      }, 100);
    }, timeout);
  }

  child.on('error', (error) => {
    spawnError = error;
    process.stderr.write(`fatal-guard: could not start command "${command[0]}": ${error.message}\n`);
  });
  child.on('close', (code, signal) => {
    finished = true;
    if (timeoutTimer) clearTimeout(timeoutTimer);
    if (timedOut) {
      reportCrash('timeout', new Error(`command timed out after ${timeout}ms`), stderrBuffer, EXIT.TIMEOUT);
      process.exit(EXIT.TIMEOUT);
    }
    if (spawnError) process.exit(EXIT.ERROR);
    const crashed = Boolean((code !== 0 && code !== null) || (signal && FATAL_SIGNALS.has(signal)));
    const hasError = Boolean(signal && FATAL_SIGNALS.has(signal)) || stderrIsTTY
      || /error|exception|traceback|failed|fatal|killed/i.test(stderrBuffer);
    if (crashed && hasError) {
      const reason = signal ? `killed_by_${signal}` : 'process_crash';
      reportCrash(reason, new Error(`exit code: ${code}, signal: ${signal || 'none'}`), stderrBuffer, code);
    }
    process.exit(code ?? EXIT.ERROR);
  });
}

main();
