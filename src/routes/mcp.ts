import { Router } from "express";
import { McpService } from "../services/mcpService.js";
import { Logger } from "../utils/logger.js";

const logger = new Logger("mcp-router");

export function createMcpRouter(mcpService: McpService): Router {
  const router = Router();

  router.get("/servers", (req, res) => {
    const servers = Array.from(mcpService["clients"].keys());
    res.json({ servers });
  });

  router.post("/disconnect/:name", (req, res) => {
    const client = mcpService.getServer(req.params.name);
    if (!client) {
      res.status(404).json({ error: "Server not found" });
      return;
    }
    client.disconnect().then(() => res.json({ ok: true }));
  });

  router.get("/status/:name", async (req, res) => {
    const client = mcpService.getServer(req.params.name);
    if (!client) {
      res.status(404).json({ error: "Server not found" });
      return;
    }
    try {
      const result = await client.getClient().callTool({
        name: "list_tools",
      });
      res.json({ status: "connected", tools: result });
    } catch (error) {
      res.status(500).json({ status: "error", message: String(error) });
    }
  });

  return router;
}
