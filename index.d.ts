/**
 * MisakaNet DSH plugin — type declarations.
 */
export const name: 'misakanet';

/** Stdio declaration for the repo's own python MCP server (see cordis.patch.yml). */
export interface MisakaNetMcpConfig {
  transport?: 'stdio' | 'streamable-http';
  /** Local namespace for model-facing tool names: mcp__<serverName>__<tool>. */
  serverName?: string;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  cwd?: string;
  toolCallTimeoutMs?: number;
  /** When true a missing/unreachable MCP client fails activation instead of degrading. */
  failOnStartupError?: boolean;
  /** Optional: override the MCP endpoint advertised to agents. */
  mcpUrl?: string;
}

/**
 * Mount MisakaNet's MCP server into the host. Resolves the official
 * `@deepseek-ai/dsh-mcp-client` at runtime and mounts it with `config`; returns
 * quietly when that client is absent (npm skill-only installs) unless
 * `failOnStartupError` is set.
 */
export function apply(ctx: unknown, config?: MisakaNetMcpConfig): Promise<void>;

/** Defaults merged under the patch row's config. */
export const DEFAULT_MCP_CONFIG: Readonly<{
  transport: 'stdio';
  serverName: string;
  command: string;
  args: string[];
  env: Record<string, string>;
  cwd: string;
  toolCallTimeoutMs: number;
  failOnStartupError: boolean;
}>;
