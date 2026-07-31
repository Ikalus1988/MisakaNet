# MisakaNet Shell Integration

## Install

```bash
# Add to ~/.bashrc or ~/.zshrc:
source /path/to/MisakaNet/integrations/shell/misaka.sh

# Or set custom repo path:
export MISAKA_REPO=/path/to/MisakaNet
source /path/to/MisakaNet/integrations/shell/misaka.sh
```

For a richer formatter (title, domain, score, snippet), load:

```bash
source /path/to/MisakaNet/scripts/misaka-search.sh
```

## Usage

```bash
misaka "pip timeout"              # Search lessons
misaka "docker M1" --top 3        # Top 3 results
misaka "git rebase" --json        # JSON output (pipe to jq)
misaka "kubernetes" --domain k8s  # Filter by domain
mk "database locked"               # Pretty-formatted results + snippets
```

## Aider Integration

```yaml
# .aider.conf.yml
read:
  - $(misaka "current error" --json --top 1 | jq -r '.[0].path // empty')
```

To query with the formatted helper:

```bash
mk "pip timeout"
```
