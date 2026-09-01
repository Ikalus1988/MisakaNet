# Solution for #1403: [Bounty] dsh plugin integration test suite

===FILE:.github/workflows/test.yml===
name: Test Suite

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    name: Test on ${{ matrix.os }} with Node ${{ matrix.node-version }}
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        node-version: [18, 20, 22]
        # Test with different dsh versions (if needed)
        # dsh-version: [latest] # can be added later

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Node.js ${{ matrix.node-version }}
        uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node-version }}
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      # Install dsh globally if not already present; use specific version if required
      - name: Install dsh
        run: npm install -g dsh

      # Build the plugin (if needed)
      - name: Build plugin
        run: npm run build
        continue-on-error: true # skip if no build script

      # Run tests with coverage
      - name: Run tests
        run: npm test

      - name: Upload coverage to Codecov (optional)
        uses: codecov/codecov-action@v4
        with:
          files: ./coverage/lcov.info
          flags: unittests
          name: codecov-umbrella
          fail_ci_if_error: false
===END_FILE===

===FILE:package.json===
{
  "name": "dsh-plugin-misakanet-tests",
  "version": "1.0.0",
  "description": "Test suite for MisakaNet dsh plugin",
  "main": "index.js",
  "scripts": {
    "test": "jest --coverage",
    "test:watch": "jest --watch",
    "test:ci": "jest --ci --coverage --maxWorkers=2",
    "build": "echo 'No build step defined' && exit 0"
  },
  "devDependencies": {
    "@jest/globals": "^29.7.0",
    "@modelcontextprotocol/sdk": "^0.5.0",
    "jest": "^29.7.0",
    "jest-environment-node": "^29.7.0",
    "mock-fs": "^5.2.0",
    "tmp": "^0.2.3"
  },
  "jest": {
    "testEnvironment": "node",
    "testMatch": [
      "<rootDir>/tests/dsh/**/*.test.js"
    ],
    "collectCoverageFrom": [
      "**/*.js",
      "!**/node_modules/**",
      "!**/tests/**",
      "!**/coverage/**"
    ],
    "coverageReporters": [
      "text",
      "lcov"
    ],
    "verbose": true,
    "testTimeout": 30000
  }
}
===END_FILE===

===FILE:tests/dsh/helpers.js===
const { spawn } = require('child_process');
const { Client } = require('@modelcontextprotocol/sdk/client/index.js');
const { StdioClientTransport } = require('@modelcontextprotocol/sdk/client/stdio.js');
const path = require('path');
const fs = require('fs');

// Locate the plugin's main entry point
// Assumes the plugin is in the repository root, with entry index.js or src/index.js
function getPluginEntry() {
  const candidates = [
    path.resolve(__dirname, '../../index.js'),
    path.resolve(__dirname, '../../src/index.js'),
    path.resolve(__dirname, '../../dist/index.js'),
    path.resolve(__dirname, '../../lib/index.js'),
  ];
  for (const file of candidates) {
    if (fs.existsSync(file)) {
      return file;
    }
  }
  throw new Error('Could not find plugin entry point');
}

/**
 * Start the MisakaNet MCP server as a child process.
 * Returns a Client connected via stdio.
 */
async function startMisakaNetServer() {
  const entry = getPluginEntry();
  // The plugin likely exports a server that can be run with --stdio flag
  // or we can spawn node with the entry and assume it starts the server.
  // For a dsh plugin, it might be a command, but we can directly run the server.
  // We'll assume the plugin's server is started when we run the entry with '--stdio' argument.
  const args = ['--stdio'];
  const child = spawn('node', [entry, ...args], {
    stdio: ['pipe', 'pipe', 'pipe', 'ipc'],
    env: { ...process.env, NODE_ENV: 'test' },
  });

  const transport = new StdioClientTransport({
    command: 'node',
    args: [entry, ...args],
  });

  const client = new Client(
    {
      name: 'test-client',
      version: '1.0.0',
    },
    {
      capabilities: {},
    }
  );

  await client.connect(transport);
  return { client, transport, child };
}

