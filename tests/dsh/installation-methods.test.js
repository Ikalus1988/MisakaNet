const { describe, it, before, after } = require('mocha');
const { expect } = require('chai');
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

describe('MisakaNet dsh Plugin Installation Methods', function() {
  this.timeout(120000);

  const skillsDir = path.join(os.homedir(), '.dsh', 'skills');
  const pluginDir = path.join(skillsDir, 'misakanet');

  function cleanup() {
    try { execSync('dsh plugin remove misakanet', { stdio: 'ignore' }); } catch (e) {}
    try { fs.rmSync(pluginDir, { recursive: true, force: true }); } catch (e) {}
  }

  describe('Method 1: npm plugin market', function() {
    before(cleanup);

    it('should install successfully via npm', function() {
      const result = execSync('dsh plugin add misakanet', { encoding: 'utf8', timeout: 60000 });
      expect(result).to.not.be.empty;
    });

    it('should appear in plugin list', function() {
      const result = execSync('dsh plugin list', { encoding: 'utf8' });
      expect(result).to.include('misakanet');
    });

    it('should create plugin directory', function() {
      expect(fs.existsSync(pluginDir)).to.be.true;
    });

    it('should have MCP tools accessible', function() {
      const result = execSync('dsh tool list', { encoding: 'utf8' });
      expect(result).to.include('misakanet');
    });

    after(cleanup);
  });

  describe('Method 2: git method', function() {
    before(cleanup);

    it('should install successfully via git', function() {
      const result = execSync(
        'dsh plugin add github:Ikalus1988/MisakaNet',
        { encoding: 'utf8', timeout: 60000 }
      );
      expect(result).to.not.be.empty;
    });

    it('should appear in plugin list', function() {
      const result = execSync('dsh plugin list', { encoding: 'utf8' });
      expect(result).to.include('misakanet');
    });

    it('should have MCP tools accessible', function() {
      const result = execSync('dsh tool list', { encoding: 'utf8' });
      expect(result).to.include('misakanet');
    });

    after(cleanup);
  });

  describe('Method 3: manual skill discovery', function() {
    before(cleanup);

    it('should install successfully via manual copy', function() {
      if (!fs.existsSync(skillsDir)) {
        fs.mkdirSync(skillsDir, { recursive: true });
      }
      const sourceDir = path.join(__dirname, '..', 'skills', 'misakanet');
      // fs.cpSync (Node >=16.7) — no shell string, so no command injection
      // from env-derived paths (CodeQL js/shell-command-injection-from-environment).
      fs.cpSync(sourceDir, pluginDir, { recursive: true });
    });

    it('should appear in plugin list', function() {
      const result = execSync('dsh plugin list', { encoding: 'utf8' });
      expect(result).to.include('misakanet');
    });

    after(cleanup);
  });

  describe('Conflict test', function() {
    before(cleanup);

    it('should not conflict when switching methods', function() {
      // Install via npm
      execSync('dsh plugin add misakanet', { stdio: 'ignore', timeout: 60000 });
      let list = execSync('dsh plugin list', { encoding: 'utf8' });
      expect(list).to.include('misakanet');

      // Remove and reinstall via git
      execSync('dsh plugin remove misakanet', { stdio: 'ignore' });
      execSync('dsh plugin add github:Ikalus1988/MisakaNet', { stdio: 'ignore', timeout: 60000 });
      list = execSync('dsh plugin list', { encoding: 'utf8' });
      expect(list).to.include('misakanet');
    });

    after(cleanup);
  });

  describe('Uninstall test', function() {
    before(function() {
      cleanup();
      execSync('dsh plugin add misakanet', { stdio: 'ignore', timeout: 60000 });
    });

    it('should uninstall cleanly', function() {
      execSync('dsh plugin remove misakanet');
      const result = execSync('dsh plugin list', { encoding: 'utf8' });
      expect(result).to.not.include('misakanet');
    });

    it('should remove plugin directory', function() {
      expect(fs.existsSync(pluginDir)).to.be.false;
    });
  });
});
