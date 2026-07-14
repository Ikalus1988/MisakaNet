---
title: "FANUC Backup Payload Extraction — .VR/.SV Binary Parsing and .LS Text Fallback"
domain: "fanuc"
subdomain: "backup-analysis"
tags: ["backup", "payload", "vr-file", "sv-file", "kconvars", "sysvars", "cbparam", "plst-grp", "binary-parsing", "spottool"]
source: "internal"
status: "published"
confidence: "0.85"
created: "2026-07-14"
verified_date: "2026-07-14"
domain_expert: ""
---


## Problem

Given a FANUC robot backup directory, extract the payload (load mass, center of gravity, inertia) configuration. The backup contains 300+ files in proprietary binary formats (`.vr`, `.sv`) that cannot be read with standard text editors. The official conversion tool `kconvars.exe` may crash due to missing `robot.ini` or path encoding issues.

Two distinct payload storage mechanisms exist depending on the application software:

1. **Standard system**: `$PLST_GRP1[1..10]` in `SYSVARS.SV` — stores up to 10 payload sets with mass, COG (X/Y/Z), and inertia (IX/IY/IZ) per set.
2. **MH gripper wizard**: `PAYLOAD1`/`PAYLOAD2` in `CBPARAM.VR` — used by SpotTool+ and Material Handling applications.

## Root Cause

FANUC `.vr` and `.sv` files use a proprietary binary encoding (magic header `FE EF` for `.vr`, `*SYSTEM*` header for `.sv`). Numeric values are NOT standard IEEE 754 — FANUC uses a variable-length encoded format with interleaved type markers. This means:

- Python `struct.unpack('>f', ...)` produces garbage for most values
- ASCII strings are embedded between `0xFF` markers
- The `kconvars.exe` tool (from WinOLPC) is the only reliable decoder, but it requires `robot.ini` and crashes with non-ASCII paths

The payload data structure varies by application:

| Application | Payload Source | Variables |
|---|---|---|
| General / Handling | `$PLST_GRP1[1..10]` in SYSVARS.SV | Mass, COG, Inertia per set |
| SpotTool+ / MH Gripper | `CBPARAM.VR` | PAYLOAD1, PAYLOAD2 |
| All | `ERRCURR.LS` (text) | Single PAYLOAD value |

## Solution

### Step 1: Quick Win — Extract from .LS Files (No Tools Needed)

The `.ls` files are plain text and contain the most critical payload data:

```bash
# Find the current payload value
grep -i "PAYLOAD" <backup_dir>/ERRCURR.LS

# Expected output:
# PAYLOAD          : 280
```

Also extract robot model, firmware version, and feature list:

```bash
grep -E "ROBOT:|VERSION:|FEATURE\[125\]" <backup_dir>/ERRCURR.LS

# Expected output:
# ROBOT: M-900iB/280L
# $VERSION: V9.40236     11/21/2022
# $FEATURE[125]: M-900iB/280L
```

### Step 2: kconvars Conversion

**Critical**: `kconvars.exe` crashes with segfault (exit 139) when called from Git Bash / MSYS2 shell. Use PowerShell's `System.Diagnostics.Process` object instead.

```powershell
# Copy to ASCII-only path (kconvars fails with non-ASCII paths)
$workdir = "$env:TEMP\fanuc_conv"
New-Item -ItemType Directory -Path $workdir -Force
Copy-Item "<backup_dir>\SYSVARS.SV" "$workdir\sysvars.sv"

# Convert via PowerShell Process (avoids bash segfault)
$kconvars = "C:\Program Files (x86)\FANUC\WinOLPC\bin\kconvars.exe"
$pinfo = New-Object System.Diagnostics.ProcessStartInfo
$pinfo.FileName = $kconvars
$pinfo.Arguments = "$workdir\sysvars.sv $workdir\sysvars_out.txt"
$pinfo.WorkingDirectory = $workdir
$pinfo.UseShellExecute = $false
$pinfo.RedirectStandardOutput = $true
$pinfo.RedirectStandardError = $true
$pinfo.CreateNoWindow = $true

$p = New-Object System.Diagnostics.Process
$p.StartInfo = $pinfo
$p.Start() | Out-Null
$p.WaitForExit(10000)

# Extract payload data
Select-String -Path "$workdir\sysvars_out.txt" -Pattern "PAYLOAD"
```

Expected output for a robot with `$PLST_GRP1` configured:

```
Field: $GROUP[1].$PAYLOAD Access: RW: REAL = 1.480000e+02
Field: $PLST_GRP1[1].$PAYLOAD Access: RO: REAL = 3.300000e+02
Field: $PLST_GRP1[1].$PAYLOAD_X Access: RO: REAL = 0.000000e+00
Field: $PLST_GRP1[1].$PAYLOAD_Y Access: RO: REAL = 0.000000e+00
Field: $PLST_GRP1[1].$PAYLOAD_Z Access: RO: REAL = 0.000000e+00
Field: $PLST_GRP1[1].$PAYLOAD_IX Access: RO: REAL = 0.000000e+00
Field: $PLST_GRP1[1].$PAYLOAD_IY Access: RO: REAL = 0.000000e+00
Field: $PLST_GRP1[1].$PAYLOAD_IZ Access: RO: REAL = 0.000000e+00
```

