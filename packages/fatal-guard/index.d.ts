/**
 * @misaka-net/fatal-guard — TypeScript declaration
 */

export interface FatalPayload {
  /** Payload format version (always 1) */
  schemaVersion: 1;
  /** Error reason type */
  reason: 'uncaught_exception' | 'unhandled_rejection' | 'exit_code';
  /** ISO 8601 timestamp */
  timestamp: string;
  /** Process ID */
  pid: number;
  /** Error constructor name (v0.3+) */
  errorName?: string;
  /** Redacted error message, max 300 chars (v0.3+) */
  message?: string;
  /** Redacted stack trace snippet, max 1000 chars (v0.3+) */
  stackSnippet?: string;
}

/**
 * Build a JSON payload string with diagnostic fields.
 * @param reason - The error reason type
 * @param error - Optional error object or message for diagnostic payload
 */
export function buildPayload(reason: FatalPayload['reason'], error?: Error | string): string;

/**
 * Fire-and-forget external handler invocation.
 * Reads FATAL_HANDLER env var (or fallback chain), spawns with JSON payload as argv[1].
 * Never throws. Never blocks shutdown.
 * @param reason - The error reason type
 * @param error - Optional error object for diagnostic payload
 * @param customPayload - Optional pre-built JSON payload (wrapper mode passes extra fields)
 */
export function runHandler(reason: FatalPayload['reason'], error?: Error | string, customPayload?: string): void;
