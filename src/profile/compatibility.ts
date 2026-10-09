```typescript
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { join } from 'path';

export interface CompatibilityEntry {
  [packageVersion: string]: string[];
}

export interface ProfileManifest {
  name: string;
  version: string;
  dsh?: {
    profile?: {
      bundles?: string[];
    };
  };
}

export class ProfileCompatibility {
  private readonly profileDir: string;
  
  constructor(profileDir: string) {
    this.profileDir = profileDir;
  }

  /**
   * Read compatibility.json - handles both flat and wrapped formats
   * Legacy format: {"exemptions": {"pkg@ver": ["runtimeVer"]}}
   * Correct format: {"pkg@ver": ["runtimeVer"]}
   */
  readCompatibility(): CompatibilityEntry {
    const compatPath = join(this.profileDir, 'compatibility.json');
    if (!existsSync(compatPath)) {
      return {};
    }

    const raw = JSON.parse(readFileSync(compatPath, 'utf-8'));
    
    // Handle legacy wrapped format
    if (raw.exemptions && typeof raw.exemptions === 'object') {
      console.warn(
        `[DSH] Deprecation: compatibility.json uses legacy "exemptions" wrapper format. ` +
        `Please migrate to flat format: { "pkg@ver": ["runtimeVer"] }`
      );
      return raw.exemptions as CompatibilityEntry;
    }
    
    // Ensure we're returning the correct flat format
    if (typeof raw === 'object' && !raw.exemptions) {
      return raw as CompatibilityEntry;
    }
    
    return {};
  }

  /**
   * Write compatibility.json in correct flat format
   */
  writeCompatibility(exemptions: CompatibilityEntry): void {
    const compatPath = join(this.profileDir, 'compatibility.json');
    writeFileSync(compatPath, JSON.stringify(exemptions, null, 2), 'utf-8');
  }

  /**
   * Read profile manifest (package.json)
   */
  readManifest(): ProfileManifest | null {
    const manifestPath = join(this.profileDir, 'package.json');
    if (!existsSync(manifestPath)) {
      return null;
    }
    return JSON.parse(readFileSync(manifestPath, 'utf-8'));
  }

  /**
   * Check if a package is in the profile's bundles list
   */
  isPackageInBundles(packageVersion: string): boolean {
    const manifest = this.readManifest();
    if (!manifest?.dsh?.profile?.bundles) {
      return false;
    }
    return manifest.dsh.profile.bundles.includes(packageVersion);
  }

  /**
   * Ensure all exempted packages are in the profile's bundles list
   */
  syncBundlesFromCompatibility(): void {
    const manifest = this.readManifest();
    if (!manifest) {
      return;
    }

    if (!manifest.dsh) manifest.dsh = {};
    if (!manifest.dsh.profile) manifest.dsh.profile = {};
    if (!manifest.dsh.profile.bundles) manifest.dsh.profile.bundles = [];

    const compat = this.readCompatibility();
    const requiredBundles = Object.keys(compat);
    
    let changed = false;
    for (const pkgVer of requiredBundles) {
      if (!manifest.dsh.profile.bundles.includes(pkgVer)) {
        manifest.dsh.profile.bundles.push(pkgVer);
        changed = true;
      }
    }

    if (changed) {
      const manifestPath = join(this.profileDir, 'package.json');
      writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), 'utf-8');
    }
  }

  /**
   * Get version exemptions for a specific package
   */
  getVersionExemptions(packageVersion: string): string[] {
    const compat = this.readCompatibility();
    return compat[packageVersion] || [];
  }

  /**
   * Add version exemption
   */
  addVersionExemption(packageVersion: string, runtimeVersions: string[]): void {
    const compat = this.readCompatibility();
    compat[packageVersion] = runtimeVersions;
    this.writeCompatibility(compat);
    this.syncBundlesFromCompatibility();
  }

  /**
   * List all version exemptions
   */
  listVersionExemptions(): Array<{ package: string; exemptions: string[] }> {
    const compat = this.readCompatibility();
    return Object.entries(compat).map(([pkg, versions]) => ({
      package: pkg,
      exemptions: versions
    }));
  }
}
