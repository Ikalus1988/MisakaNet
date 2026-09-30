```swift
## Problem

When using Swift-format, which diagnostics require editing the source, and what is the correct way to specify the source?

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

swift-format --help

Expected output includes the options and their descriptions.

swift-format --source-directory .

This command should format all Swift files in the current directory.

swift-format --path example.swift

This command should format the specified file.
```