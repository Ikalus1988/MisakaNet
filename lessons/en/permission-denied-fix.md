---
{
  "title": "Permission denied / WSL NTFS cross-filesystem fix",
  "domain": "devops",
  "tags": ["permission", "wsl", "ntfs", "eacces", "filesystem", "windows"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/permission-denied-fix.md",
  "created": "2026-08-02",
  "updated": "2026-08-02",
  "confidence": "0.9"
}
provenance:
  source: "external"
  contributor: "Unknown"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

# Permission denied / WSL NTFS cross-filesystem fix

## Problem

Operations under `~/.hermes/` fail with `Permission denied` or `EACCES`, or WSL access to `/mnt/c` fails with `crossmnt` errors. Common scenarios:
- `git clone` into `/mnt/c/...` aborts with `Permission denied`.
- `touch ~/.hermes/test` returns `Permission denied` even though you own the directory.
- Python scripts cannot write logs under `/mnt/c/Users/...`.

## Root Cause

- `/mnt/c` (NTFS partition) lacks execute permissions inside WSL by default.
- `~/.hermes/` files or directories were created by `root`, so the normal user cannot write to them.
- WSL cross-filesystem permission checks are inconsistent across distros and Windows builds.
- Windows Defender Controlled Folder Access can block writes from WSL.

## Solution

### WSL NTFS crossmnt

```bash
sudo bash -c 'cat >> /etc/wsl.conf <<EOF
[automount]
enabled = true
options = "metadata,umask=22"
EOF'
# Then restart WSL: wsl --shutdown
```

### Normal permission issues

```bash
# Change ownership
sudo chown -R $(id -u):$(id -g) ~/.hermes/

# Or add write permission
chmod -R u+w ~/.hermes/

# Single file
chmod u+w ~/.hermes/some_file
```

### Inspect current permissions

```bash
id
ls -la ~/.hermes/
stat ~/.hermes/some_file
getfacl ~/.hermes/some_file
```

## Verification

```bash
touch ~/.hermes/test_write_perm && rm ~/.hermes/test_write_perm && echo "Write OK"
```

Also verify cross-filesystem access:

```bash
touch /mnt/c/tmp_test && rm /mnt/c/tmp_test && echo "NTFS write OK"
```

## Related

- Windows Defender real-time protection can also affect NTFS performance; add exclusions if needed.
- WSL2 defaults to NTFS; WSL1 uses `drvfs` with different behavior.
- See [WSL file system limitations](https://docs.microsoft.com/en-us/windows/wsl/compare-versions) for the full compatibility matrix.
