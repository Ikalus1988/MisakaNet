// tests/dsh/install.test.mjs
// Installation and loading tests for the MisakaNet DSH plugin.
import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..', '..');

test('package.json contains required dsh configuration', () => {
  const pkg = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8'));
  assert.ok(pkg.dsh, 'package.json must have a "dsh" field');
  assert.ok(pkg.dsh.bundle, 'dsh must have a "bundle" field');
  assert.ok(pkg.dsh.bundle.patch, 'dsh.bundle must have a "patch" field');
  assert.ok(pkg.dsh.client, 'dsh must have a "client" field');
  assert.equal(typeof pkg.dsh.client.platform, 'string', 'dsh.client.platform must be a string');
});

test('main entry point exports expected API', async () => {
  const mod = await import(join(ROOT, 'index.js'));
  assert.equal(mod.name, 'misakanet', 'plugin must export name "misakanet"');
  assert.equal(typeof mod.apply, 'function', 'plugin must export an apply function');
});

test('apply function is callable without throwing', async () => {
  const mod = await import(join(ROOT, 'index.js'));
  // Mock cordis context — apply should be inert
  const mockCtx = {};
  assert.doesNotThrow(() => mod.apply(mockCtx, {}), 'apply() must not throw');
  assert.doesNotThrow(() => mod.apply(mockCtx), 'apply() without config must not throw');
});

test('SKILL.md exists and is non-empty', () => {
  const skillPath = join(ROOT, 'SKILL.md');
  assert.ok(existsSync(skillPath), 'SKILL.md must exist');
  const content = readFileSync(skillPath, 'utf8');
  assert.ok(content.length > 100, 'SKILL.md must be non-trivial (>100 chars)');
  assert.ok(content.includes('misakanet') || content.includes('MisakaNet'),
    'SKILL.md should reference MisakaNet');
});

test('cordis.patch.yml exists and is valid YAML', () => {
  const patchPath = join(ROOT, 'cordis.patch.yml');
  assert.ok(existsSync(patchPath), 'cordis.patch.yml must exist');
  const content = readFileSync(patchPath, 'utf8');
  assert.ok(content.length > 10, 'cordis.patch.yml must not be empty');
  // Basic YAML sanity: should contain key identifiers
  assert.ok(content.includes('misakanet') || content.includes('bundle'),
    'cordis.patch.yml should reference the plugin');
});

test('package.json "files" field includes dsh essentials', () => {
  const pkg = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8'));
  assert.ok(Array.isArray(pkg.files), '"files" must be an array');
  assert.ok(pkg.files.includes('SKILL.md'), 'files must include SKILL.md');
  assert.ok(pkg.files.includes('index.js'), 'files must include index.js');
  assert.ok(pkg.files.some(f => f.includes('cordis')), 'files must include cordis patch');
});
