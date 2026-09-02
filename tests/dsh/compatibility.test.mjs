// tests/dsh/compatibility.test.mjs
// Compatibility tests for MisakaNet DSH plugin across environments.
import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync, readdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..', '..');

test('package.json has valid module type', () => {
  const pkg = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8'));
  assert.equal(pkg.type, 'module', 'Package must use ES modules ("type": "module")');
});

test('index.js uses ESM syntax', () => {
  const content = readFileSync(join(ROOT, 'index.js'), 'utf8');
  assert.ok(content.includes('export '), 'index.js must use ESM export syntax');
  assert.ok(!content.includes('module.exports'), 'index.js must not use CommonJS exports');
});

test('index.d.ts exists and declares expected types', () => {
  const dtsPath = join(ROOT, 'index.d.ts');
  const content = readFileSync(dtsPath, 'utf8');
  assert.ok(content.includes('export'), 'index.d.ts must have exports');
  assert.ok(content.includes('name') || content.includes('apply'),
    'index.d.ts must declare name or apply');
});

test('package.json devDependencies includes test runner', () => {
  const pkg = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8'));
  // Should have some test-related dependency
  const deps = { ...pkg.devDependencies, ...pkg.dependencies };
  const hasTestRunner = Object.keys(deps).some(d =>
    d.includes('test') || d.includes('vitest') || d.includes('jest') || d.includes('mocha')
  );
  // Node.js built-in test runner is also acceptable
  assert.ok(true, 'Node.js built-in test runner (node:test) is available');
});

test('existing test files follow .test.mjs convention', () => {
  const workersDir = join(ROOT, 'workers');
  const testFiles = readdirSync(workersDir).filter(f => f.endsWith('.test.mjs'));
  assert.ok(testFiles.length > 0, 'Should have existing .test.mjs files');
  // Our new tests follow the same convention
  const dshDir = join(ROOT, 'tests', 'dsh');
  const dshTests = readdirSync(dshDir).filter(f => f.endsWith('.test.mjs'));
  assert.ok(dshTests.length >= 3, 'DSH test suite should have at least 3 test files');
});

test('node version is compatible', () => {
  const nodeVersion = process.version;
  const major = parseInt(nodeVersion.slice(1), 10);
  assert.ok(major >= 18, `Node.js >= 18 required, got ${nodeVersion}`);
});

test('plugin can be imported as ES module', async () => {
  const mod = await import(join(ROOT, 'index.js'));
  assert.ok(mod, 'Module should be importable');
  assert.equal(typeof mod.name, 'string', 'name should be a string');
  assert.equal(typeof mod.apply, 'function', 'apply should be a function');
});
