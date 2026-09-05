const { describe, it, before, after } = require('mocha');
const { expect } = require('chai');
const { execSync } = require('child_process');

describe('MisakaNet dsh Plugin Functionality', function() {
  this.timeout(60000);

  before(function() {
    // Ensure plugin is installed
    try {
      const list = execSync('dsh plugin list', { encoding: 'utf8' });
      if (!list.includes('misakanet')) {
        execSync('dsh plugin add misakanet', { stdio: 'ignore', timeout: 60000 });
      }
    } catch (e) {
      execSync('dsh plugin add misakanet', { stdio: 'ignore', timeout: 60000 });
    }
  });

  describe('MCP Tool Discovery', function() {
    it('should list misakanet tools', function() {
      const result = execSync('dsh tool list', { encoding: 'utf8' });
      expect(result).to.include('misakanet');
    });

    it('should expose misakanet_search tool', function() {
      const result = execSync('dsh tool list --json', { encoding: 'utf8' });
      const tools = JSON.parse(result);
      const searchTool = tools.find(t => t.name === 'misakanet_search');
      expect(searchTool).to.exist;
      expect(searchTool.description).to.include('search');
    });

    it('should expose misakanet_get_lesson tool', function() {
      const result = execSync('dsh tool list --json', { encoding: 'utf8' });
      const tools = JSON.parse(result);
      const getTool = tools.find(t => t.name === 'misakanet_get_lesson');
      expect(getTool).to.exist;
      expect(getTool.description).to.include('lesson');
    });
  });

  describe('Tool Execution', function() {
    it('should execute misakanet_search', function() {
      const result = execSync(
        'dsh tool run misakanet_search --input \'{"query":"curl timeout"}\'',
        { encoding: 'utf8', timeout: 30000 }
      );
      const response = JSON.parse(result);
      expect(response).to.have.property('results');
      expect(response.results).to.be.an('array');
    });

    it('should execute misakanet_get_lesson', function() {
      const result = execSync(
        'dsh tool run misakanet_get_lesson --input \'{"path":"lessons/contrib/cloudflare-worker-deploy-three-pitfalls.md"}\'',
        { encoding: 'utf8', timeout: 30000 }
      );
      const response = JSON.parse(result);
      expect(response).to.have.property('content');
      expect(response.content).to.include('Cloudflare');
    });

    it('should handle invalid search query gracefully', function() {
      const result = execSync(
        'dsh tool run misakanet_search --input \'{"query":""}\'',
        { encoding: 'utf8', timeout: 30000 }
      );
      const response = JSON.parse(result);
      expect(response).to.have.property('error');
    });

    it('should handle missing lesson path gracefully', function() {
      const result = execSync(
        'dsh tool run misakanet_get_lesson --input \'{"path":"nonexistent.md"}\'',
        { encoding: 'utf8', timeout: 30000 }
      );
      const response = JSON.parse(result);
      expect(response).to.have.property('error');
    });
  });

  describe('Resource Access', function() {
    it('should access misaka://lessons/index resource', function() {
      const result = execSync(
        'dsh resource read misaka://lessons/index',
        { encoding: 'utf8', timeout: 30000 }
      );
      const index = JSON.parse(result);
      expect(index).to.be.an('array');
      expect(index.length).to.be.greaterThan(0);
      expect(index[0]).to.have.property('path');
      expect(index[0]).to.have.property('title');
    });

    it('should return valid lesson metadata', function() {
      const result = execSync(
        'dsh resource read misaka://lessons/index',
        { encoding: 'utf8', timeout: 30000 }
      );
      const index = JSON.parse(result);
      const lesson = index[0];
      expect(lesson).to.have.property('domain');
      expect(lesson).to.have.property('tags');
      expect(lesson.tags).to.be.an('array');
    });
  });
});
