# Auto-Draft from Crash Tombstones

`auto-draft.yml` has two supported input paths:

1. **Manual dispatch** — provide `tombstone_json`, or provide a
   `tombstone_file` path that already exists in the checked-out repository.
2. **Remote dispatch** — a relay configured as fatal-guard's `FATAL_HANDLER`
   calls the GitHub `repository_dispatch` API with event type
   `crash-tombstone`. Its `client_payload` must contain either:

   - `tombstone`: the decoded tombstone object; or
   - `tombstone_json`: the JSON string containing that object.

`@misaka-net/fatal-guard` only serializes a crash and invokes the configured
handler. It does **not** write `crash-reports/latest-tombstone.json` into this
repository. There is therefore no implicit `crash-reports/` fallback: the
handler/relay is the source for remote events, and manual dispatch is the
source for local files.

The workflow invokes `scripts/tombstone_to_draft.py --create-issue`, which is
the converter's supported metadata option. It generates a draft under
`lessons/drafts/` and a `.issue.json` sidecar; the sidecar is review metadata,
not an automatic bounty or GitHub issue creation request.