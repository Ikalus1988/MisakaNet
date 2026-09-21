#!/usr/bin/env bash
set -euo pipefail

workdir=${1:?usage: setup.sh WORKDIR}
rm -rf -- "$workdir"
mkdir -p "$workdir/repo"

# Pin the initial branch: `git init` honours init.defaultBranch, so a machine configured
# with `dev` has no `master` or `main` and the switch below dies with
# "fatal: invalid reference: main" before any conflict exists.
git -C "$workdir/repo" init -q -b base
git -C "$workdir/repo" config user.name "Fixture Author"
git -C "$workdir/repo" config user.email "fixture@example.invalid"
printf 'original\n' > "$workdir/repo/config.txt"
git -C "$workdir/repo" add config.txt
git -C "$workdir/repo" -c commit.gpgsign=false commit -q -m 'fixture base commit'
git -C "$workdir/repo" switch -q -c conflicting-change
printf 'change from branch\n' > "$workdir/repo/config.txt"
git -C "$workdir/repo" add config.txt
git -C "$workdir/repo" -c commit.gpgsign=false commit -q -m 'conflicting branch change'
git -C "$workdir/repo" switch -q base
printf 'change from base\n' > "$workdir/repo/config.txt"
git -C "$workdir/repo" add config.txt
git -C "$workdir/repo" -c commit.gpgsign=false commit -q -m 'base branch change'
git -C "$workdir/repo" merge conflicting-change >/dev/null 2>&1 || true
