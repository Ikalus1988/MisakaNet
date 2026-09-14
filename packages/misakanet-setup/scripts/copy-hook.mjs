#!/usr/bin/env node
// Copy the canonical hook into the package at pack/publish time.
//
// The hook lives in integrations/agent-autostart/ (one source of truth, tested by
// workers/agent-autostart-hook.test.mjs). Shipping a copy in the tarball means `npx
// @misaka-net/misakanet-setup` does not have to download anything at install time - which
// matters on networks where GitHub raw is unreachable, i.e. exactly where a one-command
// installer is the only kind that works.
import { copyFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, '..', '..', '..', 'integrations', 'agent-autostart', 'checkpoint_reminder.mjs');
const destDir = resolve(here, '..', 'hook');
const dest = join(destDir, 'checkpoint_reminder.mjs');

if (!existsSync(src)) {
  console.error(`copy-hook: source not found at ${src}`);
  process.exit(1);
}
mkdirSync(destDir, { recursive: true });
copyFileSync(src, dest);
console.log(`copy-hook: ${dest}`);
