import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import type { McpClientConfig, McpServerConfig } from "./types.js";

export class McpClient {
  private client: Client | null = null;
  private transport: StdioClientTransport | StreamableHTTPClientTransport | null = null;

  async connect(config: McpServerConfig): Promise<void> {
    if (this.client) {
      await this.disconnect();
    }

    this.transport =
      config.transport.type === "stdio"
        ? new StdioClientTransport({
            command: config.transport.command,
            args: config.transport.args ?? [],
            env: config.transport.env,
          })
        : new StreamableHTTPClientTransport(new URL(config.transport.url), {
            requestInit: config.transport.requestInit,
          });

    // Pin to legacy protocol version to avoid modern-era required fields
    // (resultType, ttlMs, cacheScope) on tools/list when the server
    // only declares them on server/discover.
    this.client = new Client(
      { name: "misakanet", version: "1.0.0" },
      {
        capabilities: {},
      },
      {
        versionNegotiation: { mode: "disabled" },
      }
    );

    await this.client.connect(this.transport);

    // Send initialize with explicit legacy protocol version.
    // The SDK will still do its handshake; we override via custom headers.
    const headers: Record<string, string> = {
      ...(config.transport.headers ?? {}),
      "MCP-Protocol-Version": "2025-06-18",
    };

    // For streamable-http we re-create the transport with fixed headers.
    if (config.transport.type === "streamable-http") {
      const legacyTransport = new StreamableHTTPClientTransport(
        new URL(config.transport.url),
        {
          requestInit: {
            ...config.transport.requestInit,
            headers,
          },
        }
      );
      await this.client.connect(legacyTransport);
      this.transport = legacyTransport;
    }
  }

  async disconnect(): Promise<void> {
    if (this.client) {
      await this.client.close();
      this.client = null;
    }
    this.transport = null;
  }

  getClient(): Client {
    if (!this.client) {
      throw new Error("MCP client not connected");
    }
    return this.client;
  }
}
