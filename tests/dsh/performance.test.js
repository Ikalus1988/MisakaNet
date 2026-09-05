const { describe, it, before } = require('mocha');
const { expect } = require('chai');
const { execSync } = require('child_process');

describe('MisakaNet dsh Plugin Performance', function() {
  this.timeout(120000);

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

  describe('Startup Time', function() {
    it('should load plugin within 2 seconds', function() {
      const start = Date.now();
      execSync('dsh tool list', { encoding: 'utf8' });
      const elapsed = Date.now() - start;
      expect(elapsed).to.be.lessThan(2000);
    });

    it('should discover tools within 1 second', function() {
      const start = Date.now();
      execSync('dsh tool list --json', { encoding: 'utf8' });
      const elapsed = Date.now() - start;
      expect(elapsed).to.be.lessThan(1000);
    });
  });

  describe('Search Performance', function() {
    it('should complete search within 5 seconds', function() {
      const start = Date.now();
      execSync(
        'dsh tool run misakanet_search --input \'{"query":"curl"}\'',
        { encoding: 'utf8', timeout: 30000 }
      );
      const elapsed = Date.now() - start;
      expect(elapsed).to.be.lessThan(5000);
    });

    it('should handle multiple search terms', function() {
      const start = Date.now();
      execSync(
        'dsh tool run misakanet_search --input \'{"query":"curl proxy timeout corporate"}\'',
        { encoding: 'utf8', timeout: 30000 }
      );
      const elapsed = Date.now() - start;
      expect(elapsed).to.be.lessThan(10000);
    });
  });

  describe('Lesson Retrieval Performance', function() {
    it('should retrieve lesson within 2 seconds', function() {
      const start = Date.now();
      execSync(
        'dsh tool run misakanet_get_lesson --input \'{"path":"lessons/contrib/cloudflare-worker-deploy-three-pitfalls.md"}\'',
        { encoding: 'utf8', timeout: 30000 }
      );
      const elapsed = Date.now() - start;
      expect(elapsed).to.be.lessThan(2000);
    });

    it('should load lesson index within 3 seconds', function() {
      const start = Date.now();
      execSync(
        'dsh resource read misaka://lessons/index',
        { encoding: 'utf8', timeout: 30000 }
      );
      const elapsed = Date.now() - start;
      expect(elapsed).to.be.lessThan(3000);
    });
  });

  describe('Concurrent Requests', function() {
    it('should handle 3 concurrent searches', function() {
      const start = Date.now();
      const promises = [];

      for (let i = 0; i < 3; i++) {
        promises.push(
          new Promise((resolve) => {
            const result = execSync(
              `dsh tool run misakanet_search --input '{"query":"test${i}"}'`,
              { encoding: 'utf8', timeout: 30000 }
            );
            resolve(JSON.parse(result));
          })
        );
      }

      return Promise.all(promises).then(results => {
        const elapsed = Date.now() - start;
        expect(results).to.have.length(3);
        expect(elapsed).to.be.lessThan(15000);
      });
    });
  });
});
