# DSH Plugin Test Fixtures

This directory contains test data and mock fixtures used by the MisakaNet dsh plugin integration test suite.

## Files

| File | Purpose |
|------|---------|
| (reserved) | Placeholder for future test fixtures (e.g., sample lesson JSON, mock MCP responses) |

## Usage

Tests in `*.test.js` may load fixtures from this directory using Node.js `fs` and `path` modules:

```javascript
const path = require('path');
const fixturesDir = path.join(__dirname, 'fixtures');
```

## Adding Fixtures

Add JSON or JavaScript fixture files here for use in tests. Keep fixtures small and self-contained.

## Notes

- The `dsh` plugin integration tests use `mocha` + `chai` for the test framework.
- Most tests rely on the actual `dsh` CLI being installed; without it, tests skip gracefully.
- Performance tests log `KEY=VALUE` artifacts for CI collection.
