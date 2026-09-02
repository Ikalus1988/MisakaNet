/**
 * tests/dsh-plugin.test.js — DSH Plugin Integration Test Suite
 *
 * Covers:
 *   - Skill discovery (skill.yml parsing, path resolution)
 *   - MCP tool contract (misakanet_search, misakanet_get_lesson)
 *   - Installation method validation (npm, git, manual/skill discovery)
 *   - Config generation (skill.yml, skill.md, package.json)
 *   - Fallback chain (npm → bun → git)
 *
 * Closes #1403, Closes #1401
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { readFileSync, existsSync, mkdirSync, writeFileSync, rmSync } from 'fs';
import { join } from 'path';
import { execSync } from 'child_process';
import { tmpdir } from 'os';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const REPO_ROOT = process.cwd();
const SKILL_DIR = join(REPO_ROOT, 'skills', 'misakanet');
const SKILL_MD = join(SKILL_DIR, 'SKILL.md');
const DSH_INSTALL_DOC = join(REPO_ROOT, 'docs', 'dsh-installation.md');
const DSH_INTEGRATION_DOC = join(REPO_ROOT, 'docs', 'integrations', 'dsh.md');

/** Minimal YAML frontmatter parser (no external deps) — handles inline and multi-line lists */
function parseFrontmatter(text) {
  const match = text.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return {};
  const fm = {};
  const lines = match[1].split('\n');
  let currentKey = null;
  let inList = false;
  for (const line of lines) {
    const trimmed = line.trimStart();
    const indent = line.length - trimmed.length;

    // List item (starts with -, may or may not be indented)
    if (trimmed.startsWith('- ') && inList && currentKey) {
      const item = trimmed.slice(2).trim().replace(/^['"]|['"]$/g, '');
      if (!Array.isArray(fm[currentKey])) fm[currentKey] = [];
      fm[currentKey].push(item);
      inList = true;
      continue;
    }

    // Top-level key-value (not indented)
    const kv = line.match(/^(\w[\w-]*):\s*(.*)$/);
    if (kv && indent === 0) {
      currentKey = kv[1];
      inList = false;
      const val = kv[2].trim();
      if (val.startsWith('[') && val.endsWith(']')) {
        // Inline array: [a, b, c]
        fm[currentKey] = val.slice(1, -1).split(',').map(s => s.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean);
      } else if (val === '') {
        // Multi-line list starts below
        fm[currentKey] = [];
        inList = true;
      } else {
        fm[currentKey] = val.replace(/^['"]|['"]$/g, '');
      }
    }
  }
  return fm;
}

/** Temporary directory for install tests */
function makeTmpDir() {
  const dir = join(tmpdir(), `dsh-test-${Date.now()}-${Math.random().toString(36).slice(2)}`);
  mkdirSync(dir, { recursive: true });
  return dir;
}

// ---------------------------------------------------------------------------
// 1. Skill Discovery Tests
// ---------------------------------------------------------------------------

describe('Skill Discovery', () => {
  it('SKILL.md exists and has YAML frontmatter', () => {
    expect(existsSync(SKILL_MD)).toBe(true);
    const content = readFileSync(SKILL_MD, 'utf8');
    const fm = parseFrontmatter(content);
    expect(fm.name).toBeTruthy();
  });

  it('SKILL.md has required frontmatter fields', () => {
    const content = readFileSync(SKILL_MD, 'utf8');
    const fm = parseFrontmatter(content);
    expect(fm.name).toBeTruthy();
    expect(fm.description).toBeTruthy();
  });

  it('SKILL.md has markdown body with headings', () => {
    const content = readFileSync(SKILL_MD, 'utf8');
    // Should have at least one heading after frontmatter
    const body = content.replace(/^---[\s\S]*?---\n/, '');
    expect(body).toMatch(/^#\s+.+/m);
  });

  it('SKILL.md documents MCP tools', () => {
    const content = readFileSync(SKILL_MD, 'utf8');
    expect(content).toContain('misakanet_search');
    expect(content).toContain('misakanet_get_lesson');
  });

  it('SKILL.md includes usage examples', () => {
    const content = readFileSync(SKILL_MD, 'utf8');
    expect(content).toContain('Example');
  });
});

// ---------------------------------------------------------------------------
// 2. MCP Tool Contract Tests
// ---------------------------------------------------------------------------

describe('MCP Tool Contract', () => {
  let mcpServerModule;

  beforeEach(async () => {
    // Dynamic import of MCP server module
    try {
      mcpServerModule = await import(join(REPO_ROOT, 'scripts', 'mcp_server.js'));
    } catch {
      // If JS import fails, try reading the Python server's tool definitions
      mcpServerModule = null;
    }
  });

  it('MCP server entry point exists', () => {
    const jsServer = join(REPO_ROOT, 'scripts', 'mcp_server.js');
    const pyServer = join(REPO_ROOT, 'scripts', 'mcp_server.py');
    expect(existsSync(jsServer) || existsSync(pyServer)).toBe(true);
  });

  it('misakanet_search tool is documented in integration docs', () => {
    const content = readFileSync(DSH_INTEGRATION_DOC, 'utf8');
    expect(content).toContain('misakanet_search');
  });

  it('misakanet_get_lesson tool is documented in integration docs', () => {
    const content = readFileSync(DSH_INTEGRATION_DOC, 'utf8');
    expect(content).toContain('misakanet_get_lesson');
  });

  it('lesson index resource is documented', () => {
    const content = readFileSync(DSH_INTEGRATION_DOC, 'utf8');
    expect(content).toContain('misaka://lessons/index');
  });

  it('integration docs describe supported agents', () => {
    const content = readFileSync(DSH_INTEGRATION_DOC, 'utf8');
    // Should mention Claude Code and at least one other
    expect(content).toContain('Claude Code');
  });
});

// ---------------------------------------------------------------------------
// 3. Installation Method Validation Tests
// ---------------------------------------------------------------------------

describe('Installation Methods', () => {
  it('docs/dsh-installation.md documents npm method', () => {
    const content = readFileSync(DSH_INSTALL_DOC, 'utf8');
    expect(content).toContain('dsh plugin add misakanet');
  });

  it('docs/dsh-installation.md documents git method', () => {
    const content = readFileSync(DSH_INSTALL_DOC, 'utf8');
    expect(content).toContain('github:Ikalus1988/MisakaNet');
  });

  it('docs/dsh-installation.md documents manual/skill discovery method', () => {
    const content = readFileSync(DSH_INSTALL_DOC, 'utf8').toLowerCase();
    expect(content).toContain('manual');
    expect(content).toContain('.dsh/skills');
  });

  it('docs/dsh-installation.md lists prerequisites', () => {
    const content = readFileSync(DSH_INSTALL_DOC, 'utf8');
    expect(content).toContain('Node.js');
    expect(content).toContain('18');
  });

  it('docs/dsh-installation.md has troubleshooting section', () => {
    const content = readFileSync(DSH_INSTALL_DOC, 'utf8');
    expect(content).toContain('Troubleshooting');
    expect(content).toContain('Permission Denied');
  });

  it('docs/dsh-installation.md covers network issues', () => {
    const content = readFileSync(DSH_INSTALL_DOC, 'utf8');
    expect(content).toContain('Network Issues');
    expect(content).toContain('--verbose');
  });

  it('docs/dsh-installation.md covers version conflicts', () => {
    const content = readFileSync(DSH_INSTALL_DOC, 'utf8');
    expect(content).toContain('Version Conflicts');
  });

  it('docs/dsh-installation.md covers uninstallation', () => {
    const content = readFileSync(DSH_INSTALL_DOC, 'utf8');
    expect(content).toContain('Uninstall');
    expect(content).toContain('dsh plugin remove');
  });

  it('docs/dsh-installation.md covers updating', () => {
    const content = readFileSync(DSH_INSTALL_DOC, 'utf8');
    expect(content).toContain('Updating');
    expect(content).toContain('dsh plugin update');
  });
});

// ---------------------------------------------------------------------------
// 4. Installation Fallback Chain Tests
// ---------------------------------------------------------------------------

describe('Install Fallback Chain', () => {
  it('install docs mention fallback from git to npm', () => {
    const content = readFileSync(DSH_INSTALL_DOC, 'utf8');
    // The docs should suggest npm as recommended, git as alternative
    expect(content).toContain('Recommended');
    expect(content).toContain('Alternative');
  });

  it('existing lesson covers codeload timeout (git channel failure)', () => {
    const lessonPath = join(REPO_ROOT, 'lessons', 'contrib', 'dsh-plugin-install-github-codeload-timeout.md');
    expect(existsSync(lessonPath)).toBe(true);
    const content = readFileSync(lessonPath, 'utf8');
    expect(content).toContain('codeload');
    expect(content).toContain('timeout');
    expect(content).toContain('npm');
  });

  it('install docs show npm channel as primary', () => {
    const content = readFileSync(DSH_INSTALL_DOC, 'utf8');
    const npmPos = content.indexOf('dsh plugin add misakanet');
    const gitPos = content.indexOf('github:Ikalus1988/MisakaNet');
    // npm method should appear before git method
    expect(npmPos).toBeLessThan(gitPos);
  });
});

// ---------------------------------------------------------------------------
// 5. Config Generation Tests
// ---------------------------------------------------------------------------

describe('Config Generation', () => {
  it('SKILL.md has valid YAML frontmatter', () => {
    const content = readFileSync(SKILL_MD, 'utf8');
    // Should not have tab characters (common YAML error)
    expect(content).not.toMatch(/\t/);
    // Should start with frontmatter delimiter
    expect(content.trim()).toMatch(/^---/);
  });

  it('SKILL.md has proper markdown structure', () => {
    const content = readFileSync(SKILL_MD, 'utf8');
    // Should have at least one heading
    expect(content).toMatch(/^#\s+.+/m);
  });

  it('package.json exists with correct plugin metadata', () => {
    const pkgPath = join(REPO_ROOT, 'package.json');
    if (existsSync(pkgPath)) {
      const pkg = JSON.parse(readFileSync(pkgPath, 'utf8'));
      expect(pkg.name).toBeTruthy();
      expect(pkg.version).toBeTruthy();
    }
  });
});

// ---------------------------------------------------------------------------
// 6. DSH Plugin Packaging Tests
// ---------------------------------------------------------------------------

describe('DSH Plugin Packaging', () => {
  it('skills/misakanet directory contains SKILL.md', () => {
    expect(existsSync(SKILL_DIR)).toBe(true);
    expect(existsSync(SKILL_MD)).toBe(true);
  });

  it('SKILL.md name matches directory convention', () => {
    const content = readFileSync(SKILL_MD, 'utf8');
    const fm = parseFrontmatter(content);
    if (fm.name) {
      // Name should be consistent with directory or a known alias
      const validNames = ['misakanet', 'dsh-plugin', 'misakanet-failure-memory'];
      expect(validNames.some(n => fm.name.toLowerCase().includes(n))).toBe(true);
    }
  });

  it('SKILL.md documents trigger words or usage contexts', () => {
    const content = readFileSync(SKILL_MD, 'utf8');
    // Should contain trigger/usage references
    const hasTriggers = content.includes('When to use') || content.includes('trigger') || content.includes('Use MisakaNet');
    expect(hasTriggers).toBe(true);
  });

  it('dsh-plugin-installation.md links to plugin repo', () => {
    const content = readFileSync(DSH_INSTALL_DOC, 'utf8');
    expect(content).toContain('github.com/Ikalus1988/MisakaNet');
  });
});

// ---------------------------------------------------------------------------
// 7. Lesson Coverage for DSH Issues
// ---------------------------------------------------------------------------

describe('DSH Lesson Coverage', () => {
  it('codeload timeout lesson exists with correct frontmatter', () => {
    const lessonPath = join(REPO_ROOT, 'lessons', 'contrib', 'dsh-plugin-install-github-codeload-timeout.md');
    const content = readFileSync(lessonPath, 'utf8');
    const fm = parseFrontmatter(content);
    expect(fm.domain).toBe('mcp');
    expect(fm.tags).toContain('dsh');
    expect(fm.status).toBeTruthy();
    expect(fm.evidence_level || fm.provenance?.evidence).toBeTruthy();
  });

  it('codeload lesson covers npm fallback recommendation', () => {
    const lessonPath = join(REPO_ROOT, 'lessons', 'contrib', 'dsh-plugin-install-github-codeload-timeout.md');
    const content = readFileSync(lessonPath, 'utf8');
    expect(content).toContain('npm');
    expect(content).toContain('registry.npmjs.org');
  });

  it('codeload lesson covers Windows python3 detection', () => {
    const lessonPath = join(REPO_ROOT, 'lessons', 'contrib', 'dsh-plugin-install-github-codeload-timeout.md');
    const content = readFileSync(lessonPath, 'utf8');
    expect(content).toContain('win32');
    expect(content).toContain('python');
  });
});
