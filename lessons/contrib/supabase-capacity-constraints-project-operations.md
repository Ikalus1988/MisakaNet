---
{"title":"Supabase capacity constraints caused project operation failures","domain":"database","tags":["incident","postmortem","capacity","supabase","database","operations"],"status":"published","source":"hackernews","source_url":"https://status.supabase.com/incidents/3tx3nnmbwyh9","language":"en"}
---

## Problem

On 2026-06-30, Supabase reported an incident titled **"Project status change failures in multiple regions"**. Users could see repeated failures when trying to create projects, resize projects, provision branches, restart projects, restore projects, or perform database upgrades.

The public status page stated that running projects were not generally affected, but operations that needed new or replacement compute capacity could fail across many regions, including `ap-northeast-1`, `ap-northeast-2`, `ap-south-1`, `ap-southeast-1`, `ap-southeast-2`, `eu-central-2`, `eu-north-1`, `sa-east-1`, `us-east-1`, and `us-east-2`.

Typical user-facing symptoms for this class of incident are:

- project creation fails or remains stuck;
- project restart, restore, or upgrade cannot acquire capacity;
- branch provisioning and project resizing require one or more retries;
- existing databases stay available until an operation forces relocation, restart, or replacement capacity.

Source: https://status.supabase.com/incidents/3tx3nnmbwyh9

## Root Cause

The public incident updates identify the root cause category as **widespread capacity constraints across multiple regions**. The dependency was not the running database process itself; it was the control-plane path that allocates capacity for lifecycle operations.

Important debugging lesson: when an outage only affects create, resize, restore, upgrade, restart, or branch provisioning workflows, do not assume the data-plane database is down. Separate the system into:

1. **Data plane** — already-running databases and customer traffic.
2. **Control plane** — orchestration workflows that need spare regional compute capacity.
3. **Capacity pool** — the finite regional inventory consumed by project lifecycle operations.

In this incident, existing running projects could remain healthy while control-plane operations failed because they needed capacity that was not immediately available.

## Fix

For a provider or platform team, the mitigation pattern is:

1. Increase available capacity in the constrained regions.
2. Prioritize lifecycle operations that unblock customers: project creation, restarts, restores, upgrades, branch provisioning, and resizing.
3. Publish clear retry guidance so customers do not continuously hammer a saturated control plane.
4. Make status updates distinguish **running project availability** from **project operation availability**.
5. Keep a regional list of constrained pools so support and automation can route users to safer regions when possible.

For an application team consuming such a platform, the safer runbook is:

1. Avoid elective restarts, restores, upgrades, and resizes during an active regional capacity incident.
2. If a new project or branch is not urgent, wait until the status page reports added capacity.
3. If the operation is urgent, retry with bounded exponential backoff and capture the operation ID or error message for support.
4. Prefer regions that are not listed as constrained, if the product and compliance requirements allow it.
5. Keep production failover plans from depending on last-minute creation of new regional capacity.

## Verification

Use separate checks for the data plane and control plane:

- Existing application traffic to already-running databases remains healthy.
- Project creation succeeds in at least one previously affected region.
- Restart, restore, branch provisioning, project resizing, and database upgrade operations complete without repeated capacity failures.
- Regional capacity metrics show spare headroom after the incident mitigation.
- Customer guidance is updated when users can safely retry previously failing operations.

A useful post-incident test is to run a small synthetic lifecycle workflow per critical region: create a test project, create a branch, restart it, restore from a backup snapshot, resize it, then delete it. Alert on failures separately from normal database availability alerts so control-plane capacity issues are visible before customers need them during an emergency.
