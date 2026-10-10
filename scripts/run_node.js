'use strict';

const { execFileSync, spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

/**
 * Executes a Node.js script written to a temporary file.
 * This avoids PowerShell inline double-escaping issues entirely.
 *
 * WHY: `node -e "..."` in Windows PowerShell 5.1 suffers from:
 *   1) PS expands `$variables` before JS sees them (often to empty strings)
 *   2) PS consumes escape sequences (`\U \A \L \T \x`) before JS engine
 *   3) Quotes inside the JS string terminate the PS outer string early
 *   4) Failures are often SILENT — exit code 0 but wrong output
 *
 * SOLUTION: Write the JS to a .js file and execute the file.
 * File contents are bytes, not tokens — zero PS lexical analysis layer.
 */
function runNodeScript(scriptContent) {
  const tmpDir = process.env.TMPDIR || process.env.TEMP || process.env.TMP || 'C:\\Windows\\Temp';
  const tmpFile = path.join(tmpDir, 'misakascript_' + Date.now() + '.js');

  // Write the script as raw bytes — no PS layer at all
  fs.writeFileSync(tmpFile, scriptContent, 'utf8');

  try {
    const result = execFileSync('node', [tmpFile], {
      encoding: 'utf8',
      timeout: 60000,
    });
    return { success: true, stdout: result, stderr: '', exitCode: 0 };
  } catch (err) {
    return {
      success: false,
      stdout: err.stdout || '',
      stderr: err.stderr || '',
      exitCode: err.status || 1,
    };
  } finally {
    try { fs.unlinkSync(tmpFile); } catch (_) { /* ignore cleanup errors */ }
  }
}

/**
 * Executes a PowerShell command using ps1 file execution.
 * Avoids inline `-Command` double-escaping traps.
 */
function runPowerShellScript(scriptContent) {
  const tmpDir = process.env.TMPDIR || process.env.TEMP || process.env.TMP || 'C:\\Windows\\Temp';
  // Must use BOM for Chinese/unicode content in PS 5.1
  const bom = '\uFEFF';
  const tmpFile = path.join(tmpDir, 'misakascript_' + Date.now() + '.ps1');

  fs.writeFileSync(tmpFile, bom + scriptContent, 'utf8');

  try {
    const result = execFileSync('powershell.exe', ['-ExecutionPolicy', 'Bypass', '-File', tmpFile], {
      encoding: 'utf8',
      timeout: 60000,
    });
    return { success: true, stdout: result, stderr: '', exitCode: 0 };
  } catch (err) {
    return {
      success: false,
      stdout: err.stdout || '',
      stderr: err.stderr || '',
      exitCode: err.status || 1,
    };
  } finally {
    try { fs.unlinkSync(tmpFile); } catch (_) { /* ignore cleanup errors */ }
  }
}

/**
 * Safe SQLite query: always uses single quotes for string literals.
 * Double quotes in SQL are identifier ref quotes, NOT string literals.
 * e.g. `"events"` → column name, not string "events"
 */
function sqlLiteral(str) {
  return "'" + str.replace(/'/g, "''") + "'";
}

module.exports = { runNodeScript, runPowerShellScript, sqlLiteral };
