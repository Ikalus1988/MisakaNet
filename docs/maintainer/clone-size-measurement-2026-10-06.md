# Clone size: what was measured, and why "delete three directories" was the wrong plan

Date: 2026-10-06. All figures measured on that date; commands given so they can be re-run.

## The short version

A proposal was approved to cut `git clone` cost by 46% (73 MB → 50 MB) by deleting three
directories from the tree: `promotional/`, `docs/benchmarks/`, and `docs/data/lessons.json`.

**Measured, that number is wrong twice over, and the operation that would actually deliver a
reduction is not "delete three directories" — it is a full history rewrite.** The measured
achievable saving is 36%, not 46%, of a 45 MB clone, not a 73 MB one, and it costs every one of
the 5,660 commit SHAs in the repository.

The owner decided against the rewrite and for bounded forward growth instead
(`chore/benchmark-snapshot-retention`). This file exists so the next proposal does not start from
the 73 MB / 46% numbers again.

## 1. The clone is 45 MB, not 73 MB

```bash
git clone --bare https://github.com/Ikalus1988/MisakaNet.git /tmp/probe
du -sh /tmp/probe                       # 45M
du -cb /tmp/probe/objects/pack/*.pack   # 44,896,795 bytes
```

The 73 MB figure predates this measurement and was never re-derived from an actual clone. Treat
it as unverified.

For contrast, the working checkout is a different thing entirely:

```bash
du -sh .git              # 81M   (total pack bytes 71,560,025)
du -sh --exclude=.git .  # 293M  (the checked-out tree)
```

A clone transfers `.git`, not the 293 MB worktree — but it does check the files out, so what a
new user actually writes to disk is larger than the pack. Both numbers matter and they are not
interchangeable.

## 2. Deleting files from HEAD saves exactly zero bytes of clone

The three paths are not dead weight in the working tree; they are baked into the object store:

```bash
git log --oneline --all -- promotional | wc -l            # 31 commits
git log --oneline --all -- docs/benchmarks | wc -l        # 14 commits
git log --oneline --all -- docs/data/lessons.json | wc -l # 104 commits
```

Uncompressed blob bytes reachable under each path:

| path | history bytes |
|---|---|
| `promotional/` | 14.7 MB |
| `docs/benchmarks/` | 13.1 MB |
| `docs/data/lessons.json` | **88.0 MB** |

That last row is the one that inverts the intuition. The file on disk is 1.4 MB, but it has been
rewritten 104 times, so the object store carries 88 MB of its past revisions. **The per-file size
understates the history cost by ~60×.**

A commit that deletes a path changes the tip tree. The blobs stay in the pack because history still
references them. A clone downloads history. Therefore: deleting from HEAD does not shrink a clone.
This is not a subtlety to argue about, it is the definition of what a pack contains.

## 3. What a rewrite actually buys — measured, then thrown away

Run on a throwaway bare clone in `/tmp`, never on the working checkout:

```bash
GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
  git-filter-repo --force --invert-paths \
    --path promotional --path docs/benchmarks --path docs/data/lessons.json
```

The two `GIT_CONFIG_*` overrides are not optional on this machine. `~/.gitconfig` contains a
multi-line shell alias (`alias.ghub=!f() { … }; f`), and `git config --list` renders it across
several lines; `git_filter_repo.py` parses that output with a naive `line.split('=', 1)` and dies
with `ValueError: dictionary update sequence element #9 has length 1`. That is a local config
shape, not a repository defect, but it will hit anyone with the same alias.

Result:

| | before | after |
|---|---|---|
| bare clone | **45 MB** | **29 MB** |
| pack bytes | 44,896,795 | 27,444,222 |
| commits | 5,660 | 5,640 |
| tags | 66 | 66 |
| `main` | `4fce44f9` | `d2054441` |

**Saving: 16 MB, 36%.** Not 46%.

And the price:

- Every commit SHA changes. `main` moved from `4fce44f9` to `d2054441`; there is no way to keep
  one and change the tree.
- All 66 tags keep their names and change their targets. `v2.41.2` would stop pointing at the
  commit whose SHA is recorded in the npm and PyPI provenance for that release.
- 20 commits became empty and were pruned (5,660 → 5,640), so those changes disappear from
  history entirely.
- All open PRs break, and every existing fork diverges permanently.

36% of 45 MB, against an irreversible rewrite of the shared history of a repository with published
releases. The owner declined. That was the right call and this section exists so it does not get
re-litigated on the original numbers.

## 4. What was done instead: bound the growth, do not touch the past

Pruning a committed path cannot shrink existing clones, so the achievable action is to stop the
directory from growing. See `tests/test_benchmark_snapshot_retention.py` and the retention step in
`.github/workflows/benchmark-workers-ai.yml`.

The measured finding that motivated it: every `benchmark-YYYY-MM-DD.json` is a byte-for-byte copy
of `latest.json` as of that date (2026-09-28's snapshot and `latest.json` were both exactly
1,891,265 bytes), because `scripts/benchmark_workers_ai.py` writes a cumulative file and
`benchmark-workers-ai.yml` copies it. So they were copies, not evidence — 13.2 MB holding no
measurement that `latest.json` did not already hold.

## 5. One thing that is NOT solved by any of the above

`latest.json` itself grows without bound: 1.5 MB on 2026-08-30, 1.89 MB on 09-28, 2.06 MB on
10-05, because the benchmark resume cache is keyed on `(model, scenario[:80], condition)` and
every run is appended and never dropped. Retention on the *copies* does nothing for the original.

If clone size is ever worth revisiting, that file is where the growth actually is — and cutting it
means deciding what the benchmark history is for, which is a product question, not a git one.

## Reproduce

```bash
git clone --bare https://github.com/Ikalus1988/MisakaNet.git /tmp/probe && du -sh /tmp/probe
git log --oneline --all -- docs/data/lessons.json | wc -l
# then, on the throwaway clone only:
cd /tmp/probe && GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
  git-filter-repo --force --invert-paths --path promotional \
  --path docs/benchmarks --path docs/data/lessons.json && du -sh /tmp/probe
```