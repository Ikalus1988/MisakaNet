```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { ProfileCompatibility } from '../../src/profile';
import { writeFileSync, mkdirSync, rmSync } from 'fs';
import { join } from 'path';

describe('ProfileCompatibility', () => {
  let tempDir: string;
  let compat: ProfileCompatibility;

  beforeEach(() => {
    tempDir = join(process.cwd(), 'test-temp-profile');
    rmSync(tempDir, { recursive: true, force: true });
    mkdirSync(tempDir, { recursive: true });
    compat = new ProfileCompatibility(tempDir);
  });

  afterEach(() => {
    rmSync(tempDir, { recursive: true, force: true });
  });

  describe('readCompatibility', () => {
    it('should return empty object when file does not exist', () => {
      const result = compat.readCompatibility();
      expect(result).toEqual({});
    });

    it('should handle flat format correctly', () => {
      const flatFormat = {
        'pkg-a@1.0.0': ['1.0.0', '2.0.0'],
        'pkg-b@2.0.0': ['1.5.0']
      };
      writeFileSync(
        join(tempDir, 'compatibility.json'),
        JSON.stringify(flatFormat, null, 2)
      );
      
      const result = compat.readCompatibility();
      expect(result).toEqual(flatFormat);
    });

    it('should migrate legacy wrapped format', () => {
      const legacyFormat = {
        exemptions: {
          'pkg-a@1.0.0': ['1.0.0', '2.0.0']
        }
      };
      writeFileSync(
        join(tempDir, 'compatibility.json'),
        JSON.stringify(legacyFormat, null, 2)
      );
      
      // Should not throw and should return the inner object
      const result = compat.readCompatibility();
      expect(result).toEqual({
        'pkg-a@1.0.0': ['1.0.0', '2.0.0']
      });
    });
  });

  describe('writeCompatibility', () => {
    it('should write flat format correctly', () => {
      const exemptions = {
        'pkg-a@1.0.0': ['1.0.0', '2.0.0']
      };
      compat.writeCompatibility(exemptions);
      
      const result = compat.readCompatibility();
      expect(result).toEqual(exemptions);
    });
  });

  describe('syncBundlesFromCompatibility', () => {
    it('should add packages from compatibility to bundles', () => {
      // Create manifest without bundles
      const manifest = {
        name: 'test-profile',
        version: '1.0.0'
      };
      writeFileSync(
        join(tempDir, 'package.json'),
        JSON.stringify(manifest, null, 2)
      );
      
      // Create compatibility with exemptions
      const exemptions = {
        'pkg-a@1.0.0': ['1.0.0'],
        'pkg-b@2.0.0': ['2.0.0']
      };
      compat.writeCompatibility(exemptions);
      
      // Sync bundles
      compat.syncBundlesFromCompatibility();
      
      // Read manifest again
      const updatedManifest = JSON.parse(
        require('fs').readFileSync(join(tempDir, 'package.json'), 'utf-8')
      );
      
      expect(updatedManifest.dsh.profile.bundles).toContain('pkg-a@1.0.0');
      expect(updatedManifest.dsh.profile.bundles).toContain('pkg-b@2.0.0');
    });
  });

  describe('listVersionExemptions', () => {
    it('should return formatted exemption list', () => {
      const exemptions = {
        'pkg-a@1.0.0': ['1.0.0', '2.0.0'],
        'pkg-b@2.0.0': ['1.5.0']
      };
      compat.writeCompatibility(exemptions);
      
      const result = compat.listVersionExemptions();
      
      expect(result).toHaveLength(2);
      expect(result.find(e => e.package === 'pkg-a@1.0.0')).toEqual({
        package: 'pkg-a@1.0.0',
        exemptions: ['1.0.0', '2.0.0']
      });
    });
  });
});
