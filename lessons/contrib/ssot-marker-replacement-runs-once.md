---
title: 'A marker-replacement sync consumes its own marker: run #2 is a silent no-op'
domain: devops
tags:
  - ssot
  - idempotency
  - codegen
  - ci
  - drift
  - verification
status: published
created: '2026-09-12'
updated: '2026-09-12'
source: lesson-count-ssot-write-once-2026-09-12
evidence_level: E1

provenance:
  source: "external"
  contributor: "Ikalus1988"
  merged_at: "2026-09-12"
  evidence: "post-publication"
---

# A marker-replacement sync consumes its own marker: run #2 is a silent no-op

## Problem

A repository-wide "single source of truth" helper was added to stop public numbers from drifting. Its
docstring promised the mechanism made drift impossible:

```python
"""... docs carry a generated marker instead of hand-edited numbers,
so counts cannot silently drift."""
for name in COUNT_MARKER_DOCS:
    text = (REPO / name).read_text(encoding="utf-8")
    if "{{LESSONS_COUNT}}" not in text:
        continue                      # ← nothing left to replace
    (REPO / name).write_text(text.replace("{{LESSONS_COUNT}}", str(count)), encoding="utf-8")
```

It ran daily, stayed green, and the numbers drifted anyway — for a week, in the most visible places:

| Surface | Said | Truth |
|---|---|---|
| `README.md` tagline | `310+ failure lessons` | 378 |
| Site `<meta name="description">` / `og:description` | `435 indexed ... lessons` | 378 (+15% inflated in Google results and social cards) |
| Search page `<meta description>` | `249 indexed ... lessons` | 378 |
| `llms.txt`, integration guides | `205+ verified ... lessons` | 378 |

## Root Cause

**Replacement consumes the placeholder.** Run #1 turns `{{LESSONS_COUNT}}` into `378`. From run #2 on,
the guard `if "{{LESSONS_COUNT}}" not in text: continue` is true for every file, so the loop body never
executes. The mechanism is one-shot by construction, and *it cannot report that it did nothing*.

Three amplifiers made it invisible:

1. **The tool's own success output looks identical.** Run #1 printed
   `OK ARCHITECTURE.md: {{LESSONS_COUNT}} -> 378` and exited 0. A sync that will never run again and a
   sync that works perfectly produce the same green log on the day they are introduced.
2. **Nothing asserted re-runnability.** Unit checks covered "does it substitute correctly?" — i.e. the
   first run. No test took a second pass, so "the tenth run is as correct as the first" was never a
   property the suite could fail on.
3. **A second copy of the file list lived in workflow YAML.** The daily job's diff guard and `git add`
   listed `ARCHITECTURE.md README.md docs/_lessons_count.txt` explicitly. Any surface missing from those
   lists (the website's `<meta>` tags) could not even be *committed* if it were rewritten, so the
   workflow's "did anything change?" step silently agreed with the broken helper.

Note the ordering trap: the fix for symptom #3 (extend the hardcoded list) makes symptom #1 worse,
because now a no-op sync produces no diff at all and the job reports "nothing to commit" — success.

## Solution

Replace "substitute a marker" with **re-match a value**, and make a lost match fatal.

```python
@dataclass(frozen=True)
class Site:
    path: str         # file to keep in lockstep
    pattern: str      # regex containing named group n = the number currently written
    replace: str      # replacement template, {n} = canonical value (backrefs allowed)
    note: str         # why this surface matters (printed in every error message)
    min_matches: int = 1

for site in SITES:                      # registry, not placeholder presence
    hits = list(re.compile(site.pattern, re.MULTILINE).finditer(text))
    if len(hits) < site.min_matches:
        errors.append(f"{site.path}: pattern matched {len(hits)}×, expected ≥{site.min_matches} "
                      "— the sentence was reworded: fix the file or update SITES")
        continue
    text = site.pattern.sub(site.replace.format(n=count), text)
```

Properties this buys, in decreasing order of importance:

- **Idempotent:** the pattern describes the *value*, so run #10 rewrites as correctly as run #1.
- **A reworded sentence is an error, not a skip.** If someone edits the managed sentence, the check fails
  with the file, the line, and the pattern — instead of the tool quietly managing nothing.
- **The registry is the single list.** The workflow stages `git add -u` / `git status --porcelain`,
  so the generator's real output set and the commit step cannot disagree.

For the marker style specifically, the portable trick is to keep the sentinel *next to* the value
(`<!--LESSONS_COUNT-->378`) — but only where a comment is invisible (HTML text nodes). Inside a Markdown
code fence, or a `<meta content="...">` attribute, a sentinel is user-visible, which is exactly why the
value-regex registry is the safer default.

### Two more bugs, same family

Both were caught by writing the fix — they are what a "make it idempotent" change tends to unearth:

1. **A pattern that cannot match its own output.** A row validated `205+ verified failure lessons` with a
   pattern that *required* the `+` and the word `verified`; the replacement wrote `378 indexed failure
   lessons`. After the first successful run the pattern matched nothing and the tool would have cried
   "reworded sentence!" forever. **Invariant: every row must be a fixed point of its own replacement.**
2. **Per-row writes clobbering each other.** Applying rows one at a time from the text captured *before*
   the loop meant each write reverted the previous row's edit: the tool reported `docs/index.html: 3
   site(s) → 378`, and the file on disk still read `435`. Apply all rows for a file to one accumulating
   string, then write once.

## Verification

- **Run it twice with different inputs.** `sync(400)` then `sync(500)` must rewrite the same file again.
  A write-once mechanism passes the first call and fails the second — that is the whole test.
- **Assert the checker fails when you perturb one site.** Mutate one managed number by hand and confirm
  `--check` exits non-zero naming that file and line. A gate that was never observed failing is not a gate.
- **Assert the pattern is a fixed point:** `subn(replace)` applied to its own output must match again and
  change nothing. This fails loudly for every row whose validation is stricter than its writing.
- **Observe the *scheduled* run after the change**, not the commit: the real signal is that the daily job
  produced a new count (or explicitly reported "already consistent"), not that CI was green on push.

## Detection Heuristics

- Grep your tooling for `.replace(` on a placeholder token, and ask: *what does run #2 do?* If the answer
  is "nothing, because the token is gone", you own a write-once generator wearing an SSOT badge.
- `if <marker> not in text: continue` is a silent-skip machine. So is `continue` on a missing file, a
  missing key, or a non-matching regex — the failure mode is identical to success from the outside.
- A duplicated file list (generator code + workflow `git add` + workflow diff guard) will drift. Stage
  what changed (`git add -u`) rather than naming files in a second place.
- Docstrings and PR descriptions that claim an invariant ("cannot silently drift") are not evidence the
  invariant holds. For each claim, name the test that would fail if it were false; if there is none, the
  claim is a guess with good formatting.
- A generated number that appears in **more than one file** needs one writer and one checker. Two
  mechanisms for the same fact (a placeholder helper here, a regex helper there, neither run by CI) is how
  the same fact ends up with three different values in three places.
