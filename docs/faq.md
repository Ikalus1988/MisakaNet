# FAQ

## Common Issues

### Search returns nothing
**Symptom:** When you run a search, no results are returned.
**Cause:** The search query may be too specific or contain typos.
**Fix:** Try a broader search query or use the `--suggest` flag to get suggestions. If the issue persists, consider contributing a new lesson by running `python3 scripts/queue_lesson.py -t "your title" -d domain "content..."`.

### Lesson not found after adding
**Symptom:** After adding a new lesson, it does not appear in search results.
**Cause:** The lesson may not have been properly indexed or there might be a delay in the indexing process.
**Fix:** Ensure the lesson follows the correct format and has been committed and pushed to the repository. Wait a few minutes and try searching again. If the issue persists, check the CI logs for any errors.

### DCO check fails
**Symptom:** Your commit fails the DCO check.
**Cause:** The commit message does not include the `Signed-off-by:` trailer.
**Fix:** Add the `Signed-off-by:` trailer to your commit message. For detailed instructions, see the [Windows DCO Sign-off Guide](docs/dco-windows.md).

### Quality score too low
**Symptom:** Your PR is rejected due to a low quality score.
**Cause:** The lesson may not meet the quality standards or contains forbidden patterns.
**Fix:** Review the [lesson quality checklist](docs/lesson-checklist.md) and ensure your lesson adheres to the required format and content guidelines. Re-run the quality check with `python3 scripts/check_lesson_quality.py`.

### Windows encoding errors
**Symptom:** You encounter encoding errors on Windows.
**Cause:** Windows uses a different encoding system which may cause issues with certain characters.
**Fix:** Ensure your text editor is set to use UTF-8 encoding. For more detailed troubleshooting, see the [Windows encoding errors guide](docs/secret-scan-windows.md).
