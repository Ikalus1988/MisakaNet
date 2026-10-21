/**
 * Build a shell-free child-process invocation for Unix and Windows.
 *
 * Windows `.cmd`/`.bat` files are not directly executable with CreateProcess.
 * Routing only those extensions through ComSpec keeps normal commands on the
 * safe direct-spawn path while preserving PATH lookup for PowerShell/cmd
 * workflows used by the CLI.
 *
 * Security (CodeQL js/shell-command-injection-from-environment):
 * the `command` may originate from an env var (FATAL_HANDLER). We reject any
 * command containing shell metacharacters before it can reach a shell
 * interpreter, so the env-derived value is never an "uncontrolled command".
 */

const SHELL_METACHARS = /[;&|<>$`(){}]|\r|\n/;
// A shell interpreter invoked with arguments (spaces) is itself a shell sink:
// `cmd /c evil`, `sh -c evil`, `bash -c evil` would execute arbitrary commands
// even though they contain no metacharacters. Reject those too.
const SHELL_INTERPRETERS = /^(?:cmd(?:\.exe)?|sh|bash|zsh|dash|ksh|powershell(?:\.exe)?|pwsh(?:\.exe)?|python|python3|node|perl|ruby)\b/i;

/**
 * How long a handler may run before it is killed.
 *
 * One budget for the whole package (#3645): the CLI wrapper used 1000 ms while
 * the in-process path used 5000 ms, so the same handler was cut off on Windows
 * depending on how the program was started. A handler that searches the network
 * and writes a draft lesson needs seconds, not one.
 */
const HANDLER_TIMEOUT_MS = 5000;

function quoteWindowsArg(value) {
  const text = String(value);
  if (!/[\s"&|<>^]/.test(text)) return text;
  return `"${text.replace(/["^]/g, (match) => `^${match}`)}"`;
}

/**
 * Validate a handler command. Returns the command unchanged if safe, or null
 * if it contains shell metacharacters or is a shell interpreter invoked with
 * arguments (which would let an env-derived value smuggle a shell command
 * through the win32 cmd.exe wrapper).
 * @param {string} command
 * @returns {string|null}
 */
function sanitizeCommand(command) {
  if (typeof command !== 'string' || !command.trim()) return null;
  if (command.trim() !== command) return null;           // no leading/trailing whitespace tricks
  if (command.startsWith('-')) return null;               // no option injection
  if (SHELL_METACHARS.test(command)) return null;         // no shell metacharacters
  if (/\s/.test(command) && SHELL_INTERPRETERS.test(command)) return null;
  return command;
}

/**
 * Split a handler command string into program + arguments without a shell.
 *
 * `FATAL_HANDLER` is documented in both forms — `/usr/bin/logger` and
 * `node /opt/bin/handler.js` — so the string has to be tokenized before it is
 * spawned. This mirrors what the CLI wrapper has always done; the in-process
 * path passed the raw string to `sanitizeCommand`, which refused anything with
 * a space (`node /opt/bin/handler.js` looks like a shell interpreter with
 * arguments) and silently dropped the report (#3645).
 *
 * The tokens are still validated afterwards: `sanitizeCommand` sees the program
 * only, and the spawn is always `shell: false`, so no token reaches a shell.
 *
 * On Windows, backslashes are path separators (not escape characters).
 */
function splitCommand(value) {
  const isWindows = process.platform === 'win32';
  const parts = [];
  let part = '';
  let quote = '';
  let escaped = false;
  for (const char of value) {
    if (escaped) {
      part += char;
      escaped = false;
    } else if (char === '\\' && !isWindows) {
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

function buildSpawnSpec(command, args = []) {
  const safe = sanitizeCommand(command);
  if (safe === null) {
    return { command: '', args: [], options: {}, rejected: true };
  }
  const isWindowsScript = process.platform === 'win32' && /\.(?:cmd|bat)$/i.test(safe);
  if (!isWindowsScript) {
    return { command: safe, args, options: {} };
  }
  const shellCommand = [safe, ...args].map(quoteWindowsArg).join(' ');
  return {
    command: process.env.ComSpec || 'cmd.exe',
    args: ['/d', '/s', '/c', shellCommand],
    options: { windowsHide: true },
  };
}

module.exports = { buildSpawnSpec, quoteWindowsArg, sanitizeCommand, splitCommand, HANDLER_TIMEOUT_MS };
