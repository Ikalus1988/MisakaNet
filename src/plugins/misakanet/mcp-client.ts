import { Client } from "@modelcontextprotocol/client/index.js";
import { SSEClientTransport } from "@modelcontextprotocol/client/sse.js";

interface MisakaNetConfig {
  endpoint: string;
  bearerToken?: string;
  useLegacyMode?: boolean;
}

export class MisakaNetMCPClient {
  private client: Client | null = null;
  private config: MisakaNetConfig;

  constructor(config: MisakaNetConfig) {
    this.config = config;
  }

  async connect() {
    // Se o modo legacy estiver ativado, forçamos a configuração para evitar a probe de negociação v2
    // que causa o 401 no servidor MisakaNet.
    const transportOptions: any = {
      url: this.config.endpoint,
      headers: {}
    };

    if (this.config.bearerToken) {
      transportOptions.headers["Authorization"] = `Bearer ${this.config.bearerToken}`;
    }

    const transport = new SSEClientTransport(transportOptions);

    this.client = new Client(
      {
        name: "misakanet-dsh-plugin",
        version: "1.0.0",
      },
      {
        // A correção principal: Se houver token, garantimos que ele seja enviado.
        // Se o modo legacy for solicitado, desativamos a negociação automática que falha com 401.
        versionNegotiation: this.config.useLegacyMode 
          ? { mode: 'disabled' } 
          : { mode: 'auto' }
      }
    );

    try {
      await this.client.connect(transport);
      console.log("Successfully connected to MisakaNet MCP");
    } catch (error) {
      console.error("Failed to connect to MisakaNet MCP:", error);
      throw error;
    }
  }

  async getClient(): Promise<Client> {
    if (!this.client) {
      throw new Error("Client not connected");
    }
    return this.client;
  }
}
