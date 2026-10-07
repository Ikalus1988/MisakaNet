import subprocess, json, sys

def curl(url):
    import urllib.request
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

# Get PR #2816 files
files = curl("https://api.github.com/repos/Ikalus1988/MisakaNet/pulls/2816/files")
for f in files:
    print(f"FILE: {f['filename']}")
    patch = f.get("patch","")
    if patch:
        print(patch)
    print("="*80)

# Search repo for text cap / truncation references
import urllib.request
tree = curl("https://api.github.com/repos/Ikalus1988/MisakaNet/git/trees/main?recursive=1")
all_paths = [t["path"] for t in tree["tree"]]

# Find files mentioning 2000 or text cap
for p in all_paths:
    low = p.lower()
    if any(k in low for k in ["intake","text_cap","text-cap","truncat","sidebar"]):
        print("PATH:", p)

# Search for the constant 2000 in source files
print("\nSearching for '2000' and 'MAX_INTAKE' etc...")
for p in all_paths:
    low = p.lower()
    if low.endswith((".ts",".js",".py",".go",".rs",".cs",".java",".kt")):
        if any(k in low for k in ["intake","text","cap","trunc","sidebar","fragment"]):
            print("  SRC:", p)
