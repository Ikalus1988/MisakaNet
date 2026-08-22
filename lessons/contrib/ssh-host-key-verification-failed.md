---
{
  "title": "SSH host key verification failed when connecting to a remote server",
  "domain": "devops",
  "tags": "[ssh, host-key, verification, remote, security]",
  "language": "ja",
  "status": "published",
  "source": "manual",
  "created": "2026-07-29",
  "confidence": 0.9,
  "verified_date": "2026-07-29",
  "author": "Liona Can",
  "edited_at": "2026-08-21T13:12:59+08:00",
  "merged_by": "Liona Can"
}
---

## Problem

This error occurs when SSH refuses to connect to a remote server because the host key has changed or is unknown. The connection fails with:

```
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
IT IS POSSIBLE THAT SOMEONE IS DOING SOMETHING NASTY!
Offending ED25519 key in ~/.ssh/known_hosts:3
Host key verification failed.
```

This failure happens when trying to SSH into a server that was previously connected to but has been reinstalled or reconfigured, or when connecting to a new server for the first time in strict mode.

## Root Cause

SSH maintains a file `~/.ssh/known_hosts` that stores the public host keys of every server you connect to. This prevents man-in-the-middle attacks. The error appears in two scenarios:

1. **Host key changed**: The remote server was reinstalled or its SSH keys regenerated. The stored key in `known_hosts` no longer matches.
2. **Host unknown**: The server is not in `known_hosts` at all, and `StrictHostKeyChecking` is set to `yes`.

## Solution

**1. Remove the old host key (for changed keys)**
```bash
ssh-keygen -R hostname.example.com
```
Replace `hostname.example.com` with the actual server hostname or IP address.

Alternatively, edit `~/.ssh/known_hosts` manually and delete the offending line.

**2. Connect again**
```bash
ssh user@hostname.example.com
```
SSH will prompt you to accept the new host key. Verify the key fingerprint with the server administrator before accepting.

**3. For new servers in automation scripts**
Temporarily disable strict checking (not recommended for production):
```bash
ssh -o StrictHostKeyChecking=no user@hostname.example.com
```

Better approach: add the host key to `known_hosts` non-interactively:
```bash
ssh-keyscan -H hostname.example.com >> ~/.ssh/known_hosts
```

**4. Verify host key fingerprint**
```bash
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```
Compare the output with the fingerprint shown during SSH connection.

**5. Check the known_hosts file**
```bash
cat ~/.ssh/known_hosts
ssh-keygen -F hostname.example.com  # search for a specific host
```

## Verification

- Run `ssh user@hostname.example.com` and confirm the connection succeeds
- Verify the host key fingerprint matches the one provided by the server administrator
- Test with `ssh -v user@hostname.example.com` to see verbose connection details
- Confirm the entry appears in `known_hosts` after accepting

## Notes

- Always verify host key fingerprints with the server administrator before accepting
- The warning about a changed host key could indicate a man-in-the-middle attack — investigate before proceeding
- Use `ssh-keyscan` in provisioning scripts to pre-populate `known_hosts`
- Different key types (RSA, ECDSA, ED25519) each have separate entries in `known_hosts`
- Reference: [GitHub SSH troubleshooting guide](https://docs.github.com/en/authentication/troubleshooting-ssh/error-host-key-verification-failed)
