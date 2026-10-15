---
title: "require_relative Resolves Against the Requiring File, Not the Working Directory"
domain: "ruby"
status: "published"
evidence_level: "E1"
tags:
  - "ruby"
  - "require-relative"
  - "loaderror"
  - "path-resolution"
  - "working-directory"
  - "troubleshooting"
summary_plain: "A require_relative LoadError means the file is missing beside the script, so cd or an absolute path cannot fix it."
trigger: "cannot load such file -- lib/tui (LoadError) OR require_relative LoadError OR ruby shell helper cannot find lib"
verify: 'Run test -d "$(dirname try.rb)/lib/tui": when it fails, ruby try.rb raises LoadError from every cwd, so cd and File.expand_path cannot fix the load.'
supersedes: "ruby-require-relative-and-docker-port-allocation"
provenance:
  issue: "#2465"
  source: "maintainer correction of lessons/en/ruby-require-relative-and-docker-port-allocation.md; anchors on the official Ruby manual and its C implementation"
---

# require_relative Resolves Against the Requiring File, Not the Working Directory

> **Correction notice.** This lesson supersedes
> `lessons/en/ruby-require-relative-and-docker-port-allocation.md`, which now carries
> `status: superseded`. That lesson's Root Cause line was already right, but its Solution
> told the reader to `pwd`, `cd` into the script's directory, and rewrite the call as
> `require File.expand_path(File.join(File.dirname(__FILE__), 'lib', 'tui'))`. None of
> those three steps can repair the failure it describes, because the working directory is
> not an input to `require_relative` at all. The Docker-port half of the retired lesson is
> unaffected and now lives in
> `lessons/contrib/port-already-allocated-find-and-free-the-holder.md`.

## Problem

A Ruby helper script — for example a `try.rb` that boots a terminal UI — fails during
startup with:

```text
cannot load such file -- lib/tui (LoadError)
```

Ruby itself is installed and working, and the same `require_relative "lib/tui"` line
behaves in another project, so the failure presents itself as a "wrong directory" problem.
It is not one: the process's working directory never enters the lookup.

## Root Cause

`require_relative` anchors its lookup to **the file that contains the call**, never to the
process's current working directory. The official manual states it directly:

> Ruby tries to load the library named string relative to the directory containing the
> requiring file. If the file does not exist a LoadError is raised.
>
> — <https://docs.ruby-lang.org/en/3.3/Kernel.html#method-i-require_relative>

The C implementation of the same method derives its base from `rb_current_realfilepath()`,
i.e. the real path of the calling file. It is `load` and plain `require` that consult the
working directory and `$LOAD_PATH`; `require_relative` exists so that a library can be found
without either.

The `LoadError` therefore reports exactly one fact: **there is no `lib/tui` tree next to the
file that contains the `require_relative` line.** The shell's cwd, `$LOAD_PATH`, `RUBYLIB`,
and Bundler are not part of that lookup.

## Solution

### Step 1 — Diagnose the layout, not the cwd

Ask whether the tree actually exists beside the requiring file:

```bash
# Replace try.rb with the file that contains the require_relative line.
ls -d "$(dirname try.rb)/lib/tui"
```

If that path is missing, the load cannot succeed no matter where you stand. If it exists,
suspect the call site: a `require_relative` inside a file that itself lives in a
subdirectory (for example `bin/try.rb` requiring `lib/tui`) resolves one level deeper than
people expect, so the correct string may be `require_relative "../lib/tui"`.

### Step 2 — Fix the install layout or the call site

Choose the one that matches the cause the diagnosis found:

- **The `lib` tree is not installed where the script lives.** Move or copy it next to the
  requiring file, or ship the code as a gem and `require` it by name — plain `require` is
  the form that does consult `$LOAD_PATH`.
- **The call site is in the wrong directory.** Correct the relative path from *that file*,
  for example `require_relative "../lib/tui"`.
- **The tree genuinely cannot move.** Then you do not want relative resolution at all; put
  its parent on `$LOAD_PATH` and use plain `require` instead:

  ```ruby
  $LOAD_PATH.unshift(File.expand_path("../lib", __dir__))
  require "tui"
  ```

### Step 3 — Two "fixes" that cannot work

**`cd` into the script's directory is not a fix.** Because the anchor is the file, standing
in that file's directory changes nothing about the lookup. When `lib/tui` is absent, the
`LoadError` is identical from every working directory; a `cd` only adds a step that appears
to help in the one case where the script would have run anyway.

**`require File.expand_path(File.join(File.dirname(__FILE__), 'lib', 'tui'))` is not a fix
either.** It is a hand-written spelling of exactly what `require_relative` already does:
`File.dirname(__FILE__)` is the requiring file's own directory, and resolving `lib/tui`
against it supplies the same anchor that `rb_current_realfilepath()` supplies. If
`require_relative "lib/tui"` raises `LoadError`, this line raises the same `LoadError`,
because the file still is not there. The explicit form has legitimate uses — anchoring a
path you then hand to `load`, or building a path for a subprocess — but repairing a missing
tree is not one of them.

## Verification

The check is a directory test beside the requiring file, not a change of directory:

```bash
# Exit status is the whole answer: 0 means the tree is beside the requiring file.
test -d "$(dirname try.rb)/lib/tui"
```

Then run the script twice, once from `/` and once from the script's own directory:

```bash
cd /        && ruby /path/to/try.rb
cd /path/to && ruby try.rb
```

Both invocations must behave identically. If `lib/tui` is absent they raise the same
`LoadError`; if it is present they both load. A result that changes with the shell's cwd
means the failing call is a plain `require` elsewhere in the dependency chain, not the
`require_relative` under investigation.

## Notes

- Evidence is document-level (**E1**): the semantics above are quoted from the official
  manual and its C implementation, and no Ruby interpreter was available on the machine
  that wrote this lesson. This is not a runtime reproduction, and it should not be read as
  one.
- The original report came through issue #2465, where the maintainer's answer says the same
  thing in one paragraph. This lesson exists because the retrieval index ranks the retired
  `cd` advice highly for `require_relative LoadError` and for
  `cannot load such file -- lib/tui (LoadError)`, so an agent that follows it spends a turn
  and remains broken.
- Docker port conflicts: see
  `lessons/contrib/port-already-allocated-find-and-free-the-holder.md`.
