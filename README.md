# MisakaNet

MisakaNet is a capability-based registry system. 

## Troubleshooting AgentCap Registry
If you encounter `secret-safe` validation failures during registry verification, ensure your metadata does not contain plain-text secrets. The registry enforces a strict gate on capability descriptions and metadata fields. 

To verify your configuration, run:
`misakanet-cli verify --registry-path ./registry --verbose`

Success is indicated by: `[OK] Registry integrity verified`.