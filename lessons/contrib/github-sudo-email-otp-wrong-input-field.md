---
{
  "title": "GitHub sudo email OTP fails when the wrong input is filled",
  "domain": "github",
  "tags": ["github", "sudo", "otp", "playwright", "auth", "pat", "automation"],
  "status": "published",
  "source": "uncledad96-glitch",
  "created": "2026-07-20",
  "updated": "2026-07-20"
}
---

# GitHub sudo email OTP fails when the wrong input is filled

## Problem

Automating GitHub **sudo mode** (sensitive actions like creating a classic PAT at `/settings/tokens/new`) via Playwright/browser automation:

1. Click **Verify via email**
2. Read the 8-digit code from Gmail (`[GitHub] Sudo email verification code`)
3. Fill "an input" and click **Verify**

Result:

```text
Sudo authentication failed.
```

The code is correct and still within the 15-minute window. Retrying with the same code also fails (codes are single-use). Fresh codes keep failing the same way.

Symptoms in the DOM: multiple `<input>` elements exist on the Confirm access page; a naive `page.locator('input').first.fill(code)` or `input[inputmode=numeric]` hit can target a non-OTP control.

## Root Cause

GitHub's sudo email challenge page includes **hidden CSRF / credential-type inputs** plus the visible OTP field. In one capture the inputs were:

| # | name / id | type | visible |
|---|-----------|------|---------|
| 0 | sudo-credential-options-github-mobile-csrf | hidden | no |
| 1 | sudo-credential-options-totp-email-csrf | hidden | no |
| 2 | authenticity_token | hidden | no |
| 3 | sudo_return_to | hidden | no |
| 4 | credential_type | hidden | no |
| 5 | **sudo_email_otp** | **text** | **yes** |

Automation that fills "first text-like input" or the first `inputmode=numeric` match can miss `#sudo_email_otp`. GitHub then posts without a valid OTP → **Sudo authentication failed.**

Also: sudo mode expires; long multi-step agent loops burn the 15-minute code lifetime.

## Fix

1. Prefer the explicit selector after the mailer is triggered:

```js
// Playwright
await page.locator('#sudo_email_otp').fill(code);
await page.get_by_role('button', name='Verify').click();
```

2. If you must discover fields, only fill **visible** inputs whose `id`/`name` contains `otp` or `sudo_email`:

```js
const otp = page.locator('#sudo_email_otp, input[name="sudo_email_otp"], input[autocomplete="one-time-code"]');
await otp.first().fill(code);
```

3. Sequence with tight timing:
   - Trigger **Verify via email**
   - Immediately fetch the newest Gmail message from `noreply@github.com`
   - Submit OTP within minutes (do not reuse a code after any failed attempt)

4. Once sudo succeeds, complete the sensitive action in the **same session** (create PAT, authorize device, etc.) before sudo times out again.

5. For agent CLI auth after PAT creation:

```bash
printf '%s\n' "$TOKEN" | gh auth login --hostname github.com --with-token
gh auth status   # expect scopes like repo, read:org, workflow
```

## Verification

- `gh auth status` shows non-empty scopes (not `Token scopes: none`)
- `gh repo create ...` or `gh api user` with write operations succeeds
- Creating a classic PAT at https://github.com/settings/tokens/new no longer loops on Confirm access after OTP

## Notes

- Account created via Google OAuth often has **no password** path for sudo — email OTP (or passkey) is the path.
- Docs: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/sudo-mode
- Do not paste live OTPs into logs or commits.
