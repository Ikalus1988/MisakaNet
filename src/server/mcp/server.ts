export interface McpResponse {
  content: string;
  metadata: {
    volume?: number;
  };
}

export const handleMcpRequest = async (request: any): Promise<McpResponse> => {
  //... existing logic
  return {
    content: "Hello from MisakaNet MCP!",
    metadata: {
      volume: parseFloat(localStorage.getItem('voice-volume') || '0.5')
    }
  };
};