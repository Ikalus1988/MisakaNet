use super::{Tool, ToolResult, ToolError};
use crate::mcp::client::McpClient;
use tracing::info;

/// Tool that lists resources from the MCP server
pub struct ListMcpResourcesTool;

impl Tool for ListMcpResourcesTool {
    fn name(&self) -> &str {
        "list_mcp_resources"
    }

    fn description(&self) -> &str {
        "List all resources available from the MCP server"
    }

    async fn execute(&self, params: &serde_json::Value) -> Result<ToolResult, ToolError> {
        let server = params.get("server")
            .and_then(|s| s.as_str())
            .unwrap_or("default");

        info!(%server, "Executing list_mcp_resources");

        // Get or create the MCP client for this server
        let client = McpClient::new(server);
        
        // Ensure connection is established
        if !client.is_connected().await {
            info!(%server, "Connecting to MCP server");
            client.connect().await.map_err(|e| {
                ToolError::ExecutionError(format!("Failed to connect to MCP server {}: {}", server, e))
            })?;
        }

        // List resources
        let resources = client.list_resources().await.map_err(|e| {
            ToolError::ExecutionError(format!("MCP client error: {}", e))
        })?;

        Ok(ToolResult::Success {
            content: format!("{:#?}", resources),
        })
    }
}
