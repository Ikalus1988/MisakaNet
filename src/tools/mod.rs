use async_trait::async_trait;
use serde_json::Value;

pub mod list_mcp_resources;

pub use list_mcp_resources::ListMcpResourcesTool;

#[async_trait]
pub trait Tool: Send + Sync {
    fn name(&self) -> &str;
    fn description(&self) -> &str;
    
    async fn execute(&self, params: &Value) -> Result<ToolResult, ToolError>;
}

#[derive(Debug)]
pub enum ToolResult {
    Success { content: String },
    Error { error: String },
}

#[derive(Debug, thiserror::Error)]
pub enum ToolError {
    #[error("Execution error: {0}")]
    ExecutionError(String),
    
    #[error("Invalid parameters: {0}")]
    InvalidParams(String),
}
