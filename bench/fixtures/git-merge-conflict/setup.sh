#!/usr/bin/env bash
set -euo pipefail

workdir=${1:?usage: setup.sh WORKDIR}
rm -rf -- "$workdir"
mkdir -p "$workdir/repo"

git -C "$workdir/repo" init -q
git -C "$workdir/repo" config user.name "Fixture Author"
git -C "$workdir/repo" config user.email "fixture@example.invalid"
# The base branch is whatever `git init` just created — *not* `master`/`main`. `git init` honours
# `init.defaultBranch`, so on a machine configured with `dev`, `trunk` or anything else the old
# `switch master || switch main` died with `fatal: invalid reference: main` before creating any
# conflict, and the fixture reported "setup failed" for an environment reason (#2001).
base_branch=$(git -C "$workdir/repo" symbolic-ref --short HEAD)
printf 'original\n' > "$workdir/repo/config.txt"
git -C "$workdir/repo" add config.txt
git -C "$workdir/repo" -c commit.gpgsign=false commit -q -m 'fixture base commit'
git -C "$workdir/repo" switch -q -c conflicting-change
printf 'change from branch\n' > "$workdir/repo/config.txt"
git -C "$workdir/repo" add config.txt
git -C "$workdir/repo" -c commit.gpgsign=false commit -q -m 'conflicting branch change'
git -C "$workdir/repo" switch -q "$base_branch"
printf 'change from base\n' > "$workdir/repo/config.txt"
git -C "$workdir/repo" add config.txt
git -C "$workdir/repo" -c commit.gpgsign=false commit -q -m 'base branch change'
git -C "$workdir/repo" merge conflicting-change >/dev/null 2>&1 || true
