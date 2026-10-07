use thiserror::Error;
use std::fmt;

#[derive(Error, Debug)]
pub enum McpError {
    #[error("Server is disconnected")]
    ServerDisconnected,
    
    #[error("Connection failed: {0}")]
    ConnectionFailed(String),
    
    #[error("Request timeout")]
    Timeout,
    
    #[error("Invalid response: {0}")]
    InvalidResponse(String),
    
    #[error("Parse error: {0}")]
    ParseError(#[from] serde_json::Error),
    
    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
    
    #[error("Channel closed")]
    ChannelClosed,
}

impl McpError {
    /// Check if the error is recoverable by reconnect
    pub fn is_recoverable(&self) -> bool {
        matches!(self, McpError::ServerDisconnected | McpError::ConnectionFailed(_))
    }
}
