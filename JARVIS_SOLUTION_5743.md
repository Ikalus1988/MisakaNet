# Proposed Fix for #5743

To resolve the bounty issue #5743, we need to provide accurate, comprehensive technical answers to the two unindexed/uncovered user questions linked (#5648 and #5660) and record these answers in the repository's knowledge base or FAQ documentation so that future retrieval queries do not result in `no_match`.

---

## Implementation Plan

1. **Answer Question #5648**: Explain why OpenSSH SFTP's `put -a` (append) fails with `stat remote: No such file or directory` on the first upload (the remote file doesn't exist yet, so `stat` fails before append can occur), and provide the workaround (use standard `put` for the first upload, then `put -a` for subsequent appends, or use shell redirection / `sftp` batch scripting conditionals).
2. **Answer Question #5660**: Detail the exact verification steps for an OpenSSH `known_hosts` file containing a pinned key (verify public key algorithm matching, verify key fingerprint via a trusted out-of-band channel, check hash-format configuration `|1|...`, and ensure proper file permissions).
3. **Documentation Patch**: Add these answers to the repository's FAQ or troubleshooting knowledge base file (e.g., `docs/faq-bounties.md` or similar knowledge file) so that the BM25 retrieval path indexes them and resolves future queries.

---

## Code Patch

```markdown
# File: docs/faq-bounties.md (or equivalent knowledge base document)

## Resolved Bounty Questions

### Q1: OpenSSH SFTP batch 'put -a' for a first upload reports 'stat remote: No such file or directory' (#5648)
* **Answer:** 
The `put -a` command instructs the SFTP client to append local data to an existing remote file. Under the hood, OpenSSH's `sftp` client executes a `stat` call on the remote path to verify existence and retrieve file attributes before opening the stream in append mode. If the remote file does not yet exist, `stat` fails with `No such file or directory`, halting the batch execution.
* **Workaround:**
  1. Use standard `put` for the initial file creation/upload.
  2. Use `put -a` only for subsequent incremental updates.
  3. Alternatively, in batch scripts, handle this gracefully by ensuring the file exists beforehand (e.g., running a dummy `echo` or `touch` equivalent via sftp if supported, or splitting logic in your automation wrapper).

---

### Q2: What should a verifier check when an OpenSSH known-hosts file has a pinned key? (#5660)
* **Answer:**
When verifying an OpenSSH `known_hosts` file containing a pinned public key, a verifier should systematically check the following parameters:
  1. **Key Type & Algorithm:** Ensure the key type specified (e.g., `ssh-ed25519`, `ecdsa-sha2-nistp256`, `ssh-rsa`) matches the expected modern cryptographic standard and aligns with what the server actually presents.
  2. **Fingerprint Validation:** Compare the base64-encoded public key or its hashed representation against the officially published/out-of-band verified fingerprint (SHA256).
  3. **Hash Format (`@hash-prefix`):** Check whether the hostname is hashed (e.g., starting with `|1|`). If hashed, verify how the lookup mechanism resolves it, or unhash/re-hash if auditing manually.
  4. **Key Match and Options:** Ensure no conflicting entries exist for the same host/IP and that any forced options (like `command="..."`, `restrict`) match expected security policies.
  5. **File Permissions:** Verify that the `known_hosts` file permissions are strictly restricted (e.g., `644` or `600`) to prevent unauthorized modification or key substitution.
```
