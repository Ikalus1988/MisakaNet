```typescript
import { ProfileCompatibility } from '../profile';
import { loadProfileDirectory, readProfileManifest, readProfileVersionExemptions } from './profile-loader';

export class AppBoot {
  private readonly profileDir: string;
  
  constructor(profileDir: string) {
    this.profileDir = profileDir;
  }

  /**
   * Load profile and check for compatibility issues
   */
  async loadProfile(): Promise<{
    skippedBundles: string[];
    loadedBundles: string[];
  }> {
    const compat = new ProfileCompatibility(this.profileDir);
    
    // Read manifest
    const manifest = readProfileManifest(this.profileDir);
    
    // Read version exemptions
    const exemptions = readProfileVersionExemptions(this.profileDir);
    
    // Load profile directory
    const result = await loadProfileDirectory(this.profileDir, exemptions);
    
    return result;
  }

  /**
   * Start the application
   */
  async start(): Promise<void> {
    const { skippedBundles, loadedBundles } = await this.loadProfile();
    
    if (skippedBundles.length > 0) {
      console.warn(`Skipped ${skippedBundles.length} bundles due to incompatibility:`);
      for (const pkg of skippedBundles) {
        console.warn(`  - ${pkg}`);
      }
    }
    
    console.log(`Loaded ${loadedBundles.length} bundles successfully.`);
    
    // Start MCP servers and other services
    await this.startServices();
  }

  private async startServices(): Promise<void> {
    // Service initialization logic
  }
}
