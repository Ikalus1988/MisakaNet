/**
 * MisakaNet DSH plugin — type declarations.
 */
export const name: 'misakanet';

export interface MisakaNetPluginConfig {
  /** Optional: override the MCP endpoint advertised to agents. */
  mcpUrl?: string;
}

export function apply(ctx: unknown, config?: MisakaNetPluginConfig): void;
