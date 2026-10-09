```typescript
import { readFileSync, existsSync } from 'fs';
import { join } from 'path';
import { ProfileCompatibility, CompatibilityEntry } from '../profile';

/**
 * Read profile manifest
 */
export function readProfileManifest(profileDir: string): any {
  const manifestPath = join(profileDir, 'package.json');
  if (!existsSync(manifestPath)) {
    return null;
  }
  return JSON.parse(readFileSync(manifestPath, 'utf-8'));
}

/**
 * Read version exemptions from compatibility.json
 * Handles both flat and legacy wrapped formats
 */
export function readProfileVersionExemptions(profileDir: string): CompatibilityEntry {
  const compat = new ProfileCompatibility(profileDir);
  return compat.readCompatibility();
}

/**
 * Load profile directory and check for compatibility
 */
export async function loadProfileDirectory(
  profileDir: string,
  exemptions: CompatibilityEntry
): Promise<{
  skippedBundles: string[];
  loadedBundles: string[];
}> {
  const manifest = readProfileManifest(profileDir);
  const bundles = manifest?.dsh?.profile?.bundles || [];
  
  const skippedBundles: string[] = [];
  const loadedBundles: string[] = [];
  
  for (const bundle of bundles) {
    // Check if this bundle has version exemptions
    const versionExemptions = exemptions[bundle] || [];
    
    // In a real implementation, we would check the current runtime version
    // against the exemptions list
    // For now, assume all bundles load successfully if they have exemptions
    if (versionExemptions.length > 0) {
      loadedBundles.push(bundle);
    } else {
      // Check if bundle should be skipped
      // This would involve checking compatibility matrix
      loadedBundles.push(bundle);
    }
  }
  
  return { skippedBundles, loadedBundles };
}
