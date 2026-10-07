import { McpClient } from "../mcp/client.js";
import type { McpClientConfig } from "../mcp/types.js";
import { Logger } from "../utils/logger.js";

export class McpService {
  private clients: Map<string, McpClient> = new Map();
  private config: McpClientConfig;
  private logger = new Logger("mcp-service");

  constructor(config: McpClientConfig) {
    this.config = config;
  }

  async initialize(): Promise<void> {
    for (const server of this.config.servers) {
      try {
        const client = new McpClient();
        await client.connect(server);
        this.clients.set(server.name, client);
        this.logger.info(`Connected to MCP server: ${server.name}`);
      } catch (error) {
        this.logger.error(
          `Failed to connect to MCP server ${server.name}: ${error}`
        );
      }
    }
  }

  async disconnect(): Promise<void> {
    for (const [name, client] of this.clients) {
      try {
        await client.disconnect();
        this.logger.info(`Disconnected from MCP server: ${name}`);
      } catch (error) {
        this.logger.error(
          `Failed to disconnect MCP server ${name}: ${error}`
        );
      }
    }
    this.clients.clear();
  }

  getServer(name: string): McpClient | undefined {
    return this.clients.get(name);
  }
}
