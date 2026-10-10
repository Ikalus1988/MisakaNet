# Changelog

## [Unreleased]

### Added
- `scripts/run_node.js` — Node.js script executor that writes scripts to temp files instead of using `node -e "..."`, avoiding PowerShell's double-escaping layer.
- `scripts/harness_executor.js` — DSH harness execution layer with PowerShell version checks, safe SQL query builder (single-quote string literals), and file-based script execution.
- `scripts/harness.ps1` — PowerShell 5.1-compatible harness script with `Exec-NodeScript`, `Exec-SQLQuery`, and environment diagnostics. Uses `powershell.exe` explicitly; saves .ps1 files with UTF-8 BOM.

### Fixed
- **Inline command double-escaping trap** (#3111): All complex commands now written to `.js` / `.ps1` files before execution. This bypasses PowerShell's lexical analysis layer entirely, eliminating:
  - Quote-count mismatches causing `Unexpected token` parse errors
  - `$variable` premature expansion turning JS variables into empty strings
  - `\U \A \L \T \x` escape sequence consumption by PS before JS engine
  - Silent failures (exit code 0 but wrong path / empty data)
- **SQL double-quote literals**: String values now use single quotes; double quotes are reserved for SQL identifiers per standard.
- **PowerShell version mismatch**: Harness now detects whether `pwsh` (7.x) or `powershell.exe` (5.1) is the actual runner and adjusts behavior accordingly.

### Changed
- Replaced all `node -e "..."` calls with file-based `runNodeScript()` execution.
- Replaced all `powershell -Command "..."` calls with `.ps1` file-based execution.
- Added `$PSVersionTable` diagnostic on harness startup.
