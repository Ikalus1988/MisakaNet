# DCO Commit Sign-off Quickstart for Windows Contributors

This guide helps Windows contributors resolve **Developer Certificate of Origin (DCO)** failures on their pull requests.

## ❓ What is the DCO failure?

MisakaNet enforces the Developer Certificate of Origin (DCO) to ensure all code contributions are legally authorized. Every commit in your Pull Request must contain a `Signed-off-by:` line at the bottom of the commit message matching the git commit author's name and email.

If your PR shows a failed DCO check, it is usually because you didn't commit with the `--signoff` (or `-s`) flag.

---

## 🚀 Copy-Paste Fix Commands for Windows

To fix existing commits that failed the DCO check, open your terminal (Git Bash, Command Prompt, or PowerShell) in your repository directory and run the following commands:

### 1. For the most recent commit

If you only need to sign off your **latest** commit:

```bash
# Add the sign-off trailer to the last commit
git commit --amend --signoff --no-edit

# Force-push to update your Pull Request
git push --force-with-lease
```

### 2. For multiple commits

If you need to sign off **multiple** commits in your branch, you can perform an interactive rebase:

```bash
# Start an interactive rebase for the last N commits (replace N with your number of commits)
git rebase -i HEAD~N
```

In the editor that opens:
1. Change `pick` to `edit` (or `e`) for all the commits you need to sign off.
2. Save and exit the editor.
3. For each commit, Git will pause. Run the following:
   ```bash
   git commit --amend --signoff --no-edit
   git rebase --continue
   ```
4. Once completed, force push:
   ```bash
   git push --force-with-lease
   ```

---

## 🛠️ Configure Git on Windows to Auto-Sign (Optional)

You can configure Git on Windows to automatically sign off or template your commit messages:

### Set up Git Identity
Ensure your name and email are configured correctly (this email must match the one in your `Signed-off-by:` line):

```bash
git config --global user.name "Your Real Name"
git config --global user.email "your.email@example.com"
```

### Always Use the `-s` Flag
Remember to append `-s` whenever you make a commit:
```bash
git commit -s -m "docs: add Windows DCO quickstart"
```
