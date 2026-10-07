use std::sync::Arc;
use tokio::sync::Mutex;
use futures::channel::mpsc;
use futures::{SinkExt, StreamExt};
use serde_json::Value;
use tracing::{info, error, warn};

/// MCP Client that manages connections to MCP servers
#[derive(Clone)]
pub struct McpClient {
    state: Arc<Mutex<ClientState>>,
}

#[derive(Debug)]
enum ClientState {
    Connected {
        sender: mpsc::Sender<crate::protocol::McpMessage>,
        _handle: tokio::task::JoinHandle<()>,
    },
    Disconnected,
}

impl McpClient {
    /// Create a new MCP client
    pub fn new(server_name: &str) -> Self {
        info!(%server_name, "Creating MCP client");
        Self {
            state: Arc::new(Mutex::new(ClientState::Disconnected)),
        }
    }

    /// Connect to the MCP server
    pub async fn connect(&self) -> Result<(), crate::errors::McpError> {
        let mut state = self.state.lock().await;
        
        match *state {
            ClientState::Connected { .. } => {
                return Ok(());
            }
            ClientState::Disconnected => {}
        }

        // Start the MCP server subprocess
        let (mut sender, receiver) = mpsc::channel::<crate::protocol::McpMessage>(32);
        
        let handle = tokio::spawn(async move {
            // TODO: Implement actual server connection
            // For now, simulate a connection
        });

        *state = ClientState::Connected {
            sender,
            _handle: handle,
        };

        Ok(())
    }

    /// List resources from the MCP server
    pub async fn list_resources(&self) -> Result<Vec<crate::protocol::Resource>, crate::errors::McpError> {
        let state = self.state.lock().await;
        
        match *state {
            ClientState::Connected { ref sender, .. } => {
                // Send list_resources request
                let request = crate::protocol::McpMessage {
                    id: None,
                    method: "resources/list".to_string(),
                    params: Some(serde_json::json!({})),
                };
                
                // Drop the lock before sending to avoid deadlock
                drop(state);
                
                let mut sender = self.state.lock().await;
                match &mut *sender {
                    ClientState::Connected { sender, .. } => {
                        if let Err(e) = sender.send(request).await {
                            error!(error = %e, "Failed to send list_resources request");
                            return Err(crate::errors::McpError::ServerDisconnected);
                        }
                    }
                    ClientState::Disconnected => {
                        error!("Server is disconnected");
                        return Err(crate::errors::McpError::ServerDisconnected);
                    }
                }
                
                Ok(vec![])
            }
            ClientState::Disconnected => {
                error!("Cannot list resources: server is disconnected");
                Err(crate::errors::McpError::ServerDisconnected)
            }
        }
    }

    /// Check if the server is connected
    pub async fn is_connected(&self) -> bool {
        matches!(*self.state.lock().await, ClientState::Connected { .. })
    }

    /// Reconnect to the server
    pub async fn reconnect(&self) -> Result<(), crate::errors::McpError> {
        error!("Attempting to reconnect to MCP server");
        
        {
            let mut state = self.state.lock().await;
            *state = ClientState::Disconnected;
        }
        
        self.connect().await
    }
}

impl Drop for McpClient {
    fn drop(&mut self) {
        // Clean up resources
    }
}
