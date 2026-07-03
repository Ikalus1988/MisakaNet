# Troubleshooting FAQ

This guide covers common issues encountered by new users and contributors, structured by symptom, underlying cause, and step-by-step resolution.

---

## 1. Search Returns Nothing
* **Symptom:** Submitting a search query yields empty result pages or zero entries despite relevant content existing.
* **Cause:** The local search index has desynchronized or failed to complete its initial background crawl.
* **Fix:** Force a database index rebuild by navigating to Settings > Cache Management and clicking **Rebuild Global Search Index**, or clear your browser cache and refresh.

## 2. Lesson Not Found After Adding
* **Symptom:** A newly created or imported lesson module does not appear anywhere within the active curriculum tree layout.
* **Cause:** The main registration matrix metadata file wasn't updated, meaning the core engine is unaware the lesson path exists.
* **Fix:** Open `docs/registration-channels.md` or your local manifest configuration, append your unique lesson path id to the active register array, and save.

## 3. DCO Check Fails
* **Symptom:** Your submitted Pull Request triggers an automated block stating "Developer Certificate of Origin (DCO) check failed".
* **Cause:** Your local Git commits lack a cryptographic authorization signature string confirming ownership rights.
* **Fix:** When committing changes via CLI, always use the `-s` flag (e.g., `git commit -s -m "your message"`). If modifying via the web UI, ensure your GitHub email matches your local account sign-off credentials.

## 4. Quality Score Too Low
* **Symptom:** Automated code analysis workflow flags your contribution branch with a structural degradation warning or a low quality metrics indicator.
* **Cause:** The code contains syntax formatting violations, missing docstrings, or unresolved duplicate validation logic blocks.
* **Fix:** Run your local code formatting engine commands (like `black` or `ruff`) before committing, add descriptive inline comments to complex logic pipelines, and ensure your test coverage passes cleanly.

## 5. Windows Encoding Errors
* **Symptom:** System crash logs throw fatal character set errors (such as `UnicodeDecodeError`) when executing scripts or parsing files on Windows terminals.
* **Cause:** Windows environments default terminal operations to localized formats like `CP1252` instead of native multi-language `UTF-8` rendering.
* **Fix:** Explicitly define the standard file system variable in your terminal environment by executing `set PYTHONUTF8=1` in your Command Prompt before initializing any platform execution scripts.
