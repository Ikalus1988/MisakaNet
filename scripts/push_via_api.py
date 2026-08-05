#!/usr/bin/env python3
"""Push pending commits to GitHub via API (bypasses git TLS issues)."""
import subprocess, json, os, base64
from pathlib import Path

REPO = Path("/mnt/c/Users/hp/MisakaNet")
TOKEN = os.environ.get("GH_TOKEN", "")

def gh(*args):
    r = subprocess.run(["gh", "api"] + list(args),
                       capture_output=True, text=True,
                       env={**os.environ, "GH_TOKEN": TOKEN})
    if r.returncode != 0:
        print(f"gh error: {r.stderr[:200]}")
        return None
    return json.loads(r.stdout) if r.stdout else {}

owner, repo = "Ikalus1988", "MisakaNet"
branch = "main"
base = f"repos/{owner}/{repo}"

# 1. Get current HEAD SHA
ref = gh(f"{base}/git/refs/heads/{branch}")
if not ref:
    exit(1)
head_sha = ref["object"]["sha"]
print(f"Current HEAD: {head_sha}")

# 2. Get the local commits not yet pushed
result = subprocess.run(
    ["git", "log", "--oneline", f"origin/{branch}..HEAD", "--format=%H"],
    cwd=REPO, capture_output=True, text=True,
    env={**os.environ, "GH_TOKEN": TOKEN}
)
commits = [s.strip() for s in result.stdout.strip().split("\n") if s.strip()]
if not commits:
    print("No unpushed commits.")
    exit(0)

print(f"Unpushed commits: {len(commits)}")
for c in commits:
    print(f"  {c[:8]}")

# 3. Get the diff for each commit
for i, commit_sha in enumerate(commits):
    print(f"\nProcessing commit {i+1}/{len(commits)}: {commit_sha[:8]}")

    # Get commit info
    result = subprocess.run(
        ["git", "show", "--format=%H%n%an%n%ae%n%aI%n%B", "--no-patch", commit_sha],
        cwd=REPO, capture_output=True, text=True
    )
    lines = result.stdout.strip().split("\n", 4)
    if len(lines) < 5:
        continue
    _, author_name, author_email, author_date, commit_msg = lines

    # Get the tree from this commit
    result = subprocess.run(
        ["git", "show", "--format=%T", "--no-patch", commit_sha],
        cwd=REPO, capture_output=True, text=True
    )
    tree_sha = result.stdout.strip()

    # Get all files changed
    result = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "-r", "-t", "--name-status",
         "-M", commit_sha, "-p", commit_sha],
        cwd=REPO, capture_output=True, text=True
    )

    # Create the tree via API
    # First, get the base tree
    base_tree = gh(f"{base}/git/trees/{head_sha}")
    if not base_tree:
        continue

    # Get diff stats
    result = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "-r", "--name-status", commit_sha],
        cwd=REPO, capture_output=True, text=True
    )

    # For each changed file, create a blob
    tree_items = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        status = parts[0]
        filepath = parts[1] if len(parts) > 1 else ""

        if status == "D":
            tree_items.append({
                "path": filepath,
                "mode": "100644",
                "type": "blob",
                "sha": None
            })
            continue

        # Read file content
        file_path = REPO / filepath
        if file_path.exists():
            content = file_path.read_bytes()
            encoded = base64.b64encode(content).decode()

            # Create blob
            blob = gh(f"{base}/git/blobs", "-X", "POST",
                      "-f", f"content={encoded}",
                      "-f", "encoding=base64")
            if blob:
                tree_items.append({
                    "path": filepath,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob["sha"]
                })

    if not tree_items:
        # Empty commit - just copy parent tree
        new_tree_sha = head_sha
    else:
        # Create new tree
        tree_data = json.dumps({"tree": tree_items, "base_tree": head_sha})
        result = subprocess.run(
            ["gh", "api", f"{base}/git/trees", "-X", "POST",
             "--input", "-"],
            input=tree_data, capture_output=True, text=True,
            env={**os.environ, "GH_TOKEN": TOKEN}
        )
        if result.returncode != 0:
            print(f"  tree error: {result.stderr[:200]}")
            continue
        new_tree = json.loads(result.stdout)
        new_tree_sha = new_tree["sha"]

    # Create commit
    commit_data = json.dumps({
        "message": commit_msg,
        "author": {"name": author_name, "email": author_email, "date": author_date},
        "parents": [head_sha],
        "tree": new_tree_sha
    })
    result = subprocess.run(
        ["gh", "api", f"{base}/git/commits", "-X", "POST",
         "--input", "-"],
        input=commit_data, capture_output=True, text=True,
        env={**os.environ, "GH_TOKEN": TOKEN}
    )
    if result.returncode != 0:
        print(f"  commit error: {result.stderr[:200]}")
        continue
    new_commit = json.loads(result.stdout)
    new_commit_sha = new_commit["sha"]
    print(f"  Created commit: {new_commit_sha[:8]}")

    # Update ref
    ref_data = json.dumps({
        "sha": new_commit_sha,
        "force": False
    })
    result = subprocess.run(
        ["gh", "api", f"{base}/git/refs/heads/{branch}", "-X", "PATCH",
         "--input", "-"],
        input=ref_data, capture_output=True, text=True,
        env={**os.environ, "GH_TOKEN": TOKEN}
    )
    if result.returncode != 0:
        print(f"  ref update error: {result.stderr[:200]}")
        continue
    head_sha = new_commit_sha
    print(f"  Ref updated to {new_commit_sha[:8]}")

print(f"\nDone! Pushed {len(commits)} commits via API.")
