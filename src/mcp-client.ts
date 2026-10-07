import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";
import { PostMessageClientTransport } from "@modelcontextprotocol/sdk/client/postMessage.js";
import type { Transport } from "@modelcontextprotocol/sdk/shared/transport.js";
import type { CallToolResult, ListToolsResult, ServerCapabilities } from "@modelcontextprotocol/sdk/types.js";

export interface McpClientConfig {
  command: string;
  args?: string[];
  env?: Record<string, string>;
  timeoutMs?: number;
  maxAttempts?: number;
  initialRetryDelayMs?: number;
  maxRetryDelayMs?: number;
}

export interface McpClientState {
  connected: boolean;
  connectedAt: Date | undefined;
  lastError: string | undefined;
  toolCount: number;
  tools: Array<{ name: string; description: string }>;
}

export class McpClient {
  private client: Client | null = null;
  private transport: Transport | null = null;
  private state: McpClientState = {
    connected: false,
    connectedAt: undefined,
    lastError: undefined,
    toolCount: 0,
    tools: [],
  };
  private retryCount = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private readonly maxAttempts: number;
  private readonly initialRetryDelayMs: number;
  private readonly maxRetryDelayMs: number;
  private stopReconnecting = false;

  constructor(
    private config: McpClientConfig,
    private onStateChange?: (state: McpClientState) => void
  ) {
    this.maxAttempts = config.maxAttempts ?? 10;
    this.initialRetryDelayMs = config.initialRetryDelayMs ?? 500;
    this.maxRetryDelayMs = config.maxRetryDelayMs ?? 30000;
  }

  get state(): McpClientState {
    return { ...this.state };
  }

  get connectedAt(): Date | undefined {
    return this.state.connectedAt;
  }

  async connect(): Promise<void> {
    this.stopReconnecting = false;
    this.retryCount = 0;
    await this.doConnect();
  }

  async doConnect(): Promise<void> {
    try {
      if (this.client) {
        await this.client.close();
        this.client = null;
      }
      if (this.transport) {
        await this.disposeTransport(this.transport);
        this.transport = null;
      }

      this.transport = await this.createTransport();
      this.client = new Client(
        { name: "misakanet-mcp-client", version: "2.42.0" },
        { capabilities: {} }
      );
      await this.client.connect(this.transport);

      const toolsResult = await this.client.listTools();
      this.state.tools = toolsResult.tools.map((t) => ({
        name: t.name,
        description: t.description ?? "",
      }));
      this.state.toolCount = this.state.tools.length;
      this.state.connected = true;
      this.state.connectedAt = new Date();
      this.state.lastError = undefined;
      this.retryCount = 0;
      this.notifyStateChange();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      this.state.lastError = errorMessage;
      this.state.connected = false;
      this.state.connectedAt = undefined;
      this.notifyStateChange();
      this.scheduleReconnect(errorMessage);
    }
  }

  private scheduleReconnect(lastError: string): void {
    if (this.stopReconnecting) {
      this.state.lastError = `giving up after ${this.retryCount} consecutive failed reconnect attempts — tools unregistered; reload the plugin or restart the Host to reconnect`;
      this.notifyStateChange();
      return;
    }

    if (this.retryCount >= this.maxAttempts) {
      // Never permanently give up — keep retrying with capped delay
      this.state.lastError = `reconnecting after ${this.retryCount} failed attempts (auto-retrying indefinitely)`;
      this.notifyStateChange();
    }

    const delay = Math.min(
      this.initialRetryDelayMs * Math.pow(2, Math.min(this.retryCount, 10)),
      this.maxRetryDelayMs
    );
    this.retryCount++;

    console.warn(
      `[misakanet] reconnect attempt ${this.retryCount}/${this.maxAttempts === Infinity ? "∞" : this.maxAttempts} in ${delay}ms`
    );

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.doConnect().catch(() => {});
    }, delay);
  }

  async reconnect(): Promise<void> {
    this.stopReconnecting = false;
    this.retryCount = 0;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    await this.doConnect();
  }

  async disconnect(): Promise<void> {
    this.stopReconnecting = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.client) {
      await this.client.close();
      this.client = null;
    }
    if (this.transport) {
      await this.disposeTransport(this.transport);
      this.transport = null;
    }
    this.state.connected = false;
    this.state.connectedAt = undefined;
    this.notifyStateChange();
  }

  async callTool(name: string, args?: Record<string, unknown>): Promise<CallToolResult> {
    if (!this.client || !this.state.connected) {
      throw new Error("mcp-client(misakanet): server is disconnected");
    }
    return this.client.callTool({ name, arguments: args });
  }

  async listTools(): Promise<ListToolsResult> {
    if (!this.client || !this.state.connected) {
      throw new Error("mcp-client(misakanet): server is disconnected");
    }
    return { tools: this.state.tools };
  }

  private async createTransport(): Promise<Transport> {
    const env = { ...process.env, ...this.config.env };
    const transport = new StdioClientTransport({
      command: this.config.command,
      args: this.config.args ?? [],
      env,
      stderr: "pipe",
    });

    transport.onerror = (error) => {
      console.error("[misakanet] transport error:", error);
    };

    transport.onclose = () => {
      if (!this.stopReconnecting) {
        console.warn("[misakanet] transport closed unexpectedly, scheduling reconnect");
        this.doConnect().catch(() => {});
      }
    };

    return transport;
  }

  private async disposeTransport(transport: Transport): Promise<void> {
    if ("close" in transport && typeof (transport as { close?: () => Promise<void> }).close === "function") {
      await (transport as { close: () => Promise<void> }).close();
    }
  }

  private notifyStateChange(): void {
    this.onStateChange?.(this.state);
  }
}
