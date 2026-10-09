```typescript
import { Command } from 'commander';
import { ProfileCompatibility } from '../profile';
import { resolve } from 'path';

export function registerPluginCommands(program: Command) {
  const pluginCmd = program.command('plugin');

  // List version exemptions
  pluginCmd
    .command('version-exemptions')
    .option('--profile <profile>', 'Profile directory')
    .action((options: { profile?: string }) => {
      const profileDir = options.profile 
        ? resolve(options.profile) 
        : process.cwd();
      
      const compat = new ProfileCompatibility(profileDir);
      const exemptions = compat.listVersionExemptions();
      
      if (exemptions.length === 0) {
        console.log('No version exemptions configured.');
        return;
      }
      
      for (const { package: pkg, exemptions: versions } of exemptions) {
        const inBundles = compat.isPackageInBundles(pkg);
        const status = inBundles ? '✓' : '✗ (missing from bundles)';
        console.log(`${pkg}: ${versions.join(', ')} ${status}`);
      }
    });

  // Repair compatibility.json
  pluginCmd
    .command('repair-compatibility')
    .option('--profile <profile>', 'Profile directory')
    .action((options: { profile?: string }) => {
      const profileDir = options.profile 
        ? resolve(options.profile) 
        : process.cwd();
      
      const compat = new ProfileCompatibility(profileDir);
      
      // Migrate from legacy format
      const rawCompatPath = require('path').join(profileDir, 'compatibility.json');
      const fs = require('fs');
      
      if (fs.existsSync(rawCompatPath)) {
        const raw = JSON.parse(fs.readFileSync(rawCompatPath, 'utf-8'));
        if (raw.exemptions && typeof raw.exemptions === 'object') {
          // Migrate to flat format
          compat.writeCompatibility(raw.exemptions as any);
          console.log('Migrated compatibility.json to flat format.');
        } else {
          console.log('compatibility.json is already in correct format.');
        }
      }
      
      // Sync bundles
      compat.syncBundlesFromCompatibility();
      console.log('Synced profile bundles from compatibility entries.');
      
      // Verify
      const exemptions = compat.listVersionExemptions();
      console.log(`Total exemptions: ${exemptions.length}`);
      
      const missingBundles = exemptions.filter(e => !compat.isPackageInBundles(e.package));
      if (missingBundles.length > 0) {
        console.warn('Warning: Some packages not in bundles:');
        for (const e of missingBundles) {
          console.warn(`  - ${e.package}`);
        }
      }
    });
}
