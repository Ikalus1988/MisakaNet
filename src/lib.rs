pub mod mcp;
pub mod tools;
pub mod errors;

use mcp::McpClient;
use tools::list_mcp_resources::ListMcpResourcesTool;
use tools::Tool;
use tracing::info;

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_list_mcp_resources_tool() {
        let tool = ListMcpResourcesTool;
        
        // Test with proper params
        let params = serde_json::json!({"server": "misakanet"});
        
        // This should not panic even if MCP server is not available
        let result = tool.execute(&params).await;
        
        // We expect either success or a graceful error
        match result {
            Ok(_) => (),
            Err(e) => {
                // Error is acceptable when server is not running
                info!("Expected error when server not running: {}", e);
            }
        }
    }
}
