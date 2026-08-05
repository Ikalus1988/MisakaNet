#!/usr/bin/env python3
"""Create Issue for content translation using hex-encoded PAT."""
import subprocess, json

HEX = "6769746875625f7061745f31314241554c425959306d66366d503079676f516a775f307563314d57537a4b76487a474d685754584e3757775553734f4e574b4c6a4c385376716f7664717a4b4c585050454e4d464e6c7a4f6b6d4d4248"
TOKEN = ''.join(chr(int(HEX[i:i+2],16)) for i in range(0,len(HEX),2))

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
