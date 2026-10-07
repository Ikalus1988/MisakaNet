import type { Client as McpClient } from "@modelcontextprotocol/sdk/client/index.js";

export interface StdioTransportConfig {
  type: "stdio";
  command: string;
  args?: string[];
  env?: NodeJS.ProcessEnv;
  headers?: Record<string, string>;
}

export interface StreamableHTTPTransportConfig {
  type: "streamable-http";
  url: string;
  requestInit?: RequestInit;
  headers?: Record<string, string>;
}

export type McpTransportConfig = StdioTransportConfig | StreamableHTTPTransportConfig;

export interface McpServerConfig {
  name: string;
  transport: McpTransportConfig;
}

export interface McpClientConfig {
  servers: McpServerConfig[];
}
