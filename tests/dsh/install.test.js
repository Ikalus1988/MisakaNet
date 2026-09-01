# MisakaNet dsh Plugin Installation Tests

## Quick Install (npm)

```bash
dsh plugin add misakanet
```

## Git Install

```bash
dsh plugin add github:Ikalus1988/MisakaNet
```

## Manual Install (Skill Discovery)

```bash
# Create the skills directory if it doesn't exist
mkdir -p ~/.dsh/skills

# Clone or copy the MisakaNet skill
cp -r skills/misakanet ~/.dsh/skills/
```

## Verification

After installation, verify the plugin is installed correctly:

```bash
dsh plugin list
```

You should see `misakanet` in the list of installed plugins.

## Prerequisites

- **dsh**: Version 1.0.0 or higher
- **Node.js**: Version 18.0.0 or higher (for npm installation method)
- **Git**: Required for git installation method

## Step-by-Step Instructions

### Method 1: npm Install (Recommended)

1. Ensure you have dsh installed and configured
2. Run the install command:
   ```bash
   dsh plugin add misakanet
   ```
3. Wait for the installation to complete
4. Verify with `dsh plugin list`

### Method 2: Git Install

1. Ensure you have Git installed
2. Run the install command:
   ```bash
   dsh plugin add github:Ikalus1988/MisakaNet
   ```
3. The plugin will be cloned and installed automatically
4. Verify with `dsh plugin list`

### Method 3: Manual Install

1. Clone the repository:
   ```bash
   git clone https://github.com/Ikalus1988/MisakaNet.git
   ```
2. Navigate to the skills directory:
   ```bash
   cd MisakaNet
   ```
3. Copy the skill to your dsh skills folder:
   ```bash
   mkdir -p ~/.dsh/skills
   cp -r skills/misakanet ~/.dsh/skills/
   ```
4. Verify with `dsh plugin list`

## Troubleshooting

### Permission Issues
If you encounter permission errors during installation:
```bash
# On Linux/macOS
sudo dsh plugin add misakanet

# Or fix permissions on the skills directory
chmod -R 755 ~/.dsh/skills
```

### Version Conflicts
If you experience version conflicts:
1. Check your current dsh version: `dsh --version`
2. Update dsh if needed: `npm update -g dsh`
3. Remove and reinstall the plugin:
   ```bash
   dsh plugin remove misakanet
   dsh plugin add misakanet
   ```

### Network Problems
If installation fails due to network issues:
1. Check your internet connection
2. Try using a different network
3. For npm, try clearing the cache:
   ```bash
   npm cache clean --force
   dsh plugin add misakanet
   ```

### Plugin Not Showing Up
If the plugin doesn't appear in `dsh plugin list`:
1. Restart your terminal
2. Check if the plugin files exist in `~/.dsh/skills/`
3. Reinstall the plugin

## Uninstall

To remove the MisakaNet plugin:

```bash
dsh plugin remove misakanet
```

To manually remove:
```bash
rm -rf ~/.dsh/skills/misakanet
```

## Additional Resources

- [MisakaNet GitHub Repository](https://github.com/Ikalus1988/MisakaNet)
- [dsh Documentation](https://dsh.dev/docs)
- [Plugin Development Guide](https://dsh.dev/docs/plugins)

## Support

If you encounter issues not covered in this guide:
1. Check the [GitHub Issues](https://github.com/Ikalus1988/MisakaNet/issues) page
2. Search for existing solutions
3. Create a new issue with detailed information about your problem

---

*This documentation was created for the MisakaNet dsh plugin installation bounty.*


// Signed-off-by: techlogiadg-spec <techlogiadg-spec@users.noreply.github.com>
