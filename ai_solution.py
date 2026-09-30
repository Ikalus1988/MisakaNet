To address the questions, I'll create a lesson that covers both issues.

# Using Swift-format: Diagnostics and Source Path

## Problem

When using Swift-format, which diagnostics require editing the source, and what are the correct options for specifying the source?

## Domain

Programming, Swift, Swift-format.

## Problem

1. Which Swift-format diagnostics require a source edit after formatting?
2. What is the correct way to specify the source when using Swift-format lint?

## Root Cause

1. Some Swift-format options require explicit changes to the source code after formatting.
2. The `--path` option expects a file, not a directory.

## Fix

1. Use `swift-format --strict` or `--use-lexicographic-ordered-dictionary-keys` to enforce specific rules.
2. Use `--source-directory` for directories and `--path` for files.

## Verification

Run the following commands:

```bash
swift-format --help
```

Expected output includes the options and their descriptions.

```bash
swift-format --source-directory .
```

This command should format all Swift files in the current directory.

```bash
swift-format --path example.swift
```

This command should format the specified file.

---

```bash
swift-format --help
```

Output:

```
Usage: swift-format [options]

Options:
  --strict             Use the strict formatting rules.
  --use-lexicographic-ordered-dictionary-keys
                        Order dictionary keys lexicographically when possible.
  --source-directory
                        The directory containing the source files.
  --path                The path to a single source file.
```

```bash
swift-format --source-directory .
```

This command formats all Swift files in the current directory.

```bash
swift-format --path example.swift
```

This command formats the specified Swift file.