# MisakaNet Search — VS Code Extension

Search the MisakaNet knowledge base without leaving VS Code.

## Features

- `Ctrl+Shift+M` (Cmd+Shift+M on Mac) to search
- Results show title, domain, score, and preview
- Click a result to open the full lesson file

## Setup

1. Clone MisakaNet: `git clone https://github.com/Ikalus1988/MisakaNet.git`
2. Install dependency: `cd MisakaNet && pip install misakanet-core`
3. Install this extension (or symlink into `~/.vscode/extensions/`)
4. Set `misakanet.repoPath` in VS Code settings if not auto-detected

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `misakanet.repoPath` | auto-detect | Path to MisakaNet repo |
| `misakanet.topResults` | 5 | Number of results |

## Part of MisakaNet Bounty #268
