# MisakaNet Shell Integration

## Install

```bash
# Add to ~/.bashrc or ~/.zshrc:
source /path/to/MisakaNet/integrations/shell/misaka.sh

# Or set custom repo path:
export MISAKA_REPO=/path/to/MisakaNet
source /path/to/MisakaNet/integrations/shell/misaka.sh
```

## Auto-Search Hook

Automatically suggest MisakaNet lessons when commands fail:

```bash
# Add to ~/.bashrc or ~/.zshrc:
source /path/to/MisakaNet/integrations/shell/misaka-hook.sh
export MISAKA_AUTO_SEARCH=1
```

When a command fails, the hook:
1. Captures the failed command
2. Searches MisakaNet in the background
3. Shows matching lessons at the next prompt

```bash
$ pip install nonexistent-package
ERROR: Could not find a version that satisfies the requirement...

💡 MisakaNet found matching lessons:
  1. pip install timeout — proxy configuration
  2. pip dependency resolution — version conflicts
  Run 'misaka "pip install nonexistent-package"' for full results
```

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MISAKA_AUTO_SEARCH` | `0` | Enable auto-search (`1` to activate) |
| `MISAKA_REPO` | `~/MisakaNet` | Path to MisakaNet repo |
| `MISAKA_HOOK_MAX_LINES` | `3` | Max lessons to show |

### Commands

```bash
misaka-hook-enable    # Enable auto-search
misaka-hook-disable   # Disable auto-search
misaka-hook-help      # Show help
```

## Usage

```bash
misaka "pip timeout"              # Search lessons
misaka "docker M1" --top 3        # Top 3 results
misaka "git rebase" --json        # JSON output (pipe to jq)
misaka "kubernetes" --domain k8s  # Filter by domain
```

## Aider Integration

```yaml
# .aider.conf.yml
read:
  - $(misaka "current error" --json --top 1 | jq -r '.[0].path // empty')
```
