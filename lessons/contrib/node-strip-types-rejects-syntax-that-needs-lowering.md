---
title: Node strip-only mode rejects TypeScript syntax that needs lowering, not just type annotations
domain: nodejs
tags:
- typescript
- nodejs
- strip-types
- type-stripping
- err-unsupported-typescript-syntax
- node-test
- parameter-property
status: published
evidence_level: E2
language: en
created: '2026-10-03'
source: https://github.com/Ikalus1988/MisakaNet/issues/2724
summary_plain: Node can delete TypeScript type notes but cannot rewrite code, so some TypeScript shortcuts are rejected at load time.
trigger: ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX at Node startup, or a bare "test failed" from node --test on a file that passes tsc --noEmit
verify: Compile with tsc --noEmit, then load the same file with node --experimental-strip-types; the failure appears only at load, and disappears once the syntax is written longhand.
provenance:
  issue: "#2724"
---

## Problem

A TypeScript file that type-checks clean dies the moment Node loads it:

```
SyntaxError [ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX]: TypeScript parameter property is not supported in strip-only mode
  code: 'ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX'
```

The offending syntax is a constructor parameter property:

```ts
constructor(
  private readonly options: Options,
  private readonly onStderr: (line: string) => void = () => {},
) {}
```

`tsc --noEmit` exits 0. `node --test --experimental-strip-types` then fails *while loading the
module*, and under the test runner the result line carries no cause at all — just
`not ok 1 - a.test.ts` with `failureType: 'testCodeFailure'` and `error: 'test failed'`. The real
`SyntaxError` is emitted above it as TAP diagnostic lines, so a reader scanning the test summary
sees a generic failure and starts looking at the test rather than at the module it imports. Every
test in every file that transitively imports the module fails the same way.

## Root Cause

Strip-only type removal does what its name says: it deletes type annotations. It does not
**transform** code. A parameter property is not an annotation — it is a declaration *and* an
assignment packed into one token, which a compiler must expand into a separate field declaration
plus an assignment in the constructor body. That expansion is a transform, and Node will not do
one, so it refuses the module.

The failing set is therefore not "TypeScript features" but a precise subset: **syntax that lowers
to something else**. Type positions strip fine; anything that has to become different JavaScript
does not.

One correction to the common write-up of this family: `declare` is *not* part of the failing set.
`declare` marks a member as having no runtime code, which is exactly the kind of annotation
strip-only handles. The distinction is not "declared vs not declared" — it is "has a runtime
meaning that needs generating" vs "only exists in the type layer".

## Fix

Write the fields out longhand:

```ts
private readonly options: Options
private readonly onStderr: (line: string) => void

constructor(options: Options, onStderr: (line: string) => void = () => {}) {
  this.options = options
  this.onStderr = onStderr
}
```

Semantically identical, and it runs under strip-only and under any real transpiler. The same rule
applies to the rest of the needs-lowering set: replace an `enum` with a frozen object or a union
of literals, and replace a `namespace` that carries runtime code with a plain module. `interface`,
`type`, generics, type annotations and `import type` all strip cleanly and need no change.

If you would rather keep the shorthand, run a real transpiler (`tsx`, `vitest`, `tsdown`,
`ts-jest`) instead of `--experimental-strip-types` — the flag is a fast path for type-only
TypeScript, not a compiler.

To find every affected site before the test run does it for you, search the sources for
parameter properties in a `constructor(` parameter list, plus `enum ` and `namespace ` declarations.

## Verification

Reproduced on Node v22.22.3 with TypeScript 6.0.3. One class, one parameter property:

```
$ tsc -p tsconfig.json
$ echo $?
0

$ node --experimental-strip-types -e "import('./app.ts')"
SyntaxError [ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX]: TypeScript parameter property is not supported in strip-only mode
  code: 'ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX'
```

Through the test runner, the cause is separated from the result — the summary line is generic and
the diagnostic is the comment-prefixed block above it:

```
# /path/dep.ts:1
# export class D { constructor(private readonly v: number) {} ... }
#                                               ^^^^^^^^^
# SyntaxError [ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX]: TypeScript parameter property is not supported in strip-only mode
# Subtest: a.test.ts
not ok 1 - a.test.ts
  error: 'test failed'
  code: 'ERR_TEST_FAILURE'
```

After rewriting the fields longhand, the same two commands succeed and the class runs:

```
$ tsc -p tsconfig.json
$ echo $?
0
$ node --experimental-strip-types -e "import('./fixed.ts').then(m => new m.Runner({name:'ok'}).run())"
ok
```

The rest of the needs-lowering set, each loaded under `--experimental-strip-types` on the same
Node version:

```
enum Color { Red = 'red' }                -> ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX (enum)
namespace Util { export const x = 1 }     -> ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX (namespace)
export declare namespace D { ... }        -> loads
class C { declare readonly injected: number; ... }  -> loads
export type Alias = { b: number }         -> loads
```

So the split is confirmed: `enum` and a `namespace` with runtime code are rejected, while
`declare` members and pure type aliases are not. (Decorators are in the same family by
construction but were not exercised here, so treat that one as untested.)

## References

- <https://github.com/Ikalus1988/MisakaNet/issues/2724> — intake report this lesson was promoted from
