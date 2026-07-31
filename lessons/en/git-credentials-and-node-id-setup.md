---
{
  "title": "Git credentials and Node ID setup",
  "domain": "devops",
  "tags": ["git", "credentials", "node-id", "setup"],
  "status": "published",
  "lang": "en",
  "source": "wasim-builds",
  "translated_from": "lessons/contrib/git-credentials-and-node-id-setup.md",
  "created": "2026-07-31",
  "updated": "2026-07-31"
}
---

# Git credentials and Node ID setup

> English translation of `lessons/contrib/git-credentials-and-node-id-setup.md`

## Problem

When using git in a new environment without correctly configuring credentials and node identifier, you may encounter:

1. `git push` prompts for 401 Unauthorized or asks for username/password
2. Node cannot be correctly identified

## Git credentials setup

### Method 1: gh CLI authentication (recommended)

```bash
gh auth login
```

### Method 2: Manual credential helper configuration

```bash
git config --global credential.helper store
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### Method 3: Use PAT (Personal Access Token)

```bash
git remote set-url origin https://<USERNAME>:<PAT>@github.com/<org>/<repo>.git
```

## Node ID setup

In some distributed systems, each node needs a unique identifier:

```bash
# set node identifier
export NODE_ID="<node-name>"
```

And specify it in the project configuration file:

```json
{
  "node": {
    "id": "<node-name>",
    "name": "<display-name>"
  }
}
```

## Verification

```bash
# verify git configuration
git config --list | grep -E "user.(name|email)|credential"

# verify connection
git fetch --dry-run
```

## Notes

- Treat PAT as a password; do not commit it to the repository
- Different platforms use different credential helpers (Windows: manager, macOS: osxkeychain, Linux: libsecret)
- Once a Node ID is used, keep it unchanged to avoid confusion

## Related

- `git-credentials-and-node-id-setup` (Chinese original)
