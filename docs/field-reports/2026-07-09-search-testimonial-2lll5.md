# Bounty #254 — Real Error MisakaNet Search Testimonial

## Real error

While preparing this bounty run in a fresh scheduled environment, I tried to check GitHub CLI authentication and hit this real shell error:

```text
/usr/bin/bash: line 3: gh: command not found
```

## Search command

```bash
python3 search_knowledge.py "/usr/bin/bash: line 3: gh: command not found"
```

## Search output excerpt

```text
📋 lessons/  (All 199 items) (175 matches, showing top 10)
------------------------------------------------------------
  [contrib]  [contrib]      gh credential helper 路径Error导致 git push 静默失败
                             ███████░░░ 73%  just now
                            (matched: content)
                            📄 lessons/git-credential-helper-gh-path-mismatch.md
                            ---{"title": "33mgh credential helper 路径Error导致 git push 静默失败", "domain": "devops", "tags": ["git", "github", "credential",...

  [contrib] [verified] [contrib] MisakaNet --heal UX Gap — Suggested queue_lesson.py Command Uses Wrong Flag
                             ███████░░░ 65%  just now
                            (matched: title)
                            📄 lessons/misakanet-heal-ux-gap-queue-lesson-flag-mismatch.md
                            ---{"title": "MisakaNet --heal UX Gap — From Traceback to Covered Lesson", "domain": "development", "...

  [core] [verified] [devops] DCO Auto-Fix Workflow — /fix-dco Command Design & Implementation (published)
                             ██████░░░░ 57%  just now
                            (matched: title)
                            📄 lessons/dco-auto-fix-workflow.md
                            贡献者提交 PR 后 DCO（Signed-off-by）检查失败是最常见的阻塞原因之一。

📋 reference/  (All 6 items) (2 matches, showing top 2)
------------------------------------------------------------
  [contrib]  [devops]       微信机器人方案迭代轨迹 —— wxauto 安装 + 版本兼容 (reference)
                             ███████░░░ 73%  just now
                            (matched: content)
                            📄 reference/wechat-bot-iteration-trajectory.md
```

Full command output was also saved locally during verification at `/tmp/misakanet-254-search.txt`.

## Lesson used

The top result, `lessons/contrib/git-credential-helper-gh-path-mismatch.md`, was relevant because it explained how GitHub CLI and Git credential-helper assumptions can break when `gh` is absent or installed at a different path. For this run, the immediate fix was to stop assuming the GitHub CLI was available and use the already configured GitHub API token plus git credential flow directly. The lesson also gave a useful verification pattern: inspect credential helpers and verify remotes with git/API calls before attempting a push.

## Three-sentence testimonial

MisakaNet helped me turn a live `/usr/bin/bash: line 3: gh: command not found` failure into an actionable path instead of treating the missing CLI as a blocker. The top lesson about `gh` credential-helper path mismatches was close enough to remind me to verify the actual authentication path and use token-backed Git/API operations directly. This saved time during the bounty workflow because I could continue with fork, branch, commit, push, and PR steps without installing or depending on the GitHub CLI.

## Verification

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install misakanet-core
python3 search_knowledge.py "/usr/bin/bash: line 3: gh: command not found"
git diff --check
```
