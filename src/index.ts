#!/usr/bin/env node
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { MisakaNetServer } from "./server.js";

function getConfig() {
  const url = process.env.MISAKANET_URL;
  const apiKey = process.env.MISAKANET_API_KEY;
  const model = process.env.MISAKANET_MODEL;
  const maxAttempts = process.env.MISAKANET_MAX_ATTEMPTS
    ? parseInt(process.env.MISAKANET_MAX_ATTEMPTS, 10)
    : undefined;
  const initialRetryDelayMs = process.env.MISAKANET_INITIAL_RETRY_DELAY_MS
    ? parseInt(process.env.MISAKANET_INITIAL_RETRY_DELAY_MS, 10)
    : undefined;
  const maxRetryDelayMs = process.env.MISAKANET_MAX_RETRY_DELAY_MS
    ? parseInt(process.env.MISAKANET_MAX_RETRY_DELAY_MS, 10)
    : undefined;

  if (!url || !apiKey) {
    throw new Error(
      "Missing required environment variables: MISAKANET_URL and MISAKANET_API_KEY"
    );
  }

  return { misakaNetUrl: url, apiKey, model, maxAttempts, initialRetryDelayMs, maxRetryDelayMs };
}

async function main() {
  const config = getConfig();
  const server = new MisakaNetServer(config);

  const transport = new StdioServerTransport();
  await server.connect();
  await server.server.connect(transport);

  console.error("[misakanet] server started on stdio");
}

main().catch((error) => {
  console.error("[misakanet] fatal error:", error);
  process.exit(1);
});
