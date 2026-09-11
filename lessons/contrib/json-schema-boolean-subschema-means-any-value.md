---
title: 'A JSON Schema `"key": true` says "any value allowed" — not "set it to true"'
domain: devops
tags:
  - json-schema
  - configuration
  - release-please
  - ci
  - attribution
  - verification
status: published
created: '2026-09-11'
updated: '2026-09-11'
source: release-please-signoff-schema-misread-2026-09-11
evidence_level: E1

provenance:
  source: "external"
  contributor: "Ikalus1988"
  merged_at: "2026-09-11"
  evidence: "post-publication"
---

# A JSON Schema `"key": true` says "any value allowed" — not "set it to true"

## Problem

I added one line to an automation config after "checking it against the published JSON Schema", and
broke the tool on the default branch: **every** run of it failed from then on.

```text
##[error]release-please failed: The format of 'true' is not a valid email address with display name
```

The message is baffling unless you already know two things: which config key is at fault, and that the
key was never meant to hold a boolean at all. The value I had written was `true`.

## Root Cause

Two mistakes stacked.

**1. Misreading a JSON Schema boolean subschema.** The published schema for the tool contains:

```json
"signoff": true
```

I read that as "the recommended value is `true`". It is not a value — it is a **boolean subschema**.
In JSON Schema, the schema `true` means *"any instance is valid here"* (and `false` means *"nothing is
valid here"*). So a bare `true` in a schema position is the schema author saying **"no constraints on
this field"**; it carries zero information about the intended type. This is common in schemas that are
hand-maintained or converted from another format, because it is the shortest way to reserve a key.

**2. Never consulting the implementation.** The tool's own source settled it in one line:

```js
function isValidSignoffUser(signoffUser) {
  // Parse the name and email address from a string in the following format
  // Display Name <email@address.com>
  const pattern = /^([^<]+)\s*<([^>]+)>$/i;
  ...
  throw new Error(`The format of '${signoffUser}' is not a valid email address with display name`);
  return commitMessage + `\n\nSigned-off-by: ${signoffUser}`;
}
```

The field is a **string** in the form `Display Name <email@address.com>`, interpolated verbatim into a
`Signed-off-by:` trailer. `true` is not merely the wrong value — it crashes the config load, so every
subsequent run of the tool fails.

## Solution

Read the type from the code, not the schema:

```json
{
  "signoff": "misakanet-bot <bot@misakanet.dev>",
  "packages": { ".": { "release-type": "python" } }
}
```

Pick the identity deliberately: here it matches the same bot name/email an existing auto-fix workflow
already used, so both paths produce identical trailers instead of two competing bot identities.

**Before pushing any config value**, reproduce it against the tool's own code path locally. For a
Node-based tool, pull the package from the registry and drive its real module:

```bash
npm pack <tool>            # or: curl <tarball> from registry.npmjs.org
tar xzf <tool>-<ver>.tgz
node -e "
  const {GenericJson} = require('./package/build/src/updaters/generic-json.js');
  console.log(JSON.parse(new GenericJson('\$.version','2.0.0').updateContent(require('fs').readFileSync('file.json','utf8'))));
"
```

Then check the value against the validator the tool actually uses (copy the regex/parser out of the
source) rather than an intuition about what "looks right".

## Verification

- Drive the tool's own updater/parser with the candidate value and confirm the produced artifact —
  not just that the process exits 0.
- Watch the tool's **next scheduled run after the change**, not the deployment step. This failure was
  invisible until the automation next fired; a stale green run before the change proves nothing.

## Detection Heuristics

- A schema that shows a bare `true` (or `false`, or `{}`) for a key is telling you *nothing* about the
  type — go read the parser, the factory, or the docs' example block.
- Config keys that are "obviously a boolean" deserve suspicion precisely because they are obvious:
  `signoff`, `draft`, `prerelease`, `skip-github-release` are all plausibly strings or enums in some
  tools. Confirm.
- An error phrased around *format* or *parsing* (`not a valid email address`, `cannot unmarshal`,
  `invalid literal`) means your value reached a parser: the field's type is wrong, not its spelling.

## The Second Mistake: Calling Confounded Evidence "Verified"

I had already declared this change verified. It was not — and the way it fooled me is worth recording,
because the config was broken the whole time.

An earlier auto-fix run on the same branch had left a commit whose trailer read
`Signed-off-by: misakanet-bot <bot@misakanet.dev>`. That is exactly the identity my (broken) config was
supposed to produce, because I had chosen it to match. I saw the trailer, saw the branch was green, and
concluded the config had taken effect.

The competing explanation — *the auto-fix workflow produced that trailer, using its own git identity,
and my config never ran successfully at all* — fit the evidence equally well. A verification is only
real if it **rules out the competing explanations**, which normally means:

1. The artifact must be produced **after** your change is active.
2. **No other mechanism** in the system can produce the same artifact.
3. Ideally, the mechanism under test is the *only* thing that ran — or you can observe it doing so.

Cheap disambiguators: give the config-generated artifact a distinct value (a different bot name/email)
instead of matching an existing one, or read the tool's own logs for the run that produced it. Here,
one look at *which run* created the commit would have shown the auto-fix workflow as the author, and
the config bug would have been caught before it reached the default branch — rather than by a human
noticing the alert.
