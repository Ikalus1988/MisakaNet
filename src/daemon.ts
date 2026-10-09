import { platform, homedir } from 'os';

function containsNonAscii(str: string): boolean {
  return /[^\x00-\x7F]/.test(str);
}

export async function start() {
  // Windows-specific workaround for non-ASCII username causing embedded PostgreSQL to fail
  if (platform() === 'win32') {
    const homeDir = homedir();
    if (containsNonAscii(homeDir)) {
      // Set default external PostgreSQL environment variables if not already set
      if (process.env.HINDSIGHT_API_POSTGRES_HOST == null) {
        process.env.HINDSIGHT_API_POSTGRES_HOST = 'localhost';
      }
      if (process.env.HINDSIGHT_API_POSTGRES_PORT == null) {
        process.env.HINDSIGHT_API_POSTGRES_PORT = '5432';
      }
      if (process.env.HINDSIGHT_API_POSTGRES_USER == null) {
        process.env.HINDSIGHT_API_POSTGRES_USER = 'postgres';
      }
      if (process.env.HINDSIGHT_API_POSTGRES_PASSWORD == null) {
        process.env.HINDSIGHT_API_POSTGRES_PASSWORD = 'postgres';
      }
      if (process.env.HINDSIGHT_API_POSTGRES_DB == null) {
        process.env.HINDSIGHT_API_POSTGRES_DB = 'postgres';
      }
    }
  }

  // Existing daemon start logic continues here...
  // ... (rest of the function remains unchanged)
}
