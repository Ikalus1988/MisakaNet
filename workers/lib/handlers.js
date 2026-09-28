/**
 * Shared constants for the worker bundle: the GitHub API base, the repository, and the raw-data base.
 *
 * It was called a "handler" module and carried a copy of the search handler, the lesson fetcher
 * (`fetchLessonContent`), `fetchFromGitHub`, `fetchPublicJson`, `getWithCache` and a BM25 tokenizer,
 * "extracted from register-proxy-sw.js for maintainability". None of them were imported: the worker
 * destructures `{ GITHUB_API, REPO, PUBLIC_DATA_BASE }` from here and keeps its own implementations,
 * so every copy in this file was a fork of live code that no test could reach — and the forks drifted
 * exactly as forks do:
 *
 *   * `fetchFromGitHub(token, path, ref = "data")` held the default `register-proxy-sw.js` had removed
 *     for #1820 (the `data` branch does not carry `data/counter.json`), and ignored `ref` entirely —
 *     the URL was always `PUBLIC_DATA_BASE`;
 *   * `fetchLessonContent` still interpolated an unvalidated path into the contents API, i.e. the
 *     arbitrary-repository-read and `internal_error`-for-a-404 that B35 fixes in the live copy, with
 *     none of the fix and none of the guard.
 *
 * Measured 2026-09-25: nothing outside this file referenced any of them, which is precisely why a
 * "keep the copies in sync" rule is not worth writing — the rule is that there are no copies. The
 * three constants below are the whole contract; `tests/test_worker_github_fallbacks.py` fails if a
 * function reappears here.
 */

const GITHUB_API = "https://api.github.com";
const REPO = "Ikalus1988/MisakaNet";
const PUBLIC_DATA_BASE = "https://raw.githubusercontent.com/Ikalus1988/MisakaNet/main/data";

export {
  GITHUB_API,
  REPO,
  PUBLIC_DATA_BASE,
};