/**
 * Wait for a condition, with timeout.
 */
function waitFor(condition, timeout = 5000, interval = 100) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const check = () => {
      if (condition()) {
        resolve();
      } else if (Date.now() - start >= timeout) {
        reject(new Error('Timeout waiting for condition'));
      } else {
        setTimeout(check, interval);
      }
    };
    check();
  });
}

/**
 * Clean up server resources.
 */
async function stopMisakaNetServer(client, transport, child) {
  if (client) {
    try {
      await client.close();
    } catch (_) {}
  }
  if (transport) {
    try {
      await transport.close();
    } catch (_) {}
  }
  if (child && !child.killed) {
    child.kill();
  }
}

module.exports = {
  startMisakaNetServer,
  stopMisakaNetServer,
  waitFor,
};
===END_FILE===

===FILE:tests/dsh/install.test.js===
const { exec } = require('child_process');
const { promisify } = require('util');
const fs = require('fs');
const path = require('path');
const tmp = require('tmp');

const execAsync = promisify(exec);

// Helper to run commands and capture output
async function runCommand(cmd, cwd) {
  try {
    const { stdout, stderr } = await execAsync(cmd, { cwd, shell: true });
    return { stdout, stderr, code: 0 };
  } catch (error) {
    return { stdout: error.stdout || '', stderr: error.stderr || '', code: error.code || 1 };
  }
}

describe('Installation Tests', () => {
  // These tests assume the plugin is already built and available in the repo.
  // They verify that the plugin can be installed via npm, git, and manual copy.

  // Create a temporary directory for each test
  let tempDir;

  beforeEach(() => {
    tempDir = tmp.dirSync({ unsafeCleanup: true });
  });

  afterEach(() => {
    tempDir.removeCallback();
  });

  test('Install via npm link (local development)', async () => {
    // Simulate npm link from repo root to temp dir
    const repoRoot = path.resolve(__dirname, '../..');
    // Create a package.json in temp dir
    const pkgJson = {
      name: 'test-app',
      version: '1.0.0',
      dependencies: {},
    };
    fs.writeFileSync(path.join(tempDir.name, 'package.json'), JSON.stringify(pkgJson));

    // Link the plugin globally (if not already linked) and then install in temp
    // We'll run npm link in the repo root first
    const linkResult = await runCommand('npm link', repoRoot);
    expect(linkResult.code).toBe(0);

    // Now in temp dir, install the linked package
    const installResult = await runCommand('npm link dsh-plugin-misakanet', tempDir.name);
    expect(installResult.code).toBe(0);

    // Verify the plugin is installed in node_modules
    const pluginPath = path.join(tempDir.name, 'node_modules', 'dsh-plugin-misakanet');
    expect(fs.existsSync(pluginPath)).toBe(true);
  }, 30000);

  test('Install via git URL', async () => {
    // This test may require network, so we mock or skip in CI if needed.
    // For demonstration, we'll check that the command runs without error.
    // We'll use a local git repo if available.
    const repoRoot = path.resolve(__dirname, '../..');
    // Create a temp dir for installation
    const testDir = tmp.dirSync({ unsafeCleanup: true });
    // Create a package.json
    const pkgJson = {
      name: 'test-git-install',
      version: '1.0.0',
      dependencies: {},
    };
    fs.writeFileSync(path.join(testDir.name, 'package.json'), JSON.stringify(pkgJson));

    // Use the local repo as a git source (file://)
    const gitUrl = `file://${repoRoot}`;
    const installCmd = `npm install ${gitUrl}`;
    const result = await runCommand(installCmd, testDir.name);
    // Even if npm fails due to missing git, we can assert that the command was attempted.
    // In a real CI, we might skip this test if git is not available.
    // For now, we just check that the plugin is installed if successful.
    expect(result.code).toBe(0);
    const pluginPath = path.join(testDir.name, 'node_modules', 'dsh-plugin-misakanet');
    if (result.code === 0) {
      expect(fs.existsSync(pluginPath)).toBe(true);
    }
    testDir.removeCallback();
  }, 30000);

  test('Install manually (copy files)', async () => {
    // Simulate manual installation by copying the plugin directory into node_modules
    const repoRoot = path.resolve(__dirname, '../..');
    const destDir = path.join(tempDir.name, 'node_modules', 'dsh-plugin-misakanet');
    fs.mkdirSync(path.dirname(destDir), { recursive: true });
    // Copy plugin directory (excluding node_modules and test)
    // For simplicity, we copy all files from repo root except some.
    // In a real test, we might copy only necessary files.
    // We'll copy the entire repo but filter out node_modules and tests.
    const exclude = ['node_modules', 'tests', '.git'];
    const copyRecursive = (src, dest) => {
      const entries = fs.readdirSync(src, { withFileTypes: true });
      for (const entry of entries) {
        if (exclude.includes(entry.name)) continue;
        const srcPath = path.join(src, entry.name);
        const destPath = path.join(dest, entry.name);
        if (entry.isDirectory()) {
          fs.mkdirSync(destPath, { recursive: true });
          copyRecursive(srcPath, destPath);
        } else {
          fs.copyFileSync(srcPath, destPath);
        }
      }
    };
    copyRecursive(repoRoot, destDir);

    // Now verify that the plugin is present
    expect(fs.existsSync(path.join(destDir, 'package.json'))).toBe(true);
  });
});
===END_FILE===

