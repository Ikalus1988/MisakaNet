{
  "title": "Permission Denied / WSL NTFS Cross-Filesystem Permission Fix",
  "domain": "devops",
  "tags": ["wsl", "permissions", "ntfs", "linux", "cross-platform", "chmod"],
  "status": "published",
  "source": "translated-contrib",
  "lang": "en",
  "translated_from": "permission-denied-fix.md"
}

# Permission Denied / WSL NTFS Cross-Filesystem Permission Fix

## Problem

In WSL (Windows Subsystem for Linux), file operations on the Windows filesystem (`/mnt/c/`) fail:

```bash
$ chmod 600 ~/.ssh/id_ed25519
chmod: changing permissions of '/home/user/.ssh/id_ed25519': Permission denied

$ ./script.sh
bash: ./script.sh: Permission denied

$ git clone git@github.com:user/repo.git
Cloning into 'repo'...
error: chmod on /mnt/c/Users/name/repo/.git/config.lock failed: Permission denied
```

The same commands work fine on the native Linux filesystem (`~/`), but fail on `/mnt/c/`.

## Root Cause

WSL mounts Windows drives with the **DrvFs** filesystem, which:
1. **Doesn't support POSIX permissions**: Windows NTFS uses ACLs, not Unix-style permission bits
2. **Default mount maps everything to 777**: All files appear world-readable/writable
3. **`chmod` is a no-op**: The metadata call succeeds but doesn't actually change anything
4. **Some tools strictly require 600/700 permissions**: SSH and Git refuse to use keys/configs with "loose" permissions

The error "Permission denied" is misleading — you HAVE permission, but the tool is rejecting it because the permission bits look too open.

## Fix

### Option A: Move sensitive files to native Linux filesystem
```bash
# WSL's native ext4 filesystem supports real permissions
cp ~/.ssh/id_ed25519 /home/$USER/.ssh/id_ed25519
chmod 600 /home/$USER/.ssh/id_ed25519  # Works!

# Or put entire project there
cd ~/projects  # NOT /mnt/c/Users/...
git clone git@github.com:user/repo.git
```

### Option B: Mount with metadata support
```bash
# Edit /etc/wsl.conf (create if it doesn't exist)
sudo nano /etc/wsl.conf

[automount]
enabled = true
options = "metadata,umask=22,fmask=11"

# Restart WSL to apply:
# In PowerShell (admin): wsl --shutdown
# Then reopen WSL terminal
```

### Option C: Configure Git to accept NTFS permissions
```bash
# Tell Git this is a shared/unsafe filesystem
git config --global core.fileMode false

# Allow SSH to work on DrvFs
# Add to ~/.bashrc or ~/.zshrc:
export GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=no"
```

### Option D: Workaround for single-file chmod
```bash
# Copy to Linux fs, chmod, copy back
cp /mnt/c/path/to/key ~/tmp_key
chmod 600 ~/tmp_key
# Use the copy directly, don't try to chmod on /mnt/c
ssh -i ~/tmp_key user@host
```

## Verification

```bash
# Check if you're on DrvFs
df -T . | grep -q 'drvfs\|9p' && echo "WARNING: On DrvFs — chmod won't work"

# Check actual file location
readlink -f .ssh/id_ed25519
# If it starts with /mnt/c/, you're on NTFS

# Verify permissions actually applied
ls -la .ssh/id_ed25519
# Should show -rw------- (600) not -rwxrwxrwx (777)
```

## Key Takeaways

- DrvFs silently ignores `chmod` — the command "succeeds" but does nothing
- SSH requires exactly 600 on private keys — DrvFs can never provide this
- The fix is to put sensitive files on the native Linux filesystem (`~/.ssh`, not `/mnt/c/.../`)
- `git config core.fileMode false` is essential for repos on `/mnt/c/`
- WSL2 has much better filesystem performance when projects are on the native ext4 volume
