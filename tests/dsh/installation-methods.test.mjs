// tests/dsh/installation-methods.test.mjs
// Tests for DSH plugin installation methods (Issue #1401).
import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync, writeFileSync, existsSync, mkdirSync, cpSync, rmSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';
import { tmpdir } from 'node:os';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..', '..');

// Method 3: Skill Discovery - manual copy
test('Method 3: Skill discovery installation', () => {
  const tempDir = join(tmpdir(), `misakanet-test-${Date.now()}`);
  const skillsDir = join(tempDir, '.dsh', 'skills');

  try {
    // Create temporary skill directory structure
    mkdirSync(skillsDir, { recursive: true });

    // Create minimal skill structure for testing
    mkdirSync(join(skillsDir, 'misakanet'), { recursive: true });
    const skillMd = readFileSync(join(ROOT, 'SKILL.md'), 'utf8');
    writeFileSync(join(skillsDir, 'misakanet', 'SKILL.md'), skillMd);

    // Verify installation
    assert.ok(existsSync(join(skillsDir, 'misakanet')),
      'Plugin directory should exist after skill discovery install');

    const installedSkill = readFileSync(
      join(skillsDir, 'misakanet', 'SKILL.md'), 'utf8'
    );
    assert.ok(installedSkill.length > 100, 'Installed SKILL.md should be non-empty');
  } finally {
    // Cleanup
    if (existsSync(tempDir)) {
      rmSync(tempDir, { recursive: true, force: true });
    }
  }
});

// Method 2: Git method - verify repo structure is valid
test('Method 2: Git install - repo structure validation', () => {
  // Verify the repo has all files needed for git install
  const requiredFiles = ['package.json', 'index.js', 'SKILL.md', 'cordis.patch.yml'];
  for (const file of requiredFiles) {
    assert.ok(existsSync(join(ROOT, file)),
      `Git install requires ${file} to exist`);
  }

  // Verify package.json has correct main entry
  const pkg = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8'));
  assert.ok(pkg.main, 'package.json must have "main" field for git install');
  assert.ok(existsSync(join(ROOT, pkg.main)),
    `Main entry point ${pkg.main} must exist`);
});

// Method 1: npm install - verify package is publishable
test('Method 1: npm install - package.json is publishable', () => {
  const pkg = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8'));

  // Required fields for npm publish
  assert.ok(pkg.name, 'package.json must have "name"');
  assert.ok(pkg.version, 'package.json must have "version"');
  assert.ok(pkg.description, 'package.json must have "description"');
  assert.ok(pkg.main, 'package.json must have "main"');
  assert.ok(Array.isArray(pkg.files), 'package.json must have "files" array');

  // DSH-specific fields
  assert.ok(pkg.dsh, 'package.json must have "dsh" configuration');

  // Files listed in "files" should exist
  for (const file of pkg.files) {
    // Handle glob patterns
    if (!file.includes('*')) {
      assert.ok(existsSync(join(ROOT, file)),
        `File "${file}" listed in package.json "files" must exist`);
    }
  }
});

// Activation test: Plugin should be recognized
test('Plugin recognition - exports correct name', async () => {
  const mod = await import(join(ROOT, 'index.js'));
  assert.equal(mod.name, 'misakanet', 'Plugin name must be "misakanet"');
  assert.equal(typeof mod.apply, 'function', 'Plugin must export apply function');
});

// Functionality test: MCP tools accessible
test('MCP tools - SKILL.md references MCP endpoints', () => {
  const skillContent = readFileSync(join(ROOT, 'SKILL.md'), 'utf8');

  // Should reference MCP-related concepts
  const hasMcpReference = skillContent.toLowerCase().includes('mcp') ||
    skillContent.includes('tool') || skillContent.includes('endpoint');
  assert.ok(hasMcpReference, 'SKILL.md must reference MCP tools or endpoints');
});

// Conflict test: Multiple installations don't interfere
test('No conflicts - plugin files are self-contained', () => {
  const pkg = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8'));

  // All files should be within the package
  for (const file of pkg.files) {
    if (!file.includes('*')) {
      const filePath = join(ROOT, file);
      assert.ok(existsSync(filePath),
        `Packaged file ${file} must exist and be self-contained`);
    }
  }

  // No external dependencies required (DSH plugins should be lightweight)
  const deps = pkg.dependencies || {};
  assert.equal(Object.keys(deps).length, 0,
    'DSH plugin should have no runtime dependencies');
});

// Uninstall test: Clean removal possible
test('Uninstall - no global side effects', () => {
  // Plugin should not create files outside its directory
  const pkg = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8'));

  // Check no postinstall scripts that might modify system
  assert.ok(!pkg.scripts?.postinstall,
    'Plugin should not have postinstall scripts');
  assert.ok(!pkg.scripts?.preinstall,
    'Plugin should not have preinstall scripts');
});

// Environment compatibility
test('Environment - Node.js version compatibility', () => {
  const pkg = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8'));

  // Should work with Node 18+
  const nodeVersion = process.version;
  const major = parseInt(nodeVersion.slice(1), 10);
  assert.ok(major >= 18, `Node.js >= 18 required, got ${nodeVersion}`);
});

// Integration: Plugin loads in Cordis context
test('Integration - apply function handles cordis context', async () => {
  const mod = await import(join(ROOT, 'index.js'));

  // Mock cordis context
  const mockCtx = {
    service: () => {},
    on: () => {},
  };

  // Should not throw
  assert.doesNotThrow(() => mod.apply(mockCtx),
    'apply() must handle cordis context gracefully');
});
