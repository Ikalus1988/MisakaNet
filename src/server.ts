import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  InitializeRequestSchema,
  Tool,
} from "@modelcontextprotocol/sdk/types.js";
import { McpClient } from "./mcp-client.js";

export interface MisakaNetServerConfig {
  misakaNetUrl: string;
  apiKey: string;
  model?: string;
  maxAttempts?: number;
  initialRetryDelayMs?: number;
  maxRetryDelayMs?: number;
}

export class MisakaNetServer {
  private server: Server;
  private mcpClient: McpClient;
  private tools: Tool[] = [];

  constructor(config: MisakaNetServerConfig) {
    this.mcpClient = new McpClient(
      {
        command: "node",
        args: [new URL("./index.js", import.meta.url).pathname],
        env: {
          MISAKANET_URL: config.misakaNetUrl,
          MISAKANET_API_KEY: config.apiKey,
          MISAKANET_MODEL: config.model ?? "default",
        },
        maxAttempts: config.maxAttempts,
        initialRetryDelayMs: config.initialRetryDelayMs,
        maxRetryDelayMs: config.maxRetryDelayMs,
      },
      (state) => {
        console.info(`[misakanet] connection state: connected=${state.connected}, tools=${state.toolCount}, error=${state.lastError}`);
      }
    );

    this.server = new Server(
      { name: "misakanet", version: "2.42.0" },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.setupHandlers();
    this.initialize().catch(console.error);
  }

  private async initialize(): Promise<void> {
    console.info("[misakanet] starting MCP server, attempting connection...");
    await this.mcpClient.connect();
    this.updateTools();
    console.info(`[misakanet] initialization complete, ${this.tools.length} tools registered`);
  }

  private setupHandlers(): void {
    this.server.setRequestHandler(InitializeRequestSchema, async (request) => {
      return {
        protocolVersion: "2024-11-05",
        capabilities: { tools: {} },
        serverInfo: { name: "misakanet", version: "2.42.0" },
      };
    });

    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      return { tools: this.tools };
    });

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const toolName = request.params.name;
      const args = request.params.arguments as Record<string, unknown> | undefined;

      try {
        const result = await this.mcpClient.callTool(toolName, args);
        return result;
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return {
          content: [{ type: "text", text: `Error calling tool ${toolName}: ${message}` }],
          isError: true,
        };
      }
    });
  }

  private updateTools(): void {
    this.tools = this.mcpClient.state.tools.map((tool) => ({
      name: tool.name,
      description: tool.description,
      inputSchema: {
        type: "object",
        properties: {},
      } as unknown as { type: string; properties: Record<string, unknown>; required?: string[] },
    }));
  }

  async connect(): Promise<void> {
    await this.initialize();
  }

  getTools(): Tool[] {
    return this.tools;
  }

  getState() {
    return this.mcpClient.state;
  }

  async reconnect(): Promise<void> {
    await this.mcpClient.reconnect();
    this.updateTools();
  }
}
