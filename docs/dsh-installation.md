# MisakaNet dsh Plugin Installation

This guide explains how to install the MisakaNet plugin for the dsh environment.

## Prerequisites
- **Node.js**: v18.x or later
- **dsh**: v1.x or later

## Quick Install (npm)
The fastest and recommended way to install the plugin via the dsh market:
ash
dsh plugin add misakanet
``n
## Git Install
Install directly from the latest source on GitHub:
ash
dsh plugin add github:Ikalus1988/MisakaNet
``n
## Manual Install (Skill Discovery)
If you prefer managing skills manually or modifying the plugin code locally:
ash
mkdir -p ~/.dsh/skills && cp -r skills/misakanet ~/.dsh/skills/
``n
## Verification
To verify the installation succeeded, list your installed plugins:
ash
dsh plugin list
``nThe output should include misakanet.

## Troubleshooting
- **Permission issues**: Ensure your ~/.dsh/ folder is owned by your user.
- **Version conflicts**: Check that your dsh core version meets the prerequisite.
- **Network problems**: If the npm or git install hangs, verify your network connection.

## Uninstall
To cleanly remove the plugin:
ash
dsh plugin remove misakanet
``n