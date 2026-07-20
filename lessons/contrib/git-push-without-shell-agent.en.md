{
  "title": "Git Push in Constrained Agent Environments — The Right Way",
  "domain": "devops",
  "tags": ["git", "push", "agent", "sandbox", "ci-cd", "headless"],
  "status": "published",
  "source": "translated-contrib",
  "lang": "en",
  "translated_from": "git-push-without-shell-agent.md"
}

# Git Push in Constrained Agent Environments

## Problem

You're working in a restricted agent environment (CI runner, sandboxed container, Claude Code, Codex CLI) where:
- `git push` asks for a password but there's no TTY
- SSH agent forwarding isn't available
- The shell doesn't have direct access to your GitHub credentials

The push fails silently or hangs:
```
git push origin main
# Permission denied (publickey)
# OR
# Hangs indefinitely waiting for password input
```

## Root Cause

Restricted agent shells typically:
1. **Have no SSH agent running** — `ssh-agent` isn't started, so `git@github.com` connections fail
2. **Have no Git credential helper** — `gh auth status` shows "not logged in"
3. **Can't access macOS Keychain** — the sandbox can't reach `git-credential-osxkeychain`
4. **Have no TTY** — interactive password prompts hang forever with no visible prompt

## Fix

### Option A: SSH Key with GIT_SSH_COMMAND (recommended for CI)

```bash
# Set up an SSH key specifically for this session
mkdir -p ~/.ssh
echo "$SSH_PRIVATE_KEY" > ~/.ssh/id_ed25519
chmod 600 ~/.ssh/id_ed25519

# Use GIT_SSH_COMMAND to bypass all credential helpers
export GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no"

# Now push works
git push origin main
```

### Option B: GitHub Token in Remote URL

```bash
# Replace SSH remote with HTTPS + token
git remote set-url origin https://YOUR_TOKEN@github.com/user/repo.git
git push origin main

# Or pass token inline (doesn't modify remote config)
git push https://YOUR_TOKEN@github.com/user/repo.git main
```

### Option C: GitHub CLI (`gh`) with Token

```bash
# Authenticate without browser
echo "$GITHUB_TOKEN" | gh auth login --with-token

# Verify
gh auth status

# Push works through gh
git push origin main
```

### Option D: GitHub App Installation Token (enterprise)

```bash
# Generate installation token via API (one-time)
TOKEN=$(curl -s -X POST \
  -H "Authorization: Bearer $JWT" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/app/installations/$INSTALL_ID/access_tokens \
  | jq -r '.token')

git push https://x-access-token:$TOKEN@github.com/org/repo.git main
```

## Verification

```bash
# Test SSH access
ssh -T git@github.com 2>&1 | grep -q "successfully authenticated" && echo "SSH OK"

# Test token access
curl -s -H "Authorization: Bearer $TOKEN" https://api.github.com/user | jq .login

# Actual push
git push origin main && echo "Push succeeded"
```

## Key Takeaways

- `GIT_SSH_COMMAND` is the cleanest approach — it works even without `ssh-agent`
- Generate dedicated deploy keys, never reuse your personal SSH key
- HTTPS + token works even in the most restricted environments
- The `gh` CLI's `--with-token` flag is the quickest path when `gh` is already installed
- Always test authentication BEFORE attempting the push to avoid debugging two problems at once