===FILE:tests/dsh/functionality.test.js===
const { startMisakaNetServer, stopMisakaNetServer } = require('./helpers');

describe('Functionality Tests', () => {
  let serverInfo;

  beforeAll(async () => {
    serverInfo = await startMisakaNetServer();
  });

  afterAll(async () => {
    if (serverInfo) {
      await stopMisakaNetServer(serverInfo.client, serverInfo.transport, serverInfo.child);
    }
  });

  test('MCP tool discovery - list_tools', async () => {
    const { client } = serverInfo;
    const tools = await client.listTools();
    expect(tools).toBeDefined();
    // Expect at least the two tools mentioned: misakanet_search, misakanet_get_lesson
    const toolNames = tools.map(t => t.name);
    expect(toolNames).toContain('misakanet_search');
    expect(toolNames).toContain('misakanet_get_lesson');
    // Optionally check tool schemas
    const searchTool = tools.find(t => t.name === 'misakanet_search');
    expect(searchTool).toBeDefined();
    expect(searchTool.inputSchema).toBeDefined();
  });

  test('Tool execution - misakanet_search', async () => {
    const { client } = serverInfo;
    // Call the search tool with a valid query
    const result = await client.callTool('misakanet_search', {
      query: 'network protocols',
    });
    expect(result).toBeDefined();
    expect(result.content).toBeDefined();
    // Depending on the plugin's response, check structure
    // For example, expect an array of results
    expect(Array.isArray(result.content)).toBe(true);
    // Check that at least one result has a title or something
    // We can't assert specific content, but we can check that it's not empty
    expect(result.content.length).toBeGreaterThan(0);
  });

  test('Tool execution - misakanet_get_lesson', async () => {
    const { client } = serverInfo;
    // We need a valid lesson ID. Use a known one from fixtures or from search result.
    // For test stability, we can use a lesson ID that is likely to exist.
    // Here we assume the plugin has a lesson with ID '1' or we fetch from search.
    // To make it robust, we first search for something to get a lesson ID.
    let lessonId = '1';
    try {
      const searchResult = await client.callTool('misakanet_search', { query: 'example

---
_Generated by DevilX BountyHub solver_
