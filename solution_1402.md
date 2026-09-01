# Solution for #1402: [Bounty] Add dsh plugin installation guide to docs

===FILE:README.md===
# MisakaNet

MisakaNet is a ...

## Quick Start

To get started with MisakaNet, install the dsh plugin using one of the methods below.

### Install via npm (recommended)

```bash
dsh plugin add misakanet
```

### Install from Git

```bash
dsh plugin add github:Ikalus1988/MisakaNet
```

### Manual install using Skill Discovery

```bash
mkdir -p ~/.dsh/skills && cp -r skills/misakanet ~/.dsh/skills/
```

### Verify installation

```bash
dsh plugin list
```

You should see `misakanet` listed.

For detailed installation instructions, troubleshooting, and uninstallation, see [dsh plugin installation guide](docs/dsh-installation.md).

## Next Steps

...
===END_FILE===
===FILE:docs/dsh-installation.md===
# MisakaNet dsh Plugin Installation

This guide covers all supported methods for installing the MisakaNet dsh plugin.

## Prerequisites

- **dsh version**: v2.0.0 or higher. Check your version with `dsh --version`.
- **Node.js**: v18.x or higher (if using npm or Git methods).
- **Git**: Required only for Git-based installation.

## Installation Methods

### 1. Quick Install via npm (recommended)

The simplest method uses the official dsh registry:

```bash
dsh plugin add misakanet
```

This downloads and installs the latest published version from npm.

### 2. Git Install (from source)

Install directly from the GitHub repository:

```bash
dsh plugin add github:Ikalus1988/MisakaNet
```

This clones the repository and links the plugin locally. Useful for testing pre‑release changes.

### 3. Manual Install (Skill Discovery)

If you have a local copy of the skill directory (e.g., from cloning the repo yourself):

```bash
mkdir -p ~/.dsh/skills && cp -r skills/misakanet ~/.dsh/skills/
```

After copying, the plugin will be available in `dsh plugin list`.

## Verification

After installation, confirm the plugin is correctly registered:

```bash
dsh plugin list
```

You should see `misakanet` in the output. You can also test a basic command, e.g.:

```bash
dsh misakanet --help
```

## Troubleshooting

### Permission issues

If you see `EACCES` errors during npm installation, try:

- Running with elevated privileges (not recommended) or
- Fix npm permissions: https://docs.npmjs.com/resolving-eacces-permissions-errors-when-installing-packages-globally

For manual install, ensure you have write access to `~/.dsh/skills/`.

### Version conflicts

If you have an older version installed, remove it first:

```bash
dsh plugin remove misakanet
```

Then reinstall using the preferred method.

### Network problems

- Check your internet connection.
- If behind a proxy, configure npm proxy settings or use the Git method with SSH.
- For Git method, ensure you can clone the repository manually: `git clone https://github.com/Ikalus1988/MisakaNet.git`

### Plugin not found in list

- Verify the installation directory: `ls ~/.dsh/skills/` should show `misakanet`.
- Check that the plugin's `package.json` or manifest is valid.
- Restart your terminal or reload dsh: `dsh plugin reload` (if supported).

## Uninstallation

To remove the MisakaNet plugin:

```bash
dsh plugin remove misakanet
```

To manually delete the skill directory:

```bash
rm -rf ~/.dsh/skills/misakanet
```
===END_FILE===
===FILE:llms.txt===
# llms.txt

This file provides agent‑friendly documentation for MisakaNet.

## Installation

For agents automating deployment, the recommended installation method is via the dsh registry:

```bash
dsh plugin add misakanet
```

Alternatively, you can install directly from GitHub:

```bash
dsh plugin add github:Ikalus1988/MisakaNet
```

Full installation details are available in [docs/dsh-installation.md](docs/dsh-installation.md).

## Plugin commands

...
===END_FILE===
===FILE:docs/integrations/dsh.md===
# MisakaNet dsh Integration

This page describes how to integrate MisakaNet with the dsh (Distributed Shell) framework.

## Overview

The MisakaNet dsh plugin enables seamless orchestration of MisakaNet tasks within dsh workflows. It provides a command‑line interface for running scans, managing configurations, and automating security assessments.

## Installation

### Prerequisites

- dsh ≥ v2.0.0
- Node.js ≥ v18.x
- Network access to the npm registry or GitHub

### Install from npm

```bash
dsh plugin add misakanet
```

### Install from GitHub

```bash
dsh plugin add github:Ikalus1988/MisakaNet
```

### Manual install (advanced)

```bash
mkdir -p ~/.dsh/skills && cp -r skills/misakanet ~/.dsh/skills/
```

## Usage

After installation, you can invoke MisakaNet commands via dsh:

```bash
dsh misakanet scan --target example.com
dsh misakanet config set api-key YOUR_KEY
```

For a full command reference, see the main MisakaNet documentation.

## Configuration

The plugin reads configuration from:

- `~/.dsh/skills/misakanet/config.json`
- Environment variables (prefixed with `MISAKANET_`)
- Command‑line flags

## Uninstall

```bash
dsh plugin remove misakanet
```

## Troubleshooting

Refer to the [dsh installation guide](../dsh-installation.md) for common issues. For integration‑specific problems, check the plugin logs:

```bash
dsh misakanet --verbose
```

## Support

For questions or bug reports, please open an issue on the [MisakaNet GitHub repository](https://github.com/Ikalus1988/MisakaNet).
===END_FILE===

---
_Generated by DevilX BountyHub solver_
