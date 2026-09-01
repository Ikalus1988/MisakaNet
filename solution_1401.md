# Solution for #1401: [Bounty] Test dsh plugin installation methods

===FILE:.github/workflows/test-installation.yml===
name: Test dsh plugin installation methods

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '18'
      - name: Install dsh
        run: npm install -g dsh
      - name: Install dependencies
        run: npm install
      - name: Run tests
        run: npm test
===END_FILE===
===FILE:package.json===
{
  "name": "dsh-plugin-installation-test",
  "version": "1.0.0",
  "description": "Tests for MisakaNet dsh plugin installation methods",
  "main": "test/installation.test.js",
  "scripts": {
    "test": "jest"
  },
  "devDependencies": {
    "execa": "^5.1.1",
    "fs-extra": "^10.0.0",
    "jest": "^27.0.0",
    "uuid": "^8.3.2"
  },
  "jest": {
    "testEnvironment": "node",
    "testTimeout": 120000
  }
}
===END_FILE===
===FILE:test/installation.test.js===
const { execa } = require('execa');
const fs = require('fs-extra');
const path = require('path');
const os = require('os');
const { v4: uuidv4 } = require('uuid');

describe('MisakaNet dsh plugin installation methods', () => {
  let tempDir;
  let dshHome;
  let skillsDir;
  let misakaRepoDir;

  beforeAll(async () => {
    // Create isolated environment
    tempDir = path.join(os.tmpdir(), `dsh-test-${uuidv4()}`);
    dshHome = path.join(tempDir, '.dsh');
    skillsDir = path.join(dshHome, 'skills');
    await fs.ensureDir(skillsDir);

    // Set environment so dsh uses our temp dir
    process.env.DSH_HOME = dshHome;
    process.env.HOME = tempDir;

    // Clone MisakaNet repository to obtain the skill directory for method 3
    misakaRepoDir = path.join(tempDir, 'MisakaNet');
    try {
      await execa('git', ['clone', 'https://github.com/Ikalus1988/MisakaNet.git', misakaRepoDir], {
        stdio: 'inherit',
      });
    } catch (error) {
      throw new Error(`Failed to clone MisakaNet repo: ${error.message}`);
    }
  });

  afterAll(async () => {
    await fs.remove(tempDir);
  });

  // Helper to run a dsh command
  async function dsh(args) {
    return execa('dsh', args, { env: process.env });
  }

  // Check if plugin appears in plugin list
  async function isPluginInstalled(pluginName = 'misakanet') {
    try {
      const { stdout } = await dsh(['plugin', 'list']);
      return stdout.includes(pluginName);
    } catch {
      return false;
    }
  }

  // Uninstall plugin, ignoring errors if not installed
  async function uninstallPlugin() {
    try {
      await dsh(['plugin', 'remove', 'misakanet']);
    } catch {
      // ignore
    }
  }

  // Verify plugin is functional by checking plugin info
  async function verifyPluginFunctionality() {
    const { stdout } = await dsh(['plugin', 'info', 'misakanet']);
    expect(stdout).toContain('misakanet');
  }

  beforeEach(async () => {
    await uninstallPlugin();
    // Also remove any skill directory from method 3 to start clean
    const skillPath = path.join(skillsDir, 'misakanet');
    if (await fs.pathExists(skillPath)) {
      await fs.remove(skillPath);
    }
  });

  test('Method 1: npm plugin market (dsh plugin add misakanet)', async () => {
    const { exitCode } = await dsh(['plugin', 'add', 'misakanet']);
    expect(exitCode).toBe(0);
    expect(await isPluginInstalled()).toBe(true);
    await verifyPluginFunctionality();

    // Clean up for next tests
    await uninstallPlugin();
    expect(await isPluginInstalled()).toBe(false);
  });

  test('Method 2: git method (dsh plugin add github:Ikalus1988/MisakaNet)', async () => {
    const { exitCode } = await dsh(['plugin', 'add', 'github:Ikalus1988/MisakaNet']);
    expect(exitCode).toBe(0);
    expect(await isPluginInstalled()).toBe(true);
    await verifyPluginFunctionality();

    await uninstallPlugin();
    expect(await isPluginInstalled()).toBe(false);
  });

  test('Method 3: Skill discovery (copy skills/misakanet to ~/.dsh/skills/)', async () => {
    const sourceSkillDir = path.join(misakaRepoDir, 'skills', 'misakanet');
    const destSkillDir = path.join(skillsDir, 'misakanet');
    await fs.copy(sourceSkillDir, destSkillDir);

    expect(await isPluginInstalled()).toBe(true);
    await verifyPluginFunctionality();

    // Cleanup
    await fs.remove(destSkillDir);
    expect(await isPluginInstalled()).toBe(false);
  });

  test('Conflict test: multiple installation methods should not conflict', async () => {
    // Install via method 1
    await dsh(['plugin', 'add', 'misakanet']);
    expect(await isPluginInstalled()).toBe(true);

    // Install via method 2 (should not error; may upgrade or skip)
    const { exitCode: exitCode2 } = await dsh(['plugin', 'add', 'github:Ikalus1988/MisakaNet']);
    expect(exitCode2).toBe(0);
    expect(await isPluginInstalled()).toBe(true);

    // Install via method 3 (copy skill)
    const sourceSkillDir = path.join(misakaRepoDir, 'skills', 'misakanet');
    const destSkillDir = path.join(skillsDir, 'misakanet');
    await fs.copy(sourceSkillDir, destSkillDir);
    expect(await isPluginInstalled()).toBe(true);

    // Verify still functional
    await verifyPluginFunctionality();

    // Cleanup all installations
    await uninstallPlugin();
    await fs.remove(destSkillDir);
    expect(await isPluginInstalled()).toBe(false);
  });

  test('Uninstall test: plugin should be removable cleanly', async () => {
    await dsh(['plugin', 'add', 'misakanet']);
    expect(await isPluginInstalled()).toBe(true);

    await uninstallPlugin();
    expect(await isPluginInstalled()).toBe(false);

    // Verify no residual plugin directory
    const pluginDir = path.join(dshHome, 'plugins', 'misakanet');
    expect(await fs.pathExists(pluginDir)).toBe(false);
  });
});
===END_FILE===
===FILE:README.md===
# dsh plugin installation tests

This suite tests all three installation methods for the MisakaNet dsh plugin.

## Prerequisites

- Node.js (v18 or later)
- npm
- git
- dsh installed globally (`npm install -g dsh`)

## Running Tests

Install dependencies and run:

```bash
npm install
npm test
```

## Test Coverage

- Method 1: `dsh plugin add misakanet` (npm market)
- Method 2: `dsh plugin add github:Ikalus1988/MisakaNet` (git)
- Method 3: Copy `skills/misakanet` to `~/.dsh/skills/`
- Conflict handling when multiple methods are used
- Clean uninstall

## CI

The included GitHub Actions workflow runs these tests on every push and pull request to the main branch.
===END_FILE===

---
_Generated by DevilX BountyHub solver_
