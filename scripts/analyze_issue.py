import subprocess, json, sys

# Fetch repo structure and PR #2816
repos = subprocess.run(
    ["curl", "-s", "https://api.github.com/repos/Ikalus1988/MisakaNet"],
    capture_output=True, text=True
)
print("Repo:", repos.stdout[:500])

# Get PR #2816 files
pr = subprocess.run(
    ["curl", "-s", "https://api.github.com/repos/Ikalus1988/MisakaNet/pulls/2816"],
    capture_output=True, text=True
)
pr_data = json.loads(pr.stdout)
print("PR title:", pr_data.get("title"))
print("PR body:", pr_data.get("body", "")[:2000])

# Get files changed in PR
files = subprocess.run(
    ["curl", "-s", "https://api.github.com/repos/Ikalus1988/MisakaNet/pulls/2816/files"],
    capture_output=True, text=True
)
file_data = json.loads(files.stdout)
for f in file_data:
    print(f"File: {f['filename']}")
    print(f"  patch:\n{f.get('patch','')[:3000]}")
    print("---")

# Search for truncation logic in the repo
tree = subprocess.run(
    ["curl", "-s", "https://api.github.com/repos/Ikalus1988/MisakaNet/git/trees/main?recursive=1"],
    capture_output=True, text=True
)
tree_data = json.loads(tree.stdout)
for item in tree_data.get("tree", []):
    if any(x in item["path"] for x in ["intake", "text", "cap", "trunc"]):
        print("MATCH:", item["path"])
