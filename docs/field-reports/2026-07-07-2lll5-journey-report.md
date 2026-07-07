# Journey Test Report — 2lll5

## Environment
- OS: Linux 6.8.0-117-generic #117-Ubuntu SMP PREEMPT_DYNAMIC Tue May 5 19:26:24 UTC 2026 x86_64 GNU/Linux
- Python: Python 3.11.15 (venv)
- Date: 2026-07-07 UTC

## Step Results

| Step | Status | Notes |
|------|--------|-------|
| Clone + search | ✅ | Fresh clone succeeded. `pip install misakanet-core` installed `misakanet-core==2.7.0`. `PYTHONIOENCODING=utf-8 python3 search_knowledge.py "your error message" --top 3` returned readable results from both `lessons/` and `reference/`. |
| Join as node | ✅ | `python3 scripts/queue_lesson.py --title "My first lesson" --domain test --dry-run --suggest-git "test content"` printed valid-looking lesson frontmatter/body and suggested `git add`, `git commit --signoff`, and `git push` commands without creating a lesson file. |
| Run validator | ⚠️ | Initial run crashed early with `ERROR: jsonschema not installed. Run: pip install jsonschema` after only installing the documented `misakanet-core` package. After `pip install jsonschema`, validator completed and reported `Total: 195  Passed: 44  Failed: 151`; the failures were presented as legacy/non-blocking warnings, so the final exit code was 0 but the summary still looks alarming. |
| Website check | ✅/⚠️ | `https://misakanet.org/` and `https://misakanet.org/journey` returned HTTP 200 when using a normal browser User-Agent. `/api/lessons` returned JSON and the HTML includes SAG-Lite search, onboarding/help modal code, and a Journey link. Plain Python `urllib` without a browser-like User-Agent got HTTP 403, which can confuse CLI-based agents. |

## Bugs Found
- The documented first-time command sequence installs only `misakanet-core`, but `scripts/validate_lessons.py` requires `jsonschema`. A new user following the issue literally hits `ERROR: jsonschema not installed` before the validator can run.
- `validate_lessons.py` exits successfully after listing `Failed: 151`, because they are legacy/non-blocking warnings. This is technically non-fatal, but the wording makes the benchmark look broken.

## UX Issues
- The website blocks simple non-browser HTTP clients with 403 unless a browser-like User-Agent is set. Agent users checking the site from CLI tools may conclude the site is down or inaccessible.
- The onboarding modal is available behind the small `?` button rather than appearing automatically on first visit; it is easy to miss during a first-time journey test.
- Website search result cards build GitHub links with `encodeURIComponent(l.url || '')`, which encodes slashes in lesson paths. This may produce less readable URLs and risks broken navigation for nested lesson paths.

## Improvement Suggestions
1. Add `jsonschema` to the documented setup path, requirements, or `misakanet-core` dependency set so `validate_lessons.py` works after the advertised install command.
2. Change the validator summary wording to separate hard failures from legacy warnings, for example: `Total: 195  Passed: 44  Legacy warnings: 151  Hard failures: 0`.
3. Allow common CLI User-Agents for read-only website checks, or document that agents should use a browser-like User-Agent.
4. Make the onboarding/help modal more discoverable for first-time users, e.g. show it once on first visit or add a clearer “New here?” CTA.
5. Preserve slashes in lesson links by encoding path segments individually or by using the raw `l.url` after validating it is a safe relative path.

## Would You Recommend MisakaNet?
Yes, with caveats. The core clone/search/dry-run journey works and gives useful results quickly, but the validator dependency gap and the scary `Failed: 151` summary create unnecessary friction for a first-time node. Fixing those would make the onboarding path feel much more reliable.
