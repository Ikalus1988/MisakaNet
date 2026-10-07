export interface ToolParameter {
  type: string;
  description?: string;
  enum?: string[];
  properties?: Record<string, ToolParameter>;
  required?: string[];
}

export interface ToolParameters {
  type: string;
  properties: Record<string, ToolParameter>;
  required?: string[];
}

export interface ToolResult {
  success: boolean;
  content: string;
  error?: string;
}

export interface Tool {
  readonly name: string;
  readonly description: string;
  readonly parameters: ToolParameters;
  execute(options: Record<string, unknown>): Promise<ToolResult>;
}
