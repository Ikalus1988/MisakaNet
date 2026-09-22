# State of the repository

This is the shareable maintainer snapshot. It intentionally contains no
credential values, credential hints, token names, or private handoff details.
Private, per-round notes belong in the ignored `docs/maintainer/handoff-*.md`
files and must not be copied here.

## Snapshot metadata

- Last reviewed: 2026-09-22
- Maintainer: **owner confirmation required**
- Update cadence: review this file before every release and at least once per
  week. The reviewer must update the date, remove stale items, and record any
  changed decision or risk in the same pull request.

## In-flight pull requests

No pull requests are confirmed in this checkout. Before release, the maintainer
must reconcile this section with the hosting service and list each open PR by
number, title, owner, review status, and release impact. Do not infer status from
an old handoff.

## Decisions requiring owner confirmation

- Confirm the current release target and whether any open PR is release-blocking.
- Nominate at least one maintainer who can review and run the repository without
  the owner being present.
- Replace owner-only automation credentials with least-privilege, rotatable
  service identities where the platform supports them.
- Approve an alerting policy for failed or skipped repository gates.

## Platform debt and automation ownership

- Several automations currently run under the repository owner's personal
  platform identity. This is an ownership dependency, not a credential-sharing
  instruction; values and credential hints remain private.
- Inventory each automation, its trigger, permissions, and accountable human
  owner before granting access to a second maintainer.
- Add documented rotation and revocation steps, plus a dry-run path, before
  changing an identity or permission.

## Known trust and gate weaknesses

- A gate can fail to trigger silently. A green status therefore does not prove
  that the intended gate ran; verify that the expected check exists and records
  the expected scope.
- Required checks must be tested with a deliberately failing fixture and with a
  missing-trigger scenario. Missing, skipped, or stale checks should fail closed.
- Reviewers should inspect the generated check list and the artifact timestamp,
  not only the aggregate status badge.

## Bus factor

The current operational bus factor is **1**: the owner is the only confirmed
person with the full context for the private handoff and owner-identity
automations. This public document reduces the information bottleneck, but does
not claim that a second maintainer is already enabled. The bus factor becomes
greater than one only after another maintainer can independently read this file,
run the documented checks, and complete a release dry run.

## Handoff boundary

Keep private handoff files out of commits. They may contain sensitive operational
context, but this public snapshot must remain safe to review, mirror, and share.
When updating this page, manually scan the diff and run:

```text
python3 scripts/injection_scan.py
```

