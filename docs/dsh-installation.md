# MisakaNet DSH Plugin Installation

This guide covers all methods to install the MisakaNet DSH (Developer Skill Hub) plugin.

## Prerequisites

- **Node.js**: v18.0.0 or higher
- **dsh**: Latest version (install via `npm install -g dsh`)

## Installation Methods

### Method 1: Quick Install (npm)

The fastest way to install MisakaNet:

```bash
dsh plugin add misakanet
```

This downloads the latest published version from npm and registers it with your dsh instance.

### Method 2: Git Install

Install directly from the GitHub repository:

```bash
dsh plugin add github:Ikalus1988/MisakaNet
```

This is useful for getting the latest unreleased changes or contributing to development.

### Method 3: Manual Install (Skill Discovery)

For advanced users or custom setups:

```bash
# Create the skills directory if it doesn't exist
mkdir -p ~/.dsh/skills

# Clone the repository
git clone https://github.com/Ikalus1988/MisakaNet.git ~/.dsh/skills/misakanet

# Verify installation
dsh plugin list
```

### Method 4: Local Development Install

For contributing to MisakaNet:

```bash
# Clone the repository
git clone https://github.com/Ikalus1988/MisakaNet.git
cd MisakaNet

# Install dependencies
npm install

# Link to dsh for local development
dsh plugin link .
```

## Verification

After installation, verify the plugin is loaded:

```bash
dsh plugin list
```

You should see `misakanet` in the list of installed plugins.

Test the skill is accessible:

```bash
dsh skill list | grep misakanet
```

## Configuration

The MisakaNet plugin works out of the box with default configuration. To customize:

```yaml
# ~/.dsh/config.yaml
plugins:
  misakanet:
    enabled: true
    mcp_endpoint: https://misakanet.org/mcp
```

## Troubleshooting

### Permission Issues

If you encounter permission errors:

```bash
# Fix npm permissions
mkdir -p ~/.npm-global
npm config set prefix '~/.npm-global'
export PATH=~/.npm-global/bin:$PATH

# Or use sudo (not recommended)
sudo dsh plugin add misakanet
```

### Version Conflicts

If you have multiple Node.js versions:

```bash
# Check current version
node --version

# Use nvm to switch
nvm use 20

# Reinstall plugin
dsh plugin remove misakanet
dsh plugin add misakanet
```

### Network Problems

If downloads fail:

```bash
# Check network connectivity
curl -I https://registry.npmjs.org/misakanet

# Use alternative registry
dsh plugin add misakanet --registry https://registry.npmmirror.com
```

### Plugin Not Loading

Check dsh logs for errors:

```bash
dsh --verbose plugin list
```

Ensure the plugin files exist:

```bash
ls -la ~/.dsh/plugins/misakanet/
```

## Uninstallation

To remove the MisakaNet plugin:

```bash
dsh plugin remove misakanet
```

To completely clean up:

```bash
# Remove plugin files
rm -rf ~/.dsh/plugins/misakanet
rm -rf ~/.dsh/skills/misakanet

# Remove from config
dsh config edit
# Remove the misakanet section from plugins
```

## Updating

To update to the latest version:

```bash
dsh plugin update misakanet
```

To update to a specific version:

```bash
dsh plugin add misakanet@2.23.0
```

## Integration with AI Agents

The MisakaNet plugin is designed to work with AI coding agents. Once installed:

- **Claude Code**: Automatically discovers the skill
- **Cursor**: Uses the MCP endpoints documented in SKILL.md
- **Other MCP-compatible agents**: Access via the dsh plugin system

## Support

For issues with installation:

1. Check the [troubleshooting section](#troubleshooting)
2. Search [existing issues](https://github.com/Ikalus1988/MisakaNet/issues)
3. Open a new issue with your error logs
