import subprocess, json, sys, os

def run(cmd, **kwargs):
    r = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    return r.stdout, r.stderr, r.returncode

# 1. Get PR #2816 details
out, err, code = run(["curl", "-s", "https://api.github.com/repos/Ikalus1988/MisakaNet/pulls/2816"])
if code != 0:
    print("ERR fetching PR:", err)
    sys.exit(1)
pr = json.loads(out)
print(f"PR Title: {pr.get('title')}")
print(f"PR State: {pr.get('state')}")
print(f"PR Merged: {pr.get('merged')}")
body = pr.get("body","")
print(f"PR Body (first 3000):\n{body[:3000]}")
print("="*60)

# 2. Get files changed in PR #2816
out, err, code = run(["curl", "-s", "https://api.github.com/repos/Ikalus1988/MisakaNet/pulls/2816/files"])
files = json.loads(out)
print(f"Files changed in #2816: {len(files)}")
for f in files:
    print(f"\n--- {f['filename']} ---")
    patch = f.get("patch","")
    if patch:
        print(patch[:4000])
    else:
        print("(no patch shown)")
print("="*60)

# 3. Get repo tree for search
out, err, code = run(["curl", "-s", "https://api.github.com/repos/Ikalus1988/MisakaNet/git/trees/main?recursive=1"])
tree = json.loads(out)
paths = [t["path"] for t in tree.get("tree",[])]
print(f"Total paths: {len(paths)}")

# Search for truncation-related files
matches = [p for p in paths if any(k in p.lower() for k in ["intake","trunc","cap","sidebar","fragment"])]
print("Relevant paths:", matches)

# Also search for 2000 or text cap constants
for p in paths:
    if p.endswith(".ts") or p.endswith(".js") or p.endswith(".py") or p.endswith(".go") or p.endswith(".rs"):
        if any(k in p.lower() for k in ["intake","text","cap","trunc"]):
            print("CODE FILE:", p)
