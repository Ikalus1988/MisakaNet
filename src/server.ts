import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from "@modelcontextprotocol/sdk/types.js";
import { misakaNetTools, normalizeToolSchema } from "./tools.js";
import { misakanetHandler } from "./handlers.js";

const SERVER_VERSION = "1.0.0";
const SERVER_NAME = "misakanet";

export function createMcpServer(): Server {
  const server = new Server(
    {
      name: SERVER_NAME,
      version: SERVER_VERSION,
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => {
    const tools = [
      {
        name: "misakanet_get_lesson",
        description: "Get lesson information from MisakaNet",
        inputSchema: {
          type: "object",
          properties: {
            id: {
              type: "string",
              description: "Lesson ID",
            },
          },
          required: ["id"],
          minProperties: 1,
          additionalProperties: false,
        },
      } as Tool,
      {
        name: "misakanet_me_events",
        description: "Get events for the current user from MisakaNet",
        inputSchema: {
          type: "object",
          properties: {
            limit: {
              type: "number",
              description: "Number of events to return",
            },
          },
          minProperties: 1,
          additionalProperties: false,
        },
      } as Tool,
    ];

    // Normalize schemas by stripping disallowed DSH keywords
    return {
      tools: tools.map((tool) => ({
        ...tool,
        inputSchema: normalizeToolSchema(tool.inputSchema as Record<string, unknown>),
      })),
    };
  });

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const params = misakaNetTools.parse(request.params);
    const result = await misakanetHandler(params.name);
    return result;
  });

  return server;
}

export async function runServer() {
  const transport = new StdioServerTransport();
  const server = createMcpServer();
  await server.connect(transport);
  console.error(`MisakaNet MCP server running on stdio`);
}
