import { MCPClient, ConnectionError, ErrorCode } from '../types';

export enum NegotiationMode {
  AUTO = 'auto',
  LEGACY = 'legacy',
  MODERN = 'modern'
}

export interface NegotiationConfig {
  mode: NegotiationMode;
  headers?: Record<string, string>;
}

export class VersionNegotiator {
  constructor(private client: MCPClient, private config: NegotiationConfig) {}

  async negotiate(): Promise<string> {
    if (this.config.mode === NegotiationMode.LEGACY) {
      return '2025-era';
    }

    if (this.config.mode === NegotiationMode.MODERN) {
      return '2026-07-28';
    }

    // Mode: AUTO
    try {
      const version = await this.probeModernVersion();
      return version;
    } catch (error: any) {
      // BUG FIX: Se o servidor retornar 401 durante o probe 'server/discover',
      // não devemos abortar imediatamente com CLIENT_HTTP_AUTHENTICATION.
      // Um servidor 2025-era que exige auth pode responder 401 para o método desconhecido.
      // Devemos fazer o fallback para o modo legacy.
      
      if (error.status === 401 || error.code === ErrorCode.CLIENT_HTTP_AUTHENTICATION) {
        console.warn('Modern version probe failed with 401. Falling back to legacy handshake.');
        return '2025-era';
      }

      throw error;
    }
  }

  private async probeModernVersion(): Promise<string> {
    // Simulação do probe POST <endpoint> com mcp-method: server/discover
    const response = await this.client.request({
      method: 'server/discover',
      headers: {
        'mcp-method': 'server/discover',
        'mcp-protocol-version': '2026-07-28'
      }
    });

    if (response.status === 200) {
      return '2026-07-28';
    }
    
    throw new Error('Negotiation failed');
  }
}
