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
}

/**
 * Build a 4-field JSON payload string.
 * @param reason - The error reason type
 */
export function buildPayload(reason: FatalPayload['reason']): string;

/**
 * Fire-and-forget external handler invocation.
 * Reads FATAL_HANDLER env var, spawns with 4-field JSON payload as argv[1].
 * Never throws. Never blocks shutdown.
 * @param reason - The error reason type
 */
export function runHandler(reason: FatalPayload['reason']): void;
