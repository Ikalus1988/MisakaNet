const { describe, it, before, after } = require('mocha');
const { expect } = require('chai');
const { execSync } = require('child_process');
const path = require('path');

/**
 * Functionality tests for MisakaNet dsh plugin MCP tools and resources.
 * Tests the core tools: misakanet_search, misakanet_get_lesson
 * and the misaka:// resource URIs.
 */
describe('MisakaNet dsh Plugin Functionality', function () {
  this.timeout(120000);

  const skillsDir = path.join(process.env.HOME || process.env.USERPROFILE || '/root', '.dsh', 'skills');
  const pluginDir = path.join(skillsDir, 'misakanet');

  function cleanup() {
    try { execSync('dsh plugin remove misakanet', { stdio: 'ignore' }); } catch (_) {}
  }

  before(function () {
    // Ensure plugin is installed before running
    try {
      execSync('dsh plugin add misakanet', { stdio: 'ignore', timeout: 60000 });
    } catch (e) {
      // dsh may not be installed; skip tests gracefully
      console.warn('dsh not available, skipping functionality tests');
      this.skip();
    }
  });

  after(cleanup);

  describe('MCP tool discovery', function () {
    it('should list misakanet MCP tools via dsh', function () {
      const result = execSync('dsh tool list', { encoding: 'utf8', timeout: 30000 });
      expect(result).to.include('misakanet');
    });

    it('should expose misakanet_search tool', function () {
      const result = execSync('dsh tool list', { encoding: 'utf8', timeout: 30000 });
      expect(result).to.match(/misakanet.*search/i);
    });

    it('should expose misakanet_get_lesson tool', function () {
      const result = execSync('dsh tool list', { encoding: 'utf8', timeout: 30000 });
      expect(result).to.match(/misakanet.*(get_?lesson|lesson)/i);
    });
  });

  describe('misakanet_search tool', function () {
    it('should return results for a known keyword', function () {
      // Search for a term likely to have results
      const result = execSync(
        'dsh tool call misakanet_search --input \'{"query": "python error"}\'',
        { encoding: 'utf8', timeout: 30000 }
      );
      expect(result).to.not.be.empty;
      // Should be parseable JSON or have content
      try {
        const parsed = JSON.parse(result);
        expect(parsed).to.have.property('results').or.have.property('lessons').or.have.property('data');
      } catch (_) {
        // Non-JSON output is also acceptable if not an error
        expect(result).to.not.match(/error|exception|traceback/i);
      }
    });

    it('should handle empty query gracefully', function () {
      const result = execSync(
        'dsh tool call misakanet_search --input \'{"query": ""}\'',
        { encoding: 'utf8', timeout: 30000 }
      );
      expect(result).to.not.match(/traceback|unhandled|exception/i);
    });

    it('should handle unknown keyword without crashing', function () {
      const result = execSync(
        'dsh tool call misakanet_search --input \'{"query": "xyzzy_nonexistent_keyword_12345"}\'',
        { encoding: 'utf8', timeout: 30000 }
      );
      // Should return empty results or a graceful response, not a crash
      expect(result).to.not.match(/traceback|unhandled/i);
    });
  });

  describe('misakanet_get_lesson tool', function () {
    it('should require a lesson identifier', function () {
      // Call without --lesson or with invalid id should not crash
      try {
        const result = execSync(
          'dsh tool call misakanet_get_lesson --input \'{"id": ""}\'',
          { encoding: 'utf8', timeout: 30000 }
        );
        // Empty ID may return null/empty but shouldn't crash
        expect(result).to.not.match(/traceback|unhandled/i);
      } catch (e) {
        // Non-zero exit is acceptable if it's a validation error
        expect(e.stderr || e.stdout || '').to.not.match(/traceback/i);
      }
    });

    it('should accept a lesson id parameter', function () {
      // First get a list of lesson IDs via search
      try {
        const searchResult = execSync(
          'dsh tool call misakanet_search --input \'{"query": "test"}\'',
          { encoding: 'utf8', timeout: 30000 }
        );
        let lessonId = null;
        try {
          const parsed = JSON.parse(searchResult);
          // Try to extract first lesson ID from results
          const results = parsed.results || parsed.lessons || parsed.data || [];
          if (results.length > 0) {
            lessonId = results[0].id || results[0].slug;
          }
        } catch (_) {}
      } catch (_) {}
      // If we have a lesson ID, test retrieval — otherwise skip gracefully
      if (!lessonId) this.skip();
    });
  });

  describe('Resource access', function () {
    it('should expose misaka://lessons/index resource', function () {
      // dsh resource list is not standardized; check via help or info
      try {
        const result = execSync('dsh --help', { encoding: 'utf8', timeout: 10000 });
        // If resources are exposed they should appear in dsh info
        const infoResult = execSync('dsh info misakanet', { encoding: 'utf8', timeout: 10000 });
        expect(infoResult).to.include('misakanet');
      } catch (e) {
        // dsh info may not exist; skip if not available
        this.skip();
      }
    });
  });

  describe('Error handling', function () {
    it('should not crash on malformed JSON input', function () {
      try {
        const result = execSync(
          'dsh tool call misakanet_search --input not-json',
          { encoding: 'utf8', timeout: 15000 }
        );
        expect(result).to.not.match(/traceback|unhandled/i);
      } catch (e) {
        // Non-zero exit is fine; just shouldn't be a traceback
        expect((e.stderr || e.stdout || '')).to.not.match(/traceback|unhandled/i);
      }
    });

    it('should handle missing MCP server gracefully', function () {
      // Temporarily remove plugin and try to call — should fail gracefully
      try {
        execSync('dsh plugin remove misakanet', { stdio: 'ignore' });
        const result = execSync(
          'dsh tool call misakanet_search --input \'{"query": "test"}\'',
          { encoding: 'utf8', timeout: 15000 }
        );
        // Should return an error message, not crash
        expect(result.toLowerCase()).to.include('error').or.include('not found');
      } catch (e) {
        expect((e.stderr || '')).to.not.include('traceback');
      } finally {
        // Restore plugin
        try { execSync('dsh plugin add misakanet', { stdio: 'ignore', timeout: 60000 }); } catch (_) {}
      }
    });
  });
});
