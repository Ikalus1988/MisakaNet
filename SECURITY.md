# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| v1.x    | ✅ Active development |
| < 1.0   | ❌ Pre-release |

## Reporting a Vulnerability

If you discover a security vulnerability in Misaka Network, please report it confidentially:

1. **Open a GitHub Issue** with the `security` label (preferred for non-critical issues)
2. **For sensitive disclosures**, email the project maintainer or open a Discussion

We will acknowledge receipt within 48 hours and provide an estimated timeline for a fix.

## Known Security Notes

### Exposed PAT (by design)
The public registration form uses a fine-grained Personal Access Token with **Issues:write** scope only. This is a deliberate trade-off for zero-friction onboarding:

- Scope is locked to a single repo (`Ikalus1988/MisakaNet`)
- Can only create issues (cannot read/write code, cannot manage settings)
- Hex-encoded in `docs/index.html` and `JOIN.md`
- Token should be rotated periodically

### What we do NOT expose
- No database credentials
- No cloud service keys
- No user passwords or personal data
- No access to other repositories

## Best Practices

- Rotate the public PAT every 30 days
- Review new lesson contributions for hardcoded secrets
- Use environment variables for any local credentials
