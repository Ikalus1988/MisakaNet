'use strict';

/**
 * DSH Harness Executor — PowerShell-safe execution layer
 *
 * Addresses the Windows PowerShell inline command double-escaping trap.
 *
 * Core principle: NEVER inline complex commands. Always write to files first.
 *
 * Problem summary (from issue #3111):
 *   - Host tool says "pwsh -Command" but runner is Windows PowerShell 5.1
 *   - PS 5.1 does not support: ternary `? :`, `&&` / `||`, assumes UTF-8 BOM for unicode .ps1
 *   - `node -e "..."` gets double-consumed: PS layer first, then JS layer
 *   - Failures are often SILENT (exit code 0, wrong path/data)
 *
 * Fix: Use file-based script execution exclusively for anything with
 * quotes, multi-line content, JSON, or SQL.
 */

const { runNodeScript, runPowerShellScript, sqlLiteral } = require('./run_node');
const fs = require('fs');
const path = require('path');

/**
 * Execute arbitrary JS logic without ever touching `node -e`.
 *
 * @param {string} jsScript — raw JavaScript source code
 * @returns {{success: boolean, stdout: string, stderr: string, exitCode: number}}
 */
function execNode(jsScript) {
  console.log('[execNode] Writing script to temp file, bypassing PS inline layer');
  return runNodeScript(jsScript);
}

/**
 * Execute a PowerShell script via .ps1 file (NOT -Command).
 * UTF-8 BOM is prepended automatically for unicode support.
 *
 * @param {string} psScript — raw PowerShell source code
 * @returns {{success: boolean, stdout: string, stderr: string, exitCode: number}}
 */
function execPowerShell(psScript) {
  console.log('[execPS] Writing script to .ps1 file, bypassing PS -Command inline layer');
  return runPowerShellScript(psScript);
}

/**
 * Build a safe SELECT query with proper string literal quoting.
 * Uses single quotes for strings; double quotes are reserved for identifiers.
 *
 * @param {string} table
 * @param {string[]} columns
 * @param {object} [conditions] — key-value WHERE clauses
 * @returns {string} safe SQL query
 */
function buildSelectQuery(table, columns, conditions) {
  const cols = columns.map(c => (c === '*' ? '*' : c)).join(', ');
  let sql = `SELECT ${cols} FROM ${table}`;

  if (conditions && Object.keys(conditions).length > 0) {
    const clauses = Object.entries(conditions).map(([k, v]) => {
      if (typeof v === 'string' && v.includes('%')) {
        // LIKE pattern — wrap in single quotes
        return `${k} LIKE ${sqlLiteral(v)}`;
      }
      return `${k} = ${sqlLiteral(String(v))}`;
    });
    sql += ' WHERE ' + clauses.join(' AND ');
  }

  return sql;
}

/**
 * Verify that the target environment is actually pwsh (7.x), not just
 * Windows PowerShell 5.1. Logs a warning if version mismatch detected.
 *
 * @returns {object} version info
 */
function checkPowerShellVersion() {
  const result = runPowerShellScript(`
    Write-Output ("PSVersion=" + $PSVersionTable.PSVersion.ToString())
    Write-Output ("PSEdition=" + $PSVersionTable.PSEdition)
    $pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
    Write-Output ("pwsh_in_PATH=" + ($pwsh -ne $null).ToString())
  `);

  const lines = (result.stdout || '').split('\n').filter(Boolean);
  const info = {};
  for (const line of lines) {
    const [key, val] = line.split('=');
    if (key && val !== undefined) info[key] = val.trim();
  }

  if (info.PSEdition === 'Desktop') {
    console.warn(
      '[version_check] WARNING: Target is Windows PowerShell 5.1 (Desktop), NOT pwsh 7.x.' +
      '\n  · Ternary operator (? :) is NOT supported' +
      '\n  · && / || chaining is NOT supported' +
      '\n  · Non-BOM UTF-8 .ps1 files may corrupt unicode content'
    );
  }

  return info;
}

module.exports = {
  execNode,
  execPowerShell,
  buildSelectQuery,
  checkPowerShellVersion,
  sqlLiteral,
};