**Common failure**: `kconvars.exe` crashes with segfault (exit code 139) when:
- `robot.ini` is not found in the same directory
- The path contains non-ASCII characters (Chinese, spaces)
- The installed WinOLPC version doesn't match the backup firmware version

Use `/ver V9.40-1` flag to specify the version explicitly.

### Step 3: Binary String Extraction (Fallback)

When kconvars is unavailable, extract ASCII strings from `.vr` files:

```python
import struct

def extract_fanuc_vr(filepath):
    """Extract readable data from FANUC .vr binary file."""
    with open(filepath, 'rb') as f:
        data = f.read()

    print(f"Magic: {data[0:2].hex().upper()}")  # Should be FEEF

    # Extract ASCII strings (>= 3 chars)
    strings = []
    cur = []
    for i, b in enumerate(data):
        if 32 <= b < 127:
            cur.append((i, chr(b)))
        else:
            if len(cur) >= 3:
                s = ''.join(c for _, c in cur)
                strings.append((cur[0][0], s))
            cur = []

    for offset, s in strings:
        print(f"  0x{offset:04x}: '{s}'")

    return strings

# Key files to parse:
# CBPARAM.VR — contains PAYLOAD1, E_CTRLMODE, DATA_C1
# MHGRIPDT.VR — contains CLAMP_TAB, VACUUM, TOOL, VALVE
# posreg.vr — position registers
# numreg.vr — numeric registers
extract_fanuc_vr('<backup_dir>/CBPARAM.VR')
```

### Step 4: Identify Payload Storage Mechanism

```bash
# Check which payload system this robot uses
python -c "
import os
backup = '<backup_dir>'
for fname in os.listdir(backup):
    fpath = os.path.join(backup, fname)
    if os.path.isfile(fpath):
        with open(fpath, 'rb') as f:
            data = f.read()
        for pat in [b'PLST', b'PLID', b'PAYLOAD', b'PAYLD', b'CBPARAM']:
            if pat in data:
                print(f'{fname}: contains {pat.decode()}')
"
```

- If `PLST` found → standard `$PLST_GRP1[1..10]` system (use kconvars)
- If only `PAYLOAD` in `.LS` + `CBPARAM.VR` → MH gripper wizard system
- If neither → check `ERRCURR.LS` for the single PAYLOAD value

## Verification

1. **Confirm .LS readability**:
   ```bash
   head -5 <backup_dir>/ERRCURR.LS
   # Should show robot name and date
   ```

2. **Confirm payload extraction**:
   ```bash
   grep "PAYLOAD" <backup_dir>/ERRCURR.LS
   # Should show: PAYLOAD : <value>
   ```

3. **Confirm kconvars output** (if available):
   ```bash
   grep "PAYLOAD" /tmp/fanuc_conv/sysvars_out.txt | head -20
   # Should show $GROUP[1].$PAYLOAD and/or $PLST_GRP1[N].$PAYLOAD
   ```

4. **Cross-validate**: The `$GROUP[1].$PAYLOAD` value from kconvars should match the `PAYLOAD` value in `ERRCURR.LS`.

## Notes

- **$PLST_GRP1[1..10] structure**: Each index stores mass (REAL, kg), COG X/Y/Z (REAL, mm), and inertia IX/IY/IZ (REAL, kg·mm²). Indices with all zeros are unused slots.
- **$PLID_GRP vs $PLST_GRP**: `$PLID_GRP` stores the payload identification data (calculated from tool definition), while `$PLST_GRP1` stores the payload set configuration. Both may coexist.
- **FANUC VR format**: Magic header `FE EF`, followed by version (2 bytes), uncompressed size (4 bytes), then `FF 41` marks the data section. Variable names are preceded by `FF` markers.
- **kconvars versions**: The tool supports V6.40 through V9.40. Use `/ver` to match the backup firmware version. Mismatched versions may produce incorrect output or crash.
- **kconvars bash segfault (exit 139)**: `kconvars.exe` crashes when invoked from Git Bash / MSYS2 shell due to DLL loading conflicts. The workaround is to use PowerShell's `System.Diagnostics.Process` object, which handles Windows process creation correctly. This has been verified on Windows 11 with WinOLPC V9.40-1.
- **No open-source parser exists**: As of 2026, no mature open-source tool can fully decode FANUC `.vr` binary format. The proprietary encoding includes variable-length integers, type markers, and non-IEEE-754 floats.
- **Related files by priority**: `ERRCURR.LS` (text, instant) > `SYSVARS.SV` (binary, needs kconvars) > `CBPARAM.VR` (binary, gripper-specific) > `ERRHIST.LS` (text, historical).
