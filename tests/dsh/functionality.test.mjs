// tests/dsh/functionality.test.mjs
// Functional tests for MisakaNet DSH plugin behavior.
import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..', '..');

test('SKILL.md contains MCP endpoint reference', () => {
  const content = readFileSync(join(ROOT, 'SKILL.md'), 'utf8');
  assert.ok(content.includes('mcp') || content.includes('MCP'),
    'SKILL.md must reference MCP endpoints');
});

test('SKILL.md contains lesson search workflow', () => {
  const content = readFileSync(join(ROOT, 'SKILL.md'), 'utf8');
  const hasSearch = content.includes('search') || content.includes('Search') ||
    content.includes('lesson') || content.includes('Lesson');
  assert.ok(hasSearch, 'SKILL.md must describe a search/lesson workflow');
});

test('SKILL.md contains failure recording workflow', () => {
  const content = readFileSync(join(ROOT, 'SKILL.md'), 'utf8');
  const hasRecord = content.includes('record') || content.includes('Record') ||
    content.includes('submit') || content.includes('Submit') ||
    content.includes('intake') || content.includes('Intake');
  assert.ok(hasRecord, 'SKILL.md must describe a failure recording workflow');
});

test('index.js apply accepts config parameter', async () => {
  const mod = await import(join(ROOT, 'index.js'));
  let receivedConfig = null;
  const mockCtx = {
    // Capture config if apply tries to use it
  };
  // Should not throw with various config shapes
  assert.doesNotThrow(() => mod.apply(mockCtx, { verbose: true }));
  assert.doesNotThrow(() => mod.apply(mockCtx, { enabled: false }));
  assert.doesNotThrow(() => mod.apply(mockCtx, { apiKey: 'test' }));
});

test('plugin name is consistent across package.json and index.js', async () => {
  const pkg = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8'));
  const mod = await import(join(ROOT, 'index.js'));
  // package.json "name" and index.js "name" should match
  // Note: package.json name may have scope, so check contains
  assert.ok(
    pkg.name.includes('misakanet') || pkg.name === 'misakanet',
    `package.json name "${pkg.name}" should reference misakanet`
  );
  assert.equal(mod.name, 'misakanet', 'index.js name must be "misakanet"');
});

test('SKILL.md contains actionable content', () => {
  const content = readFileSync(join(ROOT, 'SKILL.md'), 'utf8');
  // Should contain meaningful content about the skill
  const hasContent = content.length > 200;
  assert.ok(hasContent, 'SKILL.md must contain substantial content');
  // Should reference key concepts
  const hasKeyConcept = content.includes('lesson') || content.includes('failure') ||
    content.includes('skill') || content.includes('mcp');
  assert.ok(hasKeyConcept, 'SKILL.md must reference key MisakaNet concepts');
});

test('plugin exports only expected properties', async () => {
  const mod = await import(join(ROOT, 'index.js'));
  const exports = Object.keys(mod);
  assert.deepEqual(exports.sort(), ['apply', 'name'],
    'Plugin should only export "name" and "apply"');
});
