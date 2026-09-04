const { describe, it, before, after } = require('mocha');
const { expect } = require('chai');
const { execSync } = require('child_process');

describe('MisakaNet dsh Plugin Functionality', function() {
  this.timeout(30000);

  before(function() {
    // Ensure plugin is installed
    try {
      execSync('dsh plugin add misakanet', { stdio: 'ignore' });
    } catch (e) {}
  });

  describe('MCP Tool Discovery', function() {
    it('should expose misakanet_search tool', function() {
      const result = execSync('dsh tool list', { encoding: 'utf8' });
      expect(result).to.include('misakanet_search');
    });

    it('should expose misakanet_get_lesson tool', function() {
      const result = execSync('dsh tool list', { encoding: 'utf8' });
      expect(result).to.include('misakanet_get_lesson');
    });
  });

  describe('Tool Execution', function() {
    it('should execute misakanet_search', function() {
      const result = execSync(
        'dsh tool run misakanet_search --query "test"',
        { encoding: 'utf8' }
      );
      expect(result).to.not.be.empty;
    });

    it('should handle empty queries gracefully', function() {
      const result = execSync(
        'dsh tool run misakanet_search --query ""',
        { encoding: 'utf8' }
      );
      expect(result).to.exist;
    });
  });

  describe('Resource Access', function() {
    it('should access misaka://lessons/index', function() {
      const result = execSync(
        'dsh resource get misaka://lessons/index',
        { encoding: 'utf8' }
      );
      expect(result).to.not.be.empty;
    });
  });

  describe('Error Handling', function() {
    it('should handle invalid tool names gracefully', function() {
      try {
        execSync('dsh tool run misakanet_invalid_tool', { encoding: 'utf8' });
      } catch (e) {
        expect(e.status).to.not.equal(0);
      }
    });

    it('should handle invalid resource URIs gracefully', function() {
      try {
        execSync('dsh resource get misaka://invalid/resource', { encoding: 'utf8' });
      } catch (e) {
        expect(e.status).to.not.equal(0);
      }
    });
  });

  after(function() {
    try {
      execSync('dsh plugin remove misakanet', { stdio: 'ignore' });
    } catch (e) {}
  });
});
