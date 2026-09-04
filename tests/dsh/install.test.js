const { describe, it, before, after } = require('mocha');
const { expect } = require('chai');
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

describe('MisakaNet dsh Plugin Installation', function() {
  this.timeout(60000);

  const skillsDir = path.join(os.homedir(), '.dsh', 'skills');
  const pluginDir = path.join(skillsDir, 'misakanet');

  describe('Method 1: npm plugin market', function() {
    before(function() {
      // Clean install
      try {
        execSync('dsh plugin remove misakanet', { stdio: 'ignore' });
      } catch (e) {}
    });

    it('should install successfully via npm', function() {
      const result = execSync('dsh plugin add misakanet', { encoding: 'utf8' });
      expect(result).to.not.be.empty;
    });

    it('should appear in plugin list', function() {
      const result = execSync('dsh plugin list', { encoding: 'utf8' });
      expect(result).to.include('misakanet');
    });

    it('should create plugin directory', function() {
      expect(fs.existsSync(pluginDir)).to.be.true;
    });

    after(function() {
      try {
        execSync('dsh plugin remove misakanet', { stdio: 'ignore' });
      } catch (e) {}
    });
  });

  describe('Method 2: git method', function() {
    before(function() {
      try {
        execSync('dsh plugin remove misakanet', { stdio: 'ignore' });
      } catch (e) {}
    });

    it('should install successfully via git', function() {
      const result = execSync(
        'dsh plugin add github:Ikalus1988/MisakaNet',
        { encoding: 'utf8' }
      );
      expect(result).to.not.be.empty;
    });

    it('should appear in plugin list', function() {
      const result = execSync('dsh plugin list', { encoding: 'utf8' });
      expect(result).to.include('misakanet');
    });

    after(function() {
      try {
        execSync('dsh plugin remove misakanet', { stdio: 'ignore' });
      } catch (e) {}
    });
  });

  describe('Method 3: manual skill discovery', function() {
    before(function() {
      try {
        execSync('dsh plugin remove misakanet', { stdio: 'ignore' });
      } catch (e) {}
    });

    it('should install successfully via manual copy', function() {
      // Ensure skills directory exists
      if (!fs.existsSync(skillsDir)) {
        fs.mkdirSync(skillsDir, { recursive: true });
      }

      // Copy plugin
      const sourceDir = path.join(__dirname, '..', '..', 'skills', 'misakanet');
      execSync(`cp -r ${sourceDir} ${pluginDir}`);
    });

    it('should appear in plugin list', function() {
      const result = execSync('dsh plugin list', { encoding: 'utf8' });
      expect(result).to.include('misakanet');
    });

    after(function() {
      try {
        execSync('dsh plugin remove misakanet', { stdio: 'ignore' });
      } catch (e) {}
    });
  });

  describe('Uninstallation', function() {
    before(function() {
      execSync('dsh plugin add misakanet', { stdio: 'ignore' });
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
