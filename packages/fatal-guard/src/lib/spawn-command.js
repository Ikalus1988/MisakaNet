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

module.exports = { buildSpawnSpec, quoteWindowsArg, sanitizeCommand };
