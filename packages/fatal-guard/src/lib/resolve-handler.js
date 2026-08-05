'use strict';

const fs   = require('node:fs');
const path = require('node:path');

/**
 * Resolve & validate an external handler binary path.
 * Defends against env-injection RCE (audit item A2).
 *
 *  - must be inside HANDLER_ALLOWLIST_DIRS
 *  - must be a regular file (not symlink to outside, not dir, not socket)
 *  - must be executable
 *  - must NOT be group/other writable (prevents low-priv overwrite)
 */

const HANDLER_ALLOWLIST_DIRS = [
  '/opt/misakanet/handlers',
  '/usr/local/lib/fatal-guard',
];

function resolveHandler(raw) {
  if (!raw || typeof raw !== 'string') return null;
  let abs;
  try { abs = fs.realpathSync(path.resolve(raw)); } catch { return null; }
  const ok = HANDLER_ALLOWLIST_DIRS.some(
    (d) => abs === d || abs.startsWith(d + path.sep)
  );
  if (!ok) return null;

  let st;
  try { st = fs.lstatSync(abs); } catch { return null; }
  if (!st.isFile()) return null;
  if ((st.mode & 0o022) !== 0) return null;
  try { fs.accessSync(abs, fs.constants.X_OK); } catch { return null; }
  return abs;
}

module.exports = { resolveHandler, HANDLER_ALLOWLIST_DIRS };
