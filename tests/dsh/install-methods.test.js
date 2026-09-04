const { describe, it, before, after } = require('mocha');
const { expect } = require('chai');
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

describe('MisakaNet dsh Plugin - Installation Methods', function() {
  this.timeout(120000);

  const skillsDir = path.join(os.homedir(), '.dsh', 'skills');
  const pluginDir = path.join(skillsDir, 'misakanet');

  function cleanInstall() {
    try { execSync('dsh plugin remove misakanet', { stdio: 'ignore' }); } catch (e) {}
    try { fs.rmSync(pluginDir, { recursive: true, force: true }); } catch (e) {}
  }

  function isInstalled() {
    try {
      const list = execSync('dsh plugin list', { encoding: 'utf8' });
      return list.includes('misakanet');
    } catch (e) {
      return false;
    }
  }

  describe('Method 1: npm plugin market', function() {
    before(cleanInstall);

    it('should install without errors', function() {
      const result = execSync('dsh plugin add misakanet', { encoding: 'utf8', timeout: 60000 });
      expect(result).to.not.be.empty;
    });

    it('should appear in dsh plugin list', function() {
      expect(isInstalled()).to.be.true;
    });

    it('should create plugin directory', function() {
      expect(fs.existsSync(pluginDir)).to.be.true;
    });

    it('should have MCP tools accessible', function() {
      const tools = execSync('dsh tool list', { encoding: 'utf8' });
      expect(tools).to.include('misakanet_search');
      expect(tools).to.include('misakanet_get_lesson');
    });

    after(cleanInstall);
  });

  describe('Method 2: git method', function() {
    before(cleanInstall);

    it('should install without errors', function() {
      const result = execSync(
        'dsh plugin add github:Ikalus1988/MisakaNet',
        { encoding: 'utf8', timeout: 60000 }
      );
      expect(result).to.not.be.empty;
    });

    it('should appear in dsh plugin list', function() {
      expect(isInstalled()).to.be.true;
    });

    it('should have MCP tools accessible', function() {
      const tools = execSync('dsh tool list', { encoding: 'utf8' });
      expect(tools).to.include('misakanet_search');
    });

    after(cleanInstall);
  });

  describe('Method 3: manual skill discovery', function() {
    before(cleanInstall);

    it('should install via manual copy', function() {
      if (!fs.existsSync(skillsDir)) {
        fs.mkdirSync(skillsDir, { recursive: true });
      }
      const source = path.join(__dirname, '..', '..', 'skills', 'misakanet');
      execSync(`cp -r ${source} ${pluginDir}`);
      expect(fs.existsSync(pluginDir)).to.be.true;
    });

    it('should appear in dsh plugin list', function() {
      expect(isInstalled()).to.be.true;
    });

    after(cleanInstall);
  });

  describe('Conflict test: multiple methods', function() {
    before(cleanInstall);

    it('should not conflict when switching methods', function() {
      // Install via npm
      execSync('dsh plugin add misakanet', { stdio: 'ignore' });
      expect(isInstalled()).to.be.true;

      // Remove and reinstall via git
      execSync('dsh plugin remove misakanet', { stdio: 'ignore' });
      execSync('dsh plugin add github:Ikalus1988/MisakaNet', { stdio: 'ignore' });
      expect(isInstalled()).to.be.true;
    });

    after(cleanInstall);
  });

  describe('Uninstall test', function() {
    before(function() {
      execSync('dsh plugin add misakanet', { stdio: 'ignore' });
    });

    it('should remove cleanly', function() {
      execSync('dsh plugin remove misakanet');
      expect(isInstalled()).to.be.false;
    });

    it('should remove plugin directory', function() {
      expect(fs.existsSync(pluginDir)).to.be.false;
    });
  });
});
