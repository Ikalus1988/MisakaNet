---
title: "swift-format rejects directories without --recursive; only some rules are auto-fixed"
domain: development
tags: [swift, swift-format, lint, format, cli, recursive, ci]
status: published
evidence_level: E2
summary_plain: "swift-format needs -r for directories; format --in-place only fixes formatting rules, not linter-only rules"
trigger: "swift-format lint directory error 'is a path to a directory' --recursive"
verify: "swift-format lint -r Sources/ exits 0; format -r --in-place Sources/ fixes formatting rules only"
provenance:
  issue: "#2495"
  source: "MCP intake (codex), contributor-reported"
---

## Problem

Two related swift-format failures:

**Q1 (#2473)** Which diagnostics need a manual source edit after the formatter runs, versus being resolved by `swift-format format --in-place`?

**Q2 (#2495)** For swift-format lint, passing a source directory produces "is a path to a directory" error:

```
Error: 'Sources' is a path to a directory, not a Swift source file.
Use the '--recursive' option to handle directories.
```

## Root Cause

1. **Directory error**: `LintFormatOptions.validate()` in swift-format throws `ValidationError` when any CLI path is a directory and `-r/--recursive` is not set. This applies to **both** `lint` and `format`. Argument validation fails with **exit code 64** before any file is processed.

2. **Auto-fix vs manual**: swift-format rule docs state: "All of these rules can be applied in the linter, but only some of them can format your source code automatically." `format --in-place` rewrites source for **formatting rules** only. **Linter-only rules** are reported by `lint` but never rewritten by `format` — the developer must edit the source. `lint` itself never modifies files.

## Solution

**Directories:** pass `-r` / `--recursive` for both subcommands:

```bash
swift-format lint -r Sources/
swift-format format -r --in-place Sources/
```

Single files need no `-r`: `swift-format lint Sources/Foo.swift`

**Which rules are auto-fixed vs manual:**

Workflow: `format --in-place` first (auto-fix formatting rules), then `lint` to see what remains (linter-only rules need manual edits).

Formatting rules — **auto-fixed** by `swift-format format --in-place` (enabled by default unless noted):
- DoNotUseSemicolons, FileScopedDeclarationPrivacy, FullyIndirectEnum
- GroupNumericLiterals, NoAccessLevelOnExtensionDeclaration
- NoAssignmentInExpressions, NoCasesWithOnlyFallthrough
- NoEmptyTrailingClosureParentheses, NoLabelsInCasePatterns
- NoParensAroundConditions, NoVoidReturnOnFunctionSignature
- OneCasePerLine, OneVariableDeclarationPerLine, OrderedImports
- ReturnVoidInsteadOfEmptyTuple, UseExplicitNilCheckInConditions
- UseLetInEveryBoundCaseVariable, UseShorthandTypeNames
- UseSingleLinePropertyGetter, UseTripleSlashForDocumentationComments
- (disabled by default: AlwaysUseLiteralForEmptyCollectionInit, NoEmptyLinesOpeningClosingBraces, OmitExplicitReturns, UseEarlyExits, UseWhereClausesInForLoops)

Linter-only rules — **require manual source edit** (format never fixes these):
- AlwaysUseLowerCamelCase, AmbiguousTrailingClosureOverload
- AvoidRetroactiveConformances, IdentifiersMustBeASCII
- NoBlockComments, NoPlaygroundLiterals
- OnlyOneTrailingClosureArgument, ReplaceForEachWithForLoop
- SwiftTestingNamingConventions, TypeNamesShouldBeCapitalized
- UseSynthesizedInitializer
- (disabled by default: AllPublicDeclarationsHaveDocumentation, BeginDocumentationCommentWithOneLineSummary, NeverForceUnwrap, NeverUseForceTry, NeverUseImplicitlyUnwrappedOptionals, NoLeadingUnderscores, ValidateDocumentationComments)

**Exit codes** (verified on swift-format 604.0.0):
| Command | Exit |
|---|---|
| `lint`/`format` on a directory without `-r` | 64 (validation error) |
| `lint -r` with remaining linter-only warnings | 0 |
| `lint -r --strict` with remaining warnings | 1 |

## Verification

```bash
brew install swift-format
swift-format --version   # tested on 604.0.0

# Setup
mkdir -p /tmp/sf-demo/Sources
cat > /tmp/sf-demo/Sources/Bad.swift <<'EOF'
import Foundation
import Swift
class badName {
    var x = Array<Int>()
    func foo() -> () {
        if (true) { print("hi") }
    }
}
EOF
cd /tmp/sf-demo

# Q2 repro + fix
swift-format lint Sources
# Error: 'Sources' is a path to a directory ... (exit 64)

swift-format lint -r Sources
# diagnostics for formatting + linter-only rules (exit 0)

# Q1: auto-fix formatting, leave linter-only for manual edit
swift-format format -r --in-place Sources
# Auto-applied: Array<Int>()→[Int](), removed -> (), un-indented, un-parenthesized

swift-format lint -r Sources
# Remaining: TypeNamesShouldBeCapitalized — fix by hand

# strict mode → CI gate
swift-format lint -r --strict Sources; echo $?   # 1 while violations remain
```