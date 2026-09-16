#!/usr/bin/env node
// Copy the canonical hook into the package at pack/publish time.
//
// The hook lives in integrations/agent-autostart/ (one source of truth, tested by
// workers/agent-autostart-hook.test.mjs). Shipping a copy in the tarball means `npx
// @misaka-net/misakanet-setup` does not have to download anything at install time - which
// matters on networks where GitHub raw is unreachable, i.e. exactly where a one-command
// installer is the only kind that works.
import { copyFileSync, mkdirSync, existsSync, readdirSync } from 'node:fs';
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

// The voice hook (opt-in, `--voice`): the player plus the four cues it maps to. The player
// gets the same one-source-of-truth treatment as the checkpoint hook — canonical copy in
// integrations/agent-autostart/, shipped in the tarball so an install never has to download
// anything (which is exactly where a one-command installer has to work).
const voiceSrc = resolve(here, '..', '..', '..', 'integrations', 'agent-autostart', 'voice_hook.mjs');
const voiceDestDir = resolve(here, '..', 'voice');
const voiceDest = join(voiceDestDir, 'voice-hook.mjs');
const cueSrcDir = resolve(here, '..', '..', '..', 'docs', 'assets', 'voice');

if (!existsSync(voiceSrc)) {
  console.error(`copy-hook: voice player not found at ${voiceSrc}`);
  process.exit(1);
}
mkdirSync(voiceDestDir, { recursive: true });
copyFileSync(voiceSrc, voiceDest);
console.log(`copy-hook: ${voiceDest}`);

const cues = existsSync(cueSrcDir)
  ? readdirSync(cueSrcDir).filter((f) => f.endsWith('.mp3'))
  : [];
for (const cue of cues) {
  copyFileSync(join(cueSrcDir, cue), join(voiceDestDir, cue));
}
console.log(`copy-hook: ${cues.length} voice cue(s) → ${voiceDestDir}`);
