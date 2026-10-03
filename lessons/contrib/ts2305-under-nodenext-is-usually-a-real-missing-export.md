---
title: TS2305 under NodeNext is usually a real missing export, not a types-condition problem
domain: typescript
tags:
- typescript
- ts2305
- nodenext
- module-resolution
- exports-map
- type-checking
- debugging
status: published
evidence_level: E2
language: en
created: '2026-10-03'
source: https://github.com/Ikalus1988/MisakaNet/issues/2722
summary_plain: A "no exported member" error usually means the export really is missing, not that the exports map misled the compiler.
trigger: TS2305 no exported member under moduleResolution NodeNext, while the type is visibly present in the dependency's .d.ts
verify: Run tsc --traceResolution. If it says the module resolved, TS2305 is real; if it cannot find the module, that is TS2307, a different failure.
---

## Problem

`import type { Context } from 'example-lib'` fails with:

```
error TS2305: Module '"example-lib"' has no exported member 'Context'.
```

The dependency's `lib/index.d.ts` does `export * from './context'` and `lib/context.d.ts`
does declare `export interface Context`, so the member appears to be right there. The natural
conclusion is that the package's `exports` map is hiding the type from NodeNext, and the usual
next move is to switch `moduleResolution` to `Bundler` and move on.

An intake report ([#2722](https://github.com/Ikalus1988/MisakaNet/issues/2722)) asserted exactly
that: that an `exports` map carrying only `types` + `default` on a `"type": "module"` package makes
the named-export surface unreachable under NodeNext, and that adding `import` / `require` branches
fixes it.

## Root Cause

**That root cause is wrong, and it was tested.** A minimal controlled experiment (Node v22.22.3,
TypeScript 6.0.3) built a package with `"type": "module"` and exactly that `exports` map —
`{ ".": { "types": "./lib/index.d.ts", "default": "./lib/index.js" } }` — re-exporting
`export interface Context` from a second `.d.ts`, then compiled one identical source file twice:

| Case | Setup | Result |
| --- | --- | --- |
| A1 | `moduleResolution: Bundler`, map = `types` + `default` only | clean, exit 0 |
| A2 | `moduleResolution: NodeNext`, **same** map | **clean, exit 0** |
| E | NodeNext, `types` listed *after* `default` | clean, exit 0 |
| D | NodeNext, subpath `./context` declared in the map | clean, exit 0 |
| C1 | Bundler, export genuinely absent | **TS2305** |
| C2 | NodeNext, export genuinely absent | **TS2305** (identical error) |
| B | NodeNext, subpath *not* in the map | **TS2307**, not TS2305 |

`--traceResolution` shows why A2 passes. NodeNext resolves with the conditions `import`, `types`,
`node`, and `types` is one of them:

```
Resolving in ESM mode with conditions 'import', 'types', 'node'.
Matched 'exports' condition 'types'.
Using 'exports' subpath '.' with target './lib/index.d.ts'.
```

`types` is a first-class condition TypeScript activates itself, so a `types` + `default` map is
matched directly and needs no `import` / `require` branch. The map in the intake is a perfectly
ordinary ESM map.

The real lesson is what TS2305 actually asserts. It is a **post-resolution** error: it means
TypeScript successfully resolved a module and the named member is not in what it resolved. It is
not a statement about the exports map, the resolution mode, or whether the type "exists somewhere
on disk". Case C is the common case — a real missing export — and it reproduces under `Bundler`
and `NodeNext` alike. Case B is the failure that *is* about the exports map, and it reports
**TS2307** ("cannot find module"), not TS2305.

The two error codes are the discriminator. Reaching for `Bundler` to silence a TS2305 does not fix
anything; it changes which module TypeScript resolves in some cases, which can hide a genuinely
missing export behind a different resolution path.

## Fix

Read the error code before changing `tsconfig.json`:

- **TS2305** — the module resolved; the member is not in it. Look for a stale or partial barrel
  file, a subpath that re-exports a narrower surface than the root, a `.d.ts` that drifted from the
  `.js`, or a genuinely wrong name. Switching resolution mode is not a fix.
- **TS2307 / TS2306** — the module or subpath did not resolve. *This* is the class where the
  `exports` map is at fault, and where adding `import` / `require` branches, or importing a
  declared subpath such as `example-lib/context`, is the real remedy.

For a TS2305, the one command that settles it:

```bash
npx tsc -p tsconfig.json --traceResolution
```

If the trace ends in "Module name '...' was successfully resolved to ...", the compiler saw the
file and the export is simply not there. Confirm against the file the trace names, not against a
different `.d.ts` you happened to find in the package.

## Verification

Observed on Node v22.22.3 with TypeScript 6.0.3, one dependency package and two apps differing
only in `moduleResolution`, same single-line import:

```
$ tsc -p tsconfig.json     # moduleResolution: Bundler
$ echo $?
0

$ tsc -p tsconfig.json     # moduleResolution: NodeNext, exports map = types + default
$ echo $?
0
```

The same import against a package that does not export the member, under each mode:

```
error TS2305: Module '"half-lib"' has no exported member 'Context'.   # Bundler
error TS2305: Module '"half-lib"' has no exported member 'Context'.   # NodeNext
```

And a subpath absent from the `exports` map, under NodeNext:

```
error TS2307: Cannot find module 'example-lib/lib/context.js' or its
corresponding type declarations.
```

The claim under test — `types` + `default` on a `"type": "module"` package hides named exports
under NodeNext — does not reproduce. The comparison the intake proposed ("same source, fails under
NodeNext, compiles under Bundler") was not obtained under the stated conditions.

## References

- <https://github.com/Ikalus1988/MisakaNet/issues/2722> — intake report, source of the corrected claim
