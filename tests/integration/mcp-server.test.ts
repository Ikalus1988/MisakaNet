import { describe, it, expect, beforeEach } from "vitest";
import { createMcpServer } from "../../src/server";
import { normalizeToolSchema } from "../../src/tools";

describe("MCP Server Integration", () => {
  let server: ReturnType<typeof createMcpServer>;

  beforeEach(() => {
    server = createMcpServer();
  });

  it("should list tools with normalized schemas", async () => {
    // Test that normalizeToolSchema strips disallowed keywords
    const schemaWithExtraKeywords = {
      type: "object",
      properties: {
        id: {
          type: "string",
          description: "Item ID",
        },
      },
      required: ["id"],
      minProperties: 1,
      maxProperties: 10,
      additionalProperties: false,
    };

    const normalized = normalizeToolSchema(schemaWithExtraKeywords);

    expect(normalized).toEqual({
      type: "object",
      properties: {
        id: {
          type: "string",
          description: "Item ID",
        },
      },
      required: ["id"],
      additionalProperties: false,
    });
    expect(normalized).not.toHaveProperty("minProperties");
    expect(normalized).not.toHaveProperty("maxProperties");
  });

  it("should recursively normalize nested schemas", async () => {
    const nestedSchema = {
      type: "object",
      properties: {
        items: {
          type: "array",
          items: {
            type: "object",
            properties: {
              name: { type: "string" },
            },
            minProperties: 1,
            required: ["name"],
          },
        },
      },
      minProperties: 1,
    };

    const normalized = normalizeToolSchema(nestedSchema);

    expect(normalized).toEqual({
      type: "object",
      properties: {
        items: {
          type: "array",
          items: {
            type: "object",
            properties: {
              name: { type: "string" },
            },
            required: ["name"],
          },
        },
      },
    });
  });
});
