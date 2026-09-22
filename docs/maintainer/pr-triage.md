# Pull-request triage guide

## Mechanical bounty-shape guard

`bounty-claim-guard.yml` is a **signal**, not an automatic rejection or merge
blocker. It runs on `pull_request_target` and uses the trusted base checkout to
compare the pull request's changed-file shape and package metadata.

The guard flags a pull request when any of these mechanical predicates match:

1. `pyproject.toml` deletes or changes the `[project]` `name` or `version`.
2. The repository root gains `solution*.py` or `test_solution*.py`.
3. The complete changed-file set is only `pyproject.toml` plus
   `solution*`/`test_solution*` files, including files under `tests/`.

It deliberately does **not** judge implementation quality, issue relevance, or
whether a contributor is acting in good faith. The purpose is to make a
repeatedly suspicious shape cheap to notice without making a content claim that
requires human review.

### What to inspect after a hit

1. **Read the whole diff**, including the PR description and issue reference.
2. **Check package identity first.** Confirm that the original `[project]`
   `name` and `version` are still present. A replacement or truncated
   `pyproject.toml` is not an acceptable way to solve an issue.
3. **Check the changed-file list.** Look for an issue-specific source, test,
   workflow, or documentation change. A root stub plus a generic test is not
   evidence of a fix.
4. **Run the issue's acceptance commands** on the contributor's actual files;
   do not treat the guard's label as a test result.
5. **Choose the human action.** Ask for a focused revision when the work is
   salvageable; close the PR with a brief explanation when it is only a
   template submission; remove the label when the shape is justified and the
   implementation is real.

The workflow posts at most one comment containing the matched predicates and
commands for reproducing the check. It never closes a PR automatically.

### Local reproduction

The decision is a pure function with unit tests:

```bash
pytest -q tests/test_bounty_claim.py
python3 scripts/bounty_claim.py \
  --changed-files /tmp/changed-files.txt \
  --base-pyproject /tmp/base-pyproject.toml \
  --head-pyproject /tmp/head-pyproject.toml
```

To verify the mechanical rule itself, the mutation test disables the
file-shape predicate and confirms that the synthetic three-file template case
stops matching. A real PR such as the documentation/i18n change in #2065 is a
negative fixture: it changes four issue-specific files and must not be flagged.

## Advisory checks

Other automated checks may provide risk or quality information. Treat those as
triage inputs; DCO, security, and the repository's required tests remain the
actual merge requirements.
