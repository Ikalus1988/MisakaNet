#!/usr/bin/env python3
"""Create Issue for content translation using a PAT from the environment."""
import subprocess, json, os

# Security: token must come from the environment, never be hardcoded.
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")

data = {
    "title": "refactor: translate remaining Chinese lesson content to English",
    "body": "## Background\n\nAll lesson filenames have been converted to English. However, ~136 lesson files in `lessons/contrib/` still contain Chinese content.\n\n## Priority\n\nP0: RAG (~10), Feishu (~8), WSL/DevOps (~6)\nP1: GPT-SoVITS/TTS (~5), FANUC KL (~4), OpenClaw (~3)\nP2: remaining\n\n## Principles\n1. Code/commands/paths: DO NOT translate\n2. Frontmatter title/description: must be English\n3. Maintain Problem → Root Cause → Solution → Verification structure\n\n## Definition of Done\n- [ ] All contrib/*.md files have English body content\n- [ ] Frontmatter JSON is valid\n- [ ] Index updated\n",
    "labels": ["enhancement"]
}

cmd = ["curl", "-s", "-X", "POST",
       "https://api.github.com/repos/Ikalus1988/MisakaNet/issues",
       "-H", f"Authorization: Bearer {TOKEN}",
       "-H", "Content-Type: application/json",
       "-d", json.dumps(data)]

result = subprocess.run(cmd, capture_output=True, text=True)
resp = json.loads(result.stdout)
if "html_url" in resp:
    print(f"✅ Issue created: {resp['html_url']}")
else:
    print(f"❌ Failed: {resp.get('message', result.stdout[:200])}")
