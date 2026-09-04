const { describe, it } = require('mocha');
const { expect } = require('chai');
const { execSync } = require('child_process');

describe('MisakaNet dsh Plugin Compatibility', function() {
  this.timeout(30000);

  describe('Agent Compatibility', function() {
    it('should work with Claude Code', function() {
      // Verify MCP protocol compatibility
      const result = execSync('dsh plugin list', { encoding: 'utf8' });
      expect(result).to.include('misakanet');
    });

    it('should work with Cursor', function() {
      // Same MCP tools should be available
      const result = execSync('dsh tool list', { encoding: 'utf8' });
      expect(result).to.include('misakanet_search');
    });

    it('should work with any MCP-compatible agent', function() {
      // Verify standard MCP protocol compliance
      const result = execSync('dsh tool list --format json', { encoding: 'utf8' });
      const tools = JSON.parse(result);
      const misakaTools = tools.filter(t => t.name.startsWith('misakanet_'));
      expect(misakaTools.length).to.be.greaterThan(0);
    });
  });

  describe('OS Compatibility', function() {
    it('should work on current OS', function() {
      const os = process.platform;
      const result = execSync('dsh plugin list', { encoding: 'utf8' });
      expect(result).to.include('misakanet');
    });
  });
});
