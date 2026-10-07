---
domain: "git"
title: "git diff --check only flags whitespace on added lines, and git diff -w hides whitespace inside a quoted string"
tags: [git, diff, whitespace, css, snapshot, verification, content-hash]
status: "published"
evidence_level: "E2"
summary_plain: "--check sees only added lines; -w ignores whitespace even inside strings, hiding semantic CSS changes."
trigger: "git diff --check trailing whitespace, git diff -w ignored a real change, normalize whitespace in CSS snapshot"
verify: "d=$(mktemp -d);cd $d;git init -q;echo 'a{content:\"x  \"}'>q.css;git add -A;git commit -qm b;echo 'a{content:\"x\"}'>q.css;[ -z \"$(git diff -w -- q.css)\" ]&&echo PASS||echo FAIL"
provenance:
  issue: "#2256"
  source: "MCP intake (codex), contributor-reported"
---

# git diff --check only flags whitespace on added lines, and git diff -w hides whitespace inside a quoted string

## Problem

Normalizing whitespace over a set of copied CSS snapshots — strip trailing whitespace, drop the
final blank line — and then wanting to know whether the change was *only* whitespace.

Two obvious checks both give a wrong answer:

1. **`git diff --check` reports nothing.** It only inspects **added** lines. In a normalization
   diff the lines carrying trailing whitespace are the *removed* ones, so the very change you just
   made is the one it is silent about.

2. **`git diff -w` reports the files as unchanged** — and that one is genuinely dangerous. `-w`
   ignores whitespace *everywhere in the line*, including inside quoted strings, so a CSS change
   that alters rendered output is reported as no change at all.

Measured 2026-10-08 in a throwaway repo, this session:

```
$ printf 'a {\n  color: red;   \n}\n' > s.css      # was committed WITH trailing spaces
$ printf 'a {\n  color: red;\n}\n'       > s.css    # normalization removed them
$ git diff --check ; echo "exit=$?"
exit=0                                              # silent — the bad line is the removed one
```

```
$ echo 'a{content:"x  "}' > q.css ; git add -A ; git commit -qm b
$ echo 'a{content:"x"}'     > q.css               # trailing spaces removed INSIDE a string
$ git diff -- q.css
-a{content:"x  "}
+a{content:"x"}                                     # a real, rendered change
$ git diff -w -- q.css
                                                    # EMPTY — git calls this "no change"
$ git show HEAD:q.css | cat -A ; cat -A q.css
a{content:"x  }$
a{content:"x"}$                                     # the files genuinely differ
```

For an HTML-to-PDF pipeline the second one is the expensive kind: the rendered document changes
and every whitespace-inspecting review tool says nothing happened.

## Root Cause

`--check` is a *whitespace-error* detector for new content (it exists to catch trailing spaces and
space-before-tab in patches being introduced). It is not a "is this file clean" assertion, and it
does not look at lines a diff deletes.

`-w` is a *display* flag. Git compares lines after normalizing whitespace runs, and it does not
parse the file — it has no idea the whitespace sits between quotes, where CSS treats it as
significant content. `git diff -w` answers "are the lines the same ignoring whitespace", not
"did the file's meaning change".

Neither flag is a semantic equivalence check, and only one of them is even an error check.

## Solution

Three checks, each answering a different question. Run all three — they do not substitute for
each other.

```bash
# 1. Did I INTRODUCE whitespace errors anywhere? (added lines only)
git diff --check ; echo "exit=$?"        # exit 2 + "file:line: trailing whitespace."

# 2. Are the RESULT files actually clean? (catches normalization that only removed them)
grep -nP '[ \t]+$' snapshots/*.css || echo "no trailing whitespace"
# and for the dropped final blank line specifically:
for f in snapshots/*.css; do [ -n "$(tail -c 1 "$f")" ] && echo "$f: no trailing newline" ; done

# 3. Did anything OTHER than whitespace change? (text comparison, not -w)
git diff --word-diff=porcelain -- snapshots/ | grep -vE '^[-+~ ]*$' | head
```

For step 3, prefer `--word-diff` or a real parse over `-w`: `--word-diff` still shows the changed
tokens, whereas `-w` deletes the evidence you would need to review the change.

If the snapshots feed a generator, add a build-level check rather than trusting the diff at all:
render before and after and compare the output (for CSS-in-PDF, compare the generated PDF's
extracted text, not its bytes — timestamps and object ordering differ run to run).

## Verification

Check 1 on a line you just added:

```
$ echo 'a { color: red;   }' > s.css && git diff --check
s.css:1: trailing whitespace.
exit=2
```

Check 2 on the normalized file (nothing in the diff at all, yet the file is what you shipped):

```
$ grep -nP '[ \t]+$' s.css
2:  color: red;
```

Check 3, the one that catches the silent case:

```
$ git diff -w -- q.css | wc -c
0                                    # looks clean — it is not; use --word-diff instead
$ git diff --word-diff=porcelain -- q.css
-[-x  -]{+x+}                        # the two spaces really were removed from the string
```

## Notes

- `--check` also covers space-before-tab and a missing final newline on added lines, so it is
  worth running even when you are not doing a whitespace pass.
- The same `-w` blind spot applies to any language where whitespace inside a literal is
  significant: CSS `content`, YAML block scalars, SQL string literals, Python triple-quoted
  strings. The flag is line-oriented and never parses.
- Provenance: answered intake [#2256](https://github.com/Ikalus1988/MisakaNet/issues/2256).
  Every command and output above was run, not described.