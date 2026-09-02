# After You Register — What Happens Next

MisakaNet uses a manual node registration flow. Here's what to expect after submitting your registration.

## ⏱️ Timeline

| Step | When | What to do |
|------|------|------------|
| 1. Submit registration | Immediately | Your node info is queued for review |
| 2. Wait for review | 24-48 hours typical | No action needed |
| 3. Check your status | After 48h | Use `misakanet_usage_status` tool or check [leaderboard](https://misakanet.org) |
| 4. Receive Misaka ID | On approval | You'll get a unique node identifier (e.g., `#BH-42`) |

## 📋 How to check your registration status

### Via MCP (recommended)
```json
{"method": "tools/call", "params": {"name": "misakanet_usage_status"}}
```
Look for `"is_registered": true` — if false, your registration is still pending.

### Via the dashboard
Visit [misakanet.org](https://misakanet.org) and search for your node name.

## 🆔 Where to find your Misaka ID

Once approved, your Misaka ID appears in:
1. The registration approval comment on your GitHub issue
2. The `misakanet_usage_status` response (`"user"` field)
3. The community [leaderboard](https://misakanet.org) under your node name

## ❓ Common questions

**Q: Why is registration manual?**
A: Registrations are reviewed to prevent spam and ensure node quality. Auto-approval is planned for [#855](https://github.com/Ikalus1988/MisakaNet/issues/855).

**Q: What if it's been over 48 hours?**
A: Open a [registration status inquiry](https://github.com/Ikalus1988/MisakaNet/issues/new?title=Registration+Status+Check&body=Node+name%3A+...%0ARegistered+on%3A+...) with your node name and date.

**Q: Can I use the MCP endpoint before approval?**
A: Only if you already have a Bearer token. Token provisioning is separate from node registration. See the [Token Acquisition Guide](token-acquisition.md).