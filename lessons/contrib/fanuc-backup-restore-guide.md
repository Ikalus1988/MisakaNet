---
title: "FANUC Robot Backup and Restore — Full, Mirror, Auto, and File Restore"
domain: "fanuc"
subdomain: "maintenance"
tags: ["backup", "restore", "mirror", "image", "auto-backup", "file-restore", "usb", "maintenance"]
status: "published"
source: "internal-training"
confidence: "0.9"
created: "2026-07-14"
---

## Problem

FANUC robot controllers support multiple backup types (full backup, mirror/image backup, auto backup) with different contents, restore procedures, and use cases. Engineers often confuse them or use the wrong type for their situation.

## Solution

### Backup Type Comparison

| Item | Full Backup | Mirror/Image Backup |
|------|-------------|---------------------|
| System software | Not included | Included |
| User data | Included | Included |
| Restore method | Data restore | Full system restore |
| File size | Smaller | Larger |
| Use case | Daily data backup | System-level backup/migration |

### Full Backup (All of Above)

Contains: TP/LS program files, system files, IO config, vision files, KAREL files. Does NOT include system software.

```
MENU → File → Backup → "All of above" → Select storage (USB/PC) → Execute
```

### Mirror/Image Backup

Contains: complete system image (system software + all user data + config). Can restore to the exact state at backup time.

```
MENU → File → Backup → "Image Backup" → Select storage → Execute (takes longer)
```

### Auto Backup

Scheduled automatic backup without manual intervention.

```
MENU → File → Auto Backup → Enable
```

Configuration options:
- **Period**: Daily / Weekly / Monthly
- **Time**: Specific backup time
- **Type**: Full / Incremental
- **Storage**: USB / CF card / Network

### Restore Procedures

**Full backup restore:**
```
MENU → File → Restore → Select backup file → Execute
```

**Mirror/image restore:**
```
1. Power on → Enter BOOT mode
2. Select "Controlled Start"
3. Select "Restore Image"
4. Select image file
5. Execute (system will restart)
```

**Partial file restore:**
```
MENU → File → Restore → Select source (USB/CF/Network) → Select specific files → Execute
```

### Remote Image Import

For batch deployment across multiple robots via network:

```
MENU → File → Image Import → Select network import → Enter image server address
```

Supports FTP, HTTP, and custom KAREL-based protocols.

### ASCII Program Import/Export

ASCII format (.LS) programs can be edited with text editors and version-controlled:

```
Export: MENU → File → Export → Select program → ASCII format → Select storage
Import: MENU → File → Import → Select file → Overwrite/Append → Confirm
```

Note: ASCII programs must be compiled after import.

### Cross-Version File Transfer

When transferring files between different system versions:
- High→Low version may be incompatible
- Specific option files may not transfer
- System files may need reconfiguration
- Always backup target system before import

### Investigation Data Collection

Types of data available for diagnostics:
- **System info**: Software version, hardware config (MENU → Status → System)
- **Alarm history**: Alarm records, codes (MENU → Status → Alarm)
- **Runtime data**: Operating hours, cycle counts (MENU → Status → Runtime)
- **IO status**: Signal states (MENU → Status → IO)

Export methods: USB, FTP to PC, or KAREL automated collection.

## Verification

1. Create a full backup to USB and verify file count
2. Create a mirror backup and verify file size is significantly larger
3. Restore a single program file from backup without affecting others
4. Configure auto backup and verify it runs at scheduled time

## Notes

- Always verify storage device has sufficient space before backup
- Mirror backup/restore takes significantly longer than full backup
- Verify backup file integrity before relying on it
- Keep multiple backup copies in different locations
- Do not power off during mirror restore operations
- Auto backup failures usually indicate insufficient storage space
