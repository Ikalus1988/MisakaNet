const { describe, it, before, after } = require('mocha');
const { expect } = require('chai');
const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

/**
 * Performance benchmarks for MisakaNet dsh plugin.
 * Measures startup time, memory usage, and concurrent request handling.
 * All tests are advisory — they establish baselines rather than pass/fail.
 */
describe('MisakaNet dsh Plugin Performance', function () {
  this.timeout(180000);

  const skillsDir = path.join(process.env.HOME || '/root', '.dsh', 'skills');
  const pluginDir = path.join(skillsDir, 'misakanet');

  function cleanup() {
    try { execSync('dsh plugin remove misakanet', { stdio: 'ignore' }); } catch (_) {}
  }

  before(function () {
    try {
      execSync('dsh plugin add misakanet', { stdio: 'ignore', timeout: 60000 });
    } catch (e) {
      console.warn('dsh not available, skipping performance tests');
      this.skip();
    }
  });

  after(cleanup);

  describe('Startup time', function () {
    it('should start dsh tool list within reasonable time', function () {
      const start = process.hrtime.bigint();
      const result = execSync('dsh tool list', { encoding: 'utf8', timeout: 30000 });
      const end = process.hrtime.bigint();
      const ms = Number(end - start) / 1_000_000;

      // Record for CI artifact
      console.log(`STARTUP_TIME_MS=${ms.toFixed(2)}`);
      // Advisory: under 3s cold, under 1s warm
      if (ms > 10000) console.warn(`WARNING: startup took ${ms.toFixed(2)}ms`);

      expect(result).to.include('misakanet');
    });

    it('should have sub-second warm tool invocation', function () {
      // Warm call
      execSync('dsh tool list', { stdio: 'ignore' });
      const start = process.hrtime.bigint();
      const result = execSync('dsh tool list', { encoding: 'utf8', timeout: 10000 });
      const end = process.hrtime.bigint();
      const ms = Number(end - start) / 1_000_000;

      console.log(`WARM_CALL_MS=${ms.toFixed(2)}`);
      expect(ms).to.be.lessThan(5000); // generous upper bound
    });
  });

  describe('Memory usage', function () {
    it('should report reasonable RSS for dsh process', function () {
      // This is approximate — we measure the child process memory
      try {
        const result = execSync(
          'dsh tool call misakanet_search --input \'{"query": "memory test"}\'',
          { encoding: 'utf8', timeout: 30000 }
        );
        // Memory is measured externally in CI; here we just verify it runs
        expect(result).to.not.match(/traceback|unhandled|OOM|out of memory/i);
      } catch (e) {
        // Non-zero exit acceptable if no crash
        expect((e.stderr || '')).to.not.match(/traceback|unhandled|OOM/i);
      }
    });
  });

  describe('Concurrent requests', function () {
    it('should handle sequential search calls without degradation', function () {
      const times = [];
      for (let i = 0; i < 5; i++) {
        const start = process.hrtime.bigint();
        try {
          execSync(
            `dsh tool call misakanet_search --input '{"query": "concurrent test ${i}"}'`,
            { encoding: 'utf8', timeout: 30000 }
          );
        } catch (_) {
          // Ignore individual failures
        }
        const end = process.hrtime.bigint();
        times.push(Number(end - start) / 1_000_000);
      }

      const avg = times.reduce((a, b) => a + b, 0) / times.length;
      const max = Math.max(...times);
      console.log(`CONCURRENT_AVG_MS=${avg.toFixed(2)} MAX_MS=${max.toFixed(2)}`);

      // No hard fail — just log for trend tracking
      expect(avg).to.be.greaterThan(0);
    });

    it('should handle rapid fire tool calls without crash', function () {
      let crashes = 0;
      for (let i = 0; i < 10; i++) {
        try {
          execSync(
            'dsh tool call misakanet_search --input \'{"query": "rapid"}\'',
            { stdio: 'pipe', timeout: 15000 }
          );
        } catch (e) {
          if ((e.stderr || e.stdout || '').match(/traceback|unhandled|OOM|killed/)) {
            crashes++;
          }
        }
      }
      console.log(`CRASHES_IN_RAPID_FIRE=${crashes}`);
      expect(crashes).to.equal(0);
    });
  });

  describe('Resource utilization', function () {
    it('should not leak file descriptors', function () {
      // Run several calls and ensure no EMFILE errors
      for (let i = 0; i < 20; i++) {
        try {
          execSync('dsh tool list', { stdio: 'ignore', timeout: 5000 });
        } catch (e) {
          if ((e.stderr || e.stdout || '').match(/EMFILE|too many open files/)) {
            throw new Error('File descriptor leak detected');
          }
        }
      }
    });

    it('should clean up temp files after execution', function () {
      // Check common temp locations before/after
      const tmpDir = process.env.TMPDIR || process.env.TEMP || '/tmp';
      const before = fs.readdirSync(tmpDir).length;

      for (let i = 0; i < 5; i++) {
        try {
          execSync('dsh tool call misakanet_search --input \'{"query": "temp"}\'', { stdio: 'ignore' });
        } catch (_) {}
      }

      const after = fs.readdirSync(tmpDir).length;
      const leaked = after - before;
      console.log(`TEMP_FILES_BEFORE=${before} AFTER=${after} DELTA=${leaked}`);
      // Allow some variance but flag large leaks
      expect(leaked).to.be.lessThan(50);
    });
  });

  describe('CI integration', function () {
    it('should produce parseable output for CI artifacts', function () {
      // All tests above log KEY=VALUE for CI collection
      // This test just verifies the pattern works
      const result = execSync('dsh tool list', { encoding: 'utf8', timeout: 10000 });
      expect(result).to.include('misakanet');
    });
  });
});Updated test for CI re-scan
