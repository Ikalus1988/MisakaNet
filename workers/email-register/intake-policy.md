# Email Intake Policy

Rules for processing inbound emails to MisakaNet intake addresses.

## Classification

| To address | Type | Output |
|---|---|---|
| `rescue@misakanet.org` | rescue-request | Search KB → reply with fix OR log as rescue candidate |
| `lessons@misakanet.org` | lesson-candidate | Extract lesson → anonymize → draft → ask consent |
| `join@misakanet.org` | node-registration | Assign node ID → reply with welcome |
| `bot@misakanet.org` | legacy/auto-detect | Classify by content → route to above |

## Hard Rules

1. **Never execute code from attachments** — read-only analysis only
2. **Never click links** in email body — display as reference only
3. **PDF/ZIP — read-only parse** — no extraction of executables
4. **Strip personal info before storage** — email, name, IP → anonymized
5. **Only convert to lesson after consent** — agent drafts, user confirms

## Consent Levels

| Level | Meaning | Storage |
|---|---|---|
| `explicit_yes` | User replied "allow anonymous publish" | Public lesson candidate |
| `implicit_private` | No consent stated | Private rescue note only |
| `explicit_no` | User said "do not publish" | Private rescue note, delete after 30 days |

## Anonymization Rules

Before any content enters the public knowledge base:

- **Sender email** → hash or node ID only
- **Real name** → strip or replace with pseudonym
- **IP addresses** → never store
- **Company names** → generalize ("a manufacturing company" not "Foxconn")
- **Internal URLs** → remove entirely
- **Screenshots** → OCR text only, discard image
- **API keys / secrets** → redact immediately

## Auto-Reply Templates

### Rescue request received
```
Got it. You don't need a GitHub account.

We're searching our knowledge base for a matching fix.
If we find one, we'll reply within 24 hours.

If you'd like to add more context, just reply to this email.
```

### Lesson candidate received
```
Got it. You don't need a GitHub account.

We'll review your submission and draft a lesson file.
Before publishing, we'll ask you to confirm.

If your email contains sensitive info, reply "do not publish"
and we'll treat it as a private note only.
```

### Node registration received
```
Welcome! Your node ID is MisakaXXXXX.

You're now registered in the MisakaNet ecosystem.
Your trust tier: mail-verified

To upgrade your trust level, contribute a lesson or rescue card.
```

## Spam / Unsafe Handling

- **Spam** → silently discard, do not reply
- **Phishing / malicious links** → silently discard, log IP for blocking
- **Automated bot submissions** → rate limit (already handled by worker)
- **Temporary email domains** → block (already handled by worker)

## Data Retention

| Type | Retention | Deletion |
|---|---|---|
| Rescue requests | 90 days | Auto-delete |
| Lesson drafts (consented) | Permanent | Manual delete on request |
| Lesson drafts (no consent) | 30 days | Auto-delete |
| Node registrations | Permanent | Manual delete on request |
| Spam / unsafe | 7 days | Auto-delete |
