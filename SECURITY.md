# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| v2.x    | ✅ Active development |
| < 2.0   | ❌ Pre-release |

## Reporting a Vulnerability

If you discover a security vulnerability in Misaka Network, please report it confidentially:

1. **Open a GitHub Issue** with the `security` label (preferred for non-critical issues)
2. **For sensitive disclosures**, email the project maintainer or open a Discussion

We will acknowledge receipt within 48 hours and provide an estimated timeline for a fix.

## Known Security Notes

### Content-Security-Policy: where it is, and where it is not

`_headers` ships a `default-src 'none'` policy on the **521 of 532** HTML pages that
cannot execute script. Measured 2026-10-06: those pages carry no inline `on*` handler,
no executable inline `<script>`, and no `url(...)` anywhere in their inline CSS.
Because `script-src` falls through to `default-src`, script is denied on all of them.

The **eleven pages that do run script have no CSP**: `/`, `/start.html`,
`/connect.html`, `/journey/`, `/search/`, `/search/danmaku-widget.html` and
`/insights/*.html`. That is a known, accepted gap, written down because it is real:

- `docs/index.html` alone carries 47 inline `on*` handlers and an 82.9 KB inline
  `<script>`. A policy strict enough to matter would have to rewrite that markup, and
  this repository has **no browser test for the homepage**, so the rewrite could not be
  verified before shipping. Shipping an unverified rewrite to close a header gap is a
  worse outcome than leaving the gap open.
- `_headers` merges every matching rule and comma-joins a repeated header name, so a
  CSP written under `/*` cannot be relaxed for those eleven pages without shipping an
  unparseable `Content-Security-Policy: a, b`. The policy is therefore written only on
  the paths that can take it.

`tests/test_site_csp.py` keeps this honest. It fails if a page grows script *under* a
CSP rule (the policy would silently break it), if a script page appears outside the
eleven named above (the gap is growing), if a covered page reaches for a host the
policy forbids, and if the rules are deleted or loosened. Closing the remaining eleven
means adding a real browser test first and rewriting the inline handlers as
`addEventListener` second — that order is deliberate.

The homepage's text sanitizer is pinned and gated separately: DOMPurify 3.4.16 with a
recorded SRI hash in `data/external_assets.json`, checked offline on every PR and
against the live CDN weekly. See #2672, #2683 and #2730.

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
