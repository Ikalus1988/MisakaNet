# MisakaNet dsh Plugin Installation

## Quick Install

```bash
dsh plugin add misakanet
```

## Alternative Installation Methods

### Git Install

```bash
dsh plugin add github:Ikalus1988/MisakaNet
```

### Manual Install (Skill Discovery)

```bash
mkdir -p ~/.dsh/skills
cp -r skills/misakanet ~/.dsh/skills/
```

## Prerequisites

| Requirement | Minimum Version |
|-------------|----------------|
| dsh | 1.0.0 |
| Node.js | 18.0.0 |
| Git | 2.0 (for git method) |

## Step-by-Step Guide

### Method 1: npm Plugin Market (Recommended)

1. Open your terminal
2. Run the installation command:
   ```bash
   dsh plugin add misakanet
   ```
3. Wait for the download to complete
4. Verify the installation:
   ```bash
   dsh plugin list
   ```
   You should see `misakanet` in the output.

### Method 2: Git Repository

1. Ensure Git is installed on your system
2. Run the git installation command:
   ```bash
   dsh plugin add github:Ikalus1988/MisakaNet
   ```
3. The plugin will be automatically cloned and registered
4. Verify with `dsh plugin list`

### Method 3: Manual Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Ikalus1988/MisakaNet.git
   cd MisakaNet
   ```
2. Create the skills directory:
   ```bash
   mkdir -p ~/.dsh/skills
   ```
3. Copy the plugin:
   ```bash
   cp -r skills/misakanet ~/.dsh/skills/
   ```
4. Verify with `dsh plugin list`

## Verification

After installation, verify everything is working:

```bash
# Check plugin is listed
dsh plugin list

# Test MCP tools are accessible
dsh tool list | grep misakanet
```

## Troubleshooting

### Permission Denied

```bash
# Fix directory permissions
chmod -R 755 ~/.dsh/skills

# Or use sudo (not recommended for npm)
sudo dsh plugin add misakanet
```

### Plugin Not Found After Installation

1. Restart your terminal session
2. Check the plugin directory exists:
   ```bash
   ls -la ~/.dsh/skills/misakanet
   ```
3. Reinstall if needed:
   ```bash
   dsh plugin remove misakanet
   dsh plugin add misakanet
   ```

### Version Conflicts

```bash
# Update dsh to latest
npm update -g dsh

# Clear npm cache if needed
npm cache clean --force

# Reinstall plugin
dsh plugin remove misakanet
dsh plugin add misakanet
```

### Network Issues

```bash
# Check connectivity
ping github.com

# Try with verbose output
dsh plugin add misakanet --verbose

# Use git method as fallback
dsh plugin add github:Ikalus1988/MisakaNet
```

## Uninstallation

### Quick Uninstall

```bash
dsh plugin remove misakanet
```

### Manual Uninstall

```bash
rm -rf ~/.dsh/skills/misakanet
```

### Verify Removal

```bash
dsh plugin list
# misakanet should not appear
```

## Updating

```bash
# Update to latest version
dsh plugin update misakanet

# Or reinstall
dsh plugin remove misakanet
dsh plugin add misakanet
```

## Support

- [GitHub Issues](https://github.com/Ikalus1988/MisakaNet/issues)
- [Documentation](https://github.com/Ikalus1988/MisakaNet#readme)
