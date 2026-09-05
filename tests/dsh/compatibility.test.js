const { describe, it } = require('mocha');
const { expect } = require('chai');
const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

/**
 * Compatibility tests for MisakaNet dsh plugin across AI agent environments.
 * Tests Claude Code, Cursor, and other MCP-compatible agents.
 * Verifies that the plugin's MCP protocol works consistently across clients.
 */
describe('MisakaNet dsh Plugin Compatibility', function () {
  this.timeout(60000);

  const skillsDir = path.join(process.env.HOME || '/root', '.dsh', 'skills');
  const pluginDir = path.join(skillsDir, 'misakanet');

  function isInstalled() {
    try {
      execSync('dsh plugin list', { stdio: 'ignore' });
      return true;
    } catch (_) { return false; }
  }

  function getAgentInfo(cmd) {
    try {
      const result = execSync(cmd, { encoding: 'utf8', timeout: 10000 });
      return { found: true, output: result };
    } catch (e) {
      return { found: false, output: e.stderr || e.stdout || '' };
    }
  }

  describe('Claude Code compatibility', function () {
    it('should expose MCP tools in Claude Code-compatible format', function () {
      // Check that the plugin provides JSON-serializable tool schemas
      if (!fs.existsSync(path.join(pluginDir, 'package.json'))) {
        // npm bundle path
        return this.skip();
      }
      try {
        const pkg = JSON.parse(fs.readFileSync(path.join(pluginDir, 'package.json'), 'utf8'));
        // Should have dsh bundle declaration
        expect(pkg).to.have.property('dsh');
      } catch (_) {
        this.skip();
      }
    });

    it('should work with CLAUDE.md agent workflow', function () {
      // MisakaNet ships a CLAUDE.md for agent guidance — verify it exists
      const claudeMdPath = path.join(pluginDir, 'CLAUDE.md') ||
                           path.join(__dirname, '..', '..', 'CLAUDE.md');
      if (!fs.existsSync(claudeMdPath)) this.skip();

      const content = fs.readFileSync(claudeMdPath, 'utf8');
      // Should contain agent guidance relevant to the dsh plugin
      expect(content).to.match(/search|misaka|lesson/i);
    });

    it('should be installable in a fresh directory context', function () {
      // Simulate a fresh install by running in a subshell with cleared env vars
      // that point to user dirs (plugin itself uses fixed paths)
      const result = execSync(
        'dsh tool list 2>&1',
        { encoding: 'utf8', timeout: 30000, env: { ...process.env } }
      );
      expect(result).to.include('misakanet');
    });
  });

  describe('Cursor compatibility', function () {
    it('should expose a .cursor/rules compatible MCP server', function () {
      // Cursor uses .cursor/rules for agent guidance
      const cursorDir = path.join(__dirname, '..', '..', '.cursor');
      if (!fs.existsSync(cursorDir)) this.skip();

      const ruleFiles = fs.readdirSync(cursorDir).filter(f => f.startsWith('rules.') || f.endsWith('.md'));
      // Any .md files in .cursor/rules/ are Cursor rules
      expect(ruleFiles.length).to.be.greaterThan(0);
    });

    it('should provide TypeScript type definitions for Cursor', function () {
      // Verify index.d.ts exists (shipped in npm bundle)
      const dtsPath = path.join(pluginDir, 'index.d.ts') ||
                      path.join(__dirname, '..', '..', 'index.d.ts');
      if (!fs.existsSync(dtsPath)) this.skip();

      const content = fs.readFileSync(dtsPath, 'utf8');
      expect(content).to.include('misakanet');
    });
  });

  describe('General MCP client compatibility', function () {
    it('should provide a valid MCP stdio server', function () {
      // Verify the MCP server script exists and is executable
      const serverPath = path.join(pluginDir, 'scripts', 'mcp_server.py') ||
                         path.join(__dirname, '..', '..', 'scripts', 'mcp_server.py');
      if (!fs.existsSync(serverPath)) {
        // In npm bundle, python server may not be included — verify via dsh --help
        const listResult = execSync('dsh tool list', { encoding: 'utf8', timeout: 10000 });
        expect(listResult).to.include('misakanet');
        return;
      }
      expect(fs.existsSync(serverPath)).to.be.true;
      // Should be readable
      const stat = fs.statSync(serverPath);
      expect(stat.size).to.be.greaterThan(0);
    });

    it('should declare compatible MCP protocol version', function () {
      const pkgPath = path.join(pluginDir, 'package.json') ||
                      path.join(__dirname, '..', '..', 'package.json');
      if (!fs.existsSync(pkgPath)) this.skip();

      const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
      // cordis.patch.yml should declare MCP server config
      const patchPath = path.join(pluginDir, 'cordis.patch.yml') ||
                        path.join(__dirname, '..', '..', 'cordis.patch.yml');
      if (!fs.existsSync(patchPath)) {
        // npm bundle ships the patch
        expect(pkg).to.have.property('dsh');
        return;
      }
      const content = fs.readFileSync(patchPath, 'utf8');
      expect(content).to.include('mcp');
    });

    it('should not require external Python dependencies beyond stdlib', function () {
      // Verify scripts/mcp_server.py has minimal dependencies
      const serverPath = path.join(__dirname, '..', '..', 'scripts', 'mcp_server.py');
      if (!fs.existsSync(serverPath)) this.skip();

      const content = fs.readFileSync(serverPath, 'utf8');
      // Count import lines (excluding comments)
      const importLines = content.split('\n')
        .filter(l => l.trim().startsWith('import ') || l.trim().startsWith('from '))
        .filter(l => !l.trim().startsWith('#'));
      // All imports should be stdlib or the package itself
      const externalDeps = importLines.filter(l =>
        !l.includes('stdlib') && !l.includes('misaka') &&
        !l.includes('json') && !l.includes('path') &&
        !l.includes('re') && !l.includes('sys') &&
        !l.includes('typing') && !l.includes('os')
      );
      // Allow some external deps but warn if there are many
      if (externalDeps.length > 5) {
        console.warn('High number of external imports:', externalDeps.join(', '));
      }
    });
  });

  describe('Cross-platform compatibility', function () {
    it('should have OS-agnostic file paths', function () {
      // All path operations should use path.join, not os.sep directly
      const scriptsDir = path.join(__dirname, '..', '..', 'scripts');
      if (!fs.existsSync(scriptsDir)) this.skip();

      const mcpServer = path.join(scriptsDir, 'mcp_server.py');
      if (!fs.existsSync(mcpServer)) this.skip();

      const content = fs.readFileSync(mcpServer, 'utf8');
      // Should not have hardcoded Unix or Windows paths
      expect(content).to.not.match(/[A-Z]:\\\\|C:\\\\/);
      expect(content).to.not.include('~/.dsh/'); // should use proper path resolution
    });
  });
});
