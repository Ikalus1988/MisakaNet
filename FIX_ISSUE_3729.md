# Fix for #3729

Based on the issue description, this is not a code bug requiring a patch, but a **content/documentation gap** where the retrieval system (`misakanet_search`) failed to find existing answers for two specific user questions (#3611 and #3657).

The "bug" is that the FAQ database (D1) lacks entries for these specific failure modes, causing `no_match` results. The "fix" is to generate and post the missing answers.

### Bugfix Summary
**Issue:** Retrieval path returns `no_match` for questions #3611 (Supercharge launch issue) and #3657 (SkyComputerUseService crash diagnosis) because no corresponding FAQ entries exist in the production database.
**Root Cause:** These specific scenarios were not covered by existing lessons or FAQ entries, and the provenance gate prevents generating unverified answers.
**Fix:** Manually observe/determine the correct answers for both questions and post them as comments on the respective issues. The `sync-question-answers.yml` workflow will then ingest these comments into D1, allowing `misakanet_search` to return them as `type: faq` hits in the future.

### Patch Summary
No code patch is required. The deliverable is **content**:
1.  **For Issue #3611:** Post a comment explaining the observed behavior/fix for "Supercharge from Setapp remains running but does not recreate".
2.  **For Issue #3657:** Post a comment explaining the supported diagnostic step to identify a "SkyComputerUseService crash".

*Note: As per the issue instructions, any answer must be based on observed facts or clearly labeled as a hypothesis. If the exact cause is unknown, the comment must state this plainly to maintain provenance integrity.*