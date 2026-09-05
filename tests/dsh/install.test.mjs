// dsh plugin installation contract tests.
// Run: node --test tests/dsh/install.test.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

import { importModule, makeTempDir, readJson, repoRoot, run } from './dsh-test-helpers.mjs';

test('npm package includes the files dsh needs for plugin installation', async () => {
  const command = process.platform === 'win32' ? (process.env.ComSpec || 'cmd.exe') : 'npm';
  const args = process.platform === 'win32'
    ? ['/d', '/s', '/c', 'npm pack --dry-run --json']
    : ['pack', '--dry-run', '--json'];
  const { code, stdout, stderr } = await run(command, args);
  assert.equal(code, 0, stderr);
  const [pack] = JSON.parse(stdout);
  const files = new Set(pack.files.map((entry) => entry.path));

  for (const required of ['package.json', 'index.js', 'index.d.ts', 'SKILL.md', 'skills/misakanet/SKILL.md']) {
    assert.ok(files.has(required), `npm pack should include ${required}`);
  }

  assert.ok(!files.has('dsh.bundle.patch'), 'MisakaNet must stay a library plugin, not a Cordis loader patch');
});

test('git/manual checkout exposes an importable no-op dsh plugin entry', async () => {
  const plugin = await importModule(path.join(repoRoot, 'index.js'));
  assert.equal(plugin.name, 'misakanet');
  assert.equal(typeof plugin.apply, 'function');
  assert.doesNotThrow(() => plugin.apply({ services: new Map() }, { mcpUrl: 'https://misakanet.org/mcp' }));
});

test('manual file-copy install can be imported from a node_modules package directory', async () => {
  const tmp = makeTempDir();
  const packageDir = path.join(tmp, 'node_modules', 'misakanet');
  fs.mkdirSync(packageDir, { recursive: true });

  for (const file of ['package.json', 'index.js', 'index.d.ts', 'SKILL.md']) {
    fs.copyFileSync(path.join(repoRoot, file), path.join(packageDir, file));
  }
  fs.cpSync(path.join(repoRoot, 'skills'), path.join(packageDir, 'skills'), { recursive: true });

  const plugin = await importModule(path.join(packageDir, 'index.js'));
  assert.equal(plugin.name, 'misakanet');
  assert.equal(typeof plugin.apply, 'function');
});

test('package metadata advertises a dependency-free ESM plugin surface', () => {
  const pkg = readJson('package.json');
  assert.equal(pkg.name, 'misakanet');
  assert.equal(pkg.type, 'module');
  assert.equal(pkg.main, 'index.js');
  assert.equal(pkg.types, 'index.d.ts');
  assert.deepEqual(pkg.dependencies ?? {}, {});
  assert.ok(pkg.files.includes('SKILL.md'));
  assert.ok(pkg.files.includes('skills/'));
});
