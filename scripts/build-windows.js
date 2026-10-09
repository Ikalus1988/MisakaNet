#!/usr/bin/env node
/**
 * Windows build script for MisakaNet desktop app
 * 
 * Runs validation before building to ensure appId consistency.
 */

const { execSync } = require('child_process');
const path = require('path');

function runScript(scriptPath) {
  const absPath = path.resolve(__dirname, scriptPath);
  console.log(`\n[build-windows] Running validation: ${scriptPath}\n`);
  try {
    execSync(`node "${absPath}"`, { stdio: 'inherit', cwd: path.resolve(__dirname, '..') });
  } catch (error) {
    console.error(`[build-windows] Validation failed!`);
    process.exit(1);
  }
}

function main() {
  const repoRoot = path.resolve(__dirname, '..');
  
  console.log(`[build-windows] Building Windows app in: ${repoRoot}`);
  
  // Run appId validation first
  runScript('scripts/validate-appid.js');
  
  // Build with electron-builder
  console.log(`\n[build-windows] Starting electron-builder...\n`);
  try {
    execSync('npx electron-builder --win nsis', { 
      stdio: 'inherit', 
      cwd: repoRoot,
      env: { ...process.env }
    });
    console.log(`\n[build-windows] Build completed successfully!`);
  } catch (error) {
    console.error(`\n[build-windows] Build failed!`);
    process.exit(1);
  }
}

main();
