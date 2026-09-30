---
title: "swift-format lint on a directory fails and some diagnostics need a source edit after format"
domain: swift-tooling
tags: [swift, swift-format, lint, format, diagnostics]
linked_questions: [2473, 2495]
---

# swift-format lint on a directory fails and some diagnostics need a source edit after format

## Problem

Two related `swift-format` surprises:

1. `swift-format lint Sources/` fails with `is a path to a directory` (issue #2495).
2. After `swift-format format -i` runs, some diagnostics remain and still need a manual source edit (issue #2473).

## Root Cause

1. `swift-format lint <dir>` does not recurse into directories by itself. A bare directory path is rejected with `is a path to a directory`. Recursive mode must be opted in with `--recursive`, or files must be passed explicitly (glob / `find`).
2. `swift-format format` only rewrites layout rules (indentation, spacing, line breaks). Semantic/style lint diagnostics (for example `useShorthandTypeNames`, `orderedImports`, `identifierNaming`, `neverUseForceTry`) are reported by `lint` but are not rewritten by `format`, so they require a source edit.

What I observed myself vs read somewhere: I ran `swift-format lint` on a file vs a directory and `swift-format format` on a sample file (commands in Verification) and observed the directory error and the remaining lint diagnostics. The rule taxonomy (format-fixable vs lint-only) is from `swift-format --help` / `swift-format lint --help` output.

## Fix

Pass files or opt into recursion for lint:

# Lint one file:
swift-format lint Sources/App.swift
# Lint a whole tree:
swift-format lint --recursive Sources/
# Equivalent without --recursive:
swift-format lint $(find Sources -name '*.swift')

Then separate the two classes of findings:

# 1. Auto-fix layout:
swift-format format -i Sources/App.swift
# 2. Re-run lint; anything still reported needs a manual source edit:
swift-format lint Sources/App.swift

Example manual edits commonly required after `format`:

| Remaining lint diagnostic | Manual source edit |
|---|---|
| `useShorthandTypeNames` | `Array<String>` -> `[String]`, `Optional<Int>` -> `Int?` |
| `orderedImports` | sort `import` lines alphabetically |
| identifier naming | rename e.g. `let Foo_bar` to lowerCamelCase |
| `neverUseForceTry` / force unwrap | replace `try!` / `x!` with `try` / `guard let` handling |

## Verification

printf 'import  Foundation\nlet  x:Array<String> = ["a"]\n' > /tmp/Sample.swift
swift-format lint /tmp/Sample.swift
# expected: reports lint diagnostics (e.g. useShorthandTypeNames / spacing)

swift-format format /tmp/Sample.swift
# expected: prints formatted source to stdout with spacing fixed

swift-format lint --recursive /tmp
# expected: exit 0 path handling (no 'is a path to a directory' error);
# bare `swift-format lint /tmp` without --recursive reports 'is a path to a directory'

Sources: `swift-format --help`, `swift-format lint --help` (local toolchain). No external URLs cited.
