#!/usr/bin/env node
/**
 * Validation script for electron-builder NSIS installation upgrade
 * 
 * Issue #3093: When building from source, if DSH_DESKTOP_APP_ID in .env does not match
 * the online distribution's appId, NSIS cannot detect the existing installation
 * because the registry key (based on UUID.v5(appId)) will differ.
 * 
 * This script validates that the app ID used during build matches what's expected.
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// NSIS uses this fixed UUID namespace
const NSIS_UUID_NAMESPACE = '50e065bc-3134-11e6-9bab-38c9862bdaf3';

function generateAppGuid(appId) {
  // NSIS computes GUID via UUID.v5(appId, namespace)
  // We replicate this using Node.js built-in crypto
  const { createHash } = require('crypto');
  
  // NSIS uses SHA-1 for UUID v5
  const sha1 = createHash('sha1');
  sha1.update(appId);
  sha1.update(Buffer.from(NSIS_UUID_NAMESPACE.replace(/-/g, ''), 'hex'));
  
  const hash = sha1.digest();
  
  // Set version bits (version 5 = 0x50)
  hash[6] = (hash[6] & 0x0f) | 0x50;
  // Set variant bits (RFC 4122 variant = 0x80)
  hash[8] = (hash[8] & 0x3f) | 0x80;
  
  const hex = Buffer.from(hash).toString('hex');
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20,32)}`;
}

function loadEnvFile(filePath) {
  if (!fs.existsSync(filePath)) {
    return {};
  }
  const content = fs.readFileSync(filePath, 'utf8');
  const env = {};
  for (const line of content.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const match = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (match) {
      env[match[1]] = match[2].replace(/^["']|["']$/g, '');
    }
  }
  return env;
}

function main() {
  const repoRoot = path.resolve(__dirname, '..');
  
  // Load .env.windows if it exists
  const envWindowsPath = path.join(repoRoot, '.env.windows');
  const envExamplePath = path.join(repoRoot, '.env.windows.example');
  
  const envWindows = loadEnvFile(envWindowsPath);
  const envExample = loadEnvFile(envExamplePath);
  
  const appid = envWindows.DSH_DESKTOP_APP_ID || envExample.DSH_DESKTOP_APP_ID;
  
  if (!appid) {
    console.error('ERROR: DSH_DESKTOP_APP_ID not found in .env.windows or .env.windows.example');
    process.exit(1);
  }
  
  const expectedGuid = generateAppGuid(appid);
  const registryKey = `Software\\${expectedGuid}`;
  
  console.log(`✓ appId: ${appid}`);
  console.log(`✓ Expected NSIS registry key: HKCU\\${registryKey}`);
  console.log(`✓ InstallLocation should be at: HKCU\\${registryKey}\\InstallLocation`);
  
  // Check if this matches a known distribution
  const knownDistributionId = 'com.deepseek.dsh';
  if (appid !== knownDistributionId) {
    console.warn(`⚠ WARNING: DSH_DESKTOP_APP_ID is "${appid}" but expected "${knownDistributionId}"`);
    console.warn(`  This may cause NSIS to fail to detect existing installations.`);
    console.warn(`  If you're building for distribution, ensure DSH_DESKTOP_APP_ID matches the release version.`);
  } else {
    console.log(`✓ appId matches known distribution: ${knownDistributionId}`);
  }
  
  // Read package.json to verify consistency
  const packageJsonPath = path.join(repoRoot, 'packages', 'desktop', 'package.json');
  if (fs.existsSync(packageJsonPath)) {
    const pkg = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
    const pkgAppId = pkg.dshDesktopAppId || pkg.build?.appId;
    if (pkgAppId && pkgAppId !== appid) {
      console.error(`ERROR: Mismatch detected!`);
      console.error(`  .env.windows DSH_DESKTOP_APP_ID = ${appid}`);
      console.error(`  packages/desktop/package.json dshDesktopAppId = ${pkgAppId}`);
      console.error(`  These must match for NSIS upgrade to work correctly.`);
      process.exit(1);
    }
    console.log(`✓ package.json appId matches: ${pkgAppId || 'not set (using env)'}`);
  }
  
  console.log('');
  console.log('Validation passed. Build can proceed.');
}

main();
