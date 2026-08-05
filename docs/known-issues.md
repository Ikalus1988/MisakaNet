# Known Issues

Pre-existing test failures unrelated to any specific release.

## Test suite (as of v2.14.0)

Total: 432 passed, 10 failed, 1 skipped

### test_graphql.py (8 failures)

**Cause:** Missing `graphql-core` dependency in test environment.

```
FAILED tests/test_graphql.py::TestGraphQLSchema::test_lessons_query - ImportError
FAILED tests/test_graphql.py::TestGraphQLSchema::test_lesson_by_id - ImportError
FAILED tests/test_graphql.py::TestGraphQLSchema::test_search_query - ImportError
FAILED tests/test_graphql.py::TestGraphQLSchema::test_search_with_domain_filter - ImportError
FAILED tests/test_graphql.py::TestGraphQLSchema::test_search_with_limit - ImportError
FAILED tests/test_graphql.py::TestGraphQLSchema::test_empty_search - ImportError
FAILED tests/test_graphql.py::TestGraphQLSchema::test_introspection - ImportError
FAILED tests/test_graphql.py::TestGraphQLSchema::test_lesson_not_found - ImportError
```

**Fix:** Install `graphql-core` or skip tests when dependency is absent.

### test_ci_self_heal.py (1 failure)

**Cause:** Retry backoff timing test flaky in CI environment.

```
FAILED tests/test_ci_self_heal.py::TestRetryBackoff::test_succeeds_after_2_failures
```

**Fix:** Increase timeout tolerance or mock time.sleep.

### test_triage_feedback.py (1 failure)

**Cause:** Keyword-based classifier returns `noise` instead of `bug-report` for MisakaNet-specific terms.

```
FAILED tests/test_triage_feedback.py::TestTriageFeedback::test_classify_bug_report
```

**Fix:** Update classifier keywords or adjust test expectations.
