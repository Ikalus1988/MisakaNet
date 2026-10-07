import { z } from "zod";

export const misakaNetTools = z.object({
  name: z.string(),
  description: z.string().optional(),
  parameters: z.record(z.any()).optional(),
  type: z.string().optional(),
  properties: z.record(z.any()).optional(),
  required: z.array(z.string()).optional(),
});

export type MisakaNetTool = z.infer<typeof misakaNetTools>;

// DSH-enforced JSON Schema keyword subset
const ALLOWED_KEYWORDS = new Set([
  "type",
  "oneOf",
  "properties",
  "required",
  "additionalProperties",
  "items",
  "enum",
  "const",
  "description",
  "title",
]);

/**
 * Recursively strips disallowed JSON Schema keywords from a schema object.
 * Only preserves the DSH-approved subset plus description/title annotations.
 */
export function normalizeToolSchema(schema: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};

  for (const [key, value] of Object.entries(schema)) {
    if (ALLOWED_KEYWORDS.has(key)) {
      if (typeof value === "object" && value !== null && !Array.isArray(value)) {
        result[key] = normalizeToolSchema(value as Record<string, unknown>);
      } else if (Array.isArray(value)) {
        result[key] = value.map((item) =>
          typeof item === "object" && item !== null ? normalizeToolSchema(item as Record<string, unknown>) : item
        );
      } else {
        result[key] = value;
      }
    }
  }

  return result;
}

export function createToolSchema(
  name: string,
  description: string,
  properties: Record<string, unknown>,
  required?: string[]
): Record<string, unknown> {
  return {
    type: "object",
    properties,
    ...(required ? { required } : {}),
    additionalProperties: false,
  };
}
