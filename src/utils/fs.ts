import { join } from 'path';
import { platform } from 'os';

/**
 * Normalizes a path for Windows to handle edge cases like trailing dots
 * by using the extended-length path prefix (\\?\).
 */
export function getSafePath(path: string): string {
  if (platform() === 'win32') {
    // Remove existing prefix if already present to avoid double prefixing
    const cleanPath = path.startsWith('\\\\?\\') ? path.substring(4) : path;
    
    // Use absolute path for extended-length prefix
    const absolutePath = require('path').resolve(cleanPath);
    return `\\\\?\\${absolutePath}`;
  }
  return path;
}

/**
 * Wrapper for file system operations that require path safety on Windows
 */
export async function safeReadDir(path: string) {
  const fs = require('fs').promises;
  return await fs.readdir(getSafePath(path));
}
