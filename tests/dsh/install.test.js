import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '../..');

describe('MisakaNet DSH Plugin - Installation & Packaging Tests', () => {
  const packageJsonPath = path.join(REPO_ROOT, 'package.json');
  const indexJsPath = path.join(REPO_ROOT, 'index.js');
  const skillMdPath = path.join(REPO_ROOT, 'SKILL.md');
  const skillsDir = path.join(REPO_ROOT, 'skills', 'misakanet');

  it('1.1 should have valid package.json with required DSH plugin manifest fields', () => {
    assert.ok(fs.existsSync(packageJsonPath), 'package.json must exist');
    const pkg = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));

    assert.equal(pkg.name, 'misakanet');
    assert.ok(pkg.version, 'package version must be defined');
    assert.equal(pkg.main, 'index.js');
    assert.equal(pkg.type, 'module');
    assert.ok(Array.isArray(pkg.files), 'files array must be present');
    assert.ok(pkg.files.includes('SKILL.md'), 'files must include SKILL.md');
    assert.ok(pkg.files.includes('skills/'), 'files must include skills/');
    assert.ok(pkg.files.includes('index.js'), 'files must include index.js');
  });

  it('1.2 should export valid apply() and name in index.js for DSH host compatibility', async () => {
    assert.ok(fs.existsSync(indexJsPath), 'index.js must exist');
    const indexModule = await import(`file://${indexJsPath.replace(/\\/g, '/')}`);

    assert.equal(indexModule.name, 'misakanet');
    assert.equal(typeof indexModule.apply, 'function', 'apply must be an exported function');

    // Executing apply() should be a safe no-op that does not throw
    const mockContext = {};
    assert.doesNotThrow(() => {
      indexModule.apply(mockContext, {});
    }, 'apply() should safely execute without runtime errors');
  });

  it('1.3 should support manual skill directory discovery and layout', () => {
    assert.ok(fs.existsSync(skillMdPath), 'Root SKILL.md must exist');
    assert.ok(fs.existsSync(skillsDir), 'skills/misakanet directory must exist');

    const skillInSubdir = path.join(skillsDir, 'SKILL.md');
    assert.ok(fs.existsSync(skillInSubdir), 'skills/misakanet/SKILL.md must exist');

    const skillContent = fs.readFileSync(skillMdPath, 'utf8');
    assert.ok(skillContent.includes('misakanet'), 'SKILL.md should document misakanet');
    assert.ok(skillContent.includes('MCP') || skillContent.includes('mcp'), 'SKILL.md should document MCP usage');
  });

  it('1.4 should maintain cross-platform path compatibility across Windows, Linux, macOS', () => {
    const posixPath = 'skills/misakanet/SKILL.md';
    const resolvedPath = path.resolve(REPO_ROOT, posixPath);
    assert.ok(fs.existsSync(resolvedPath), `Path ${resolvedPath} should resolve regardless of host OS`);

    const normalized = path.normalize(posixPath);
    assert.ok(normalized.includes('misakanet'), 'Path normalization must preserve component names');
  });

  it('1.5 should be compatible with modern Node.js versions (>=18)', () => {
    const nodeMajor = parseInt(process.versions.node.split('.')[0], 10);
    assert.ok(nodeMajor >= 18, `Current Node.js version (${process.versions.node}) must be >= 18`);
  });
});
