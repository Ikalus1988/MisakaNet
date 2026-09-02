#!/usr/bin/env bash
set -euo pipefail

workdir=${1:?usage: setup.sh WORKDIR}
rm -rf -- "$workdir"
mkdir -p "$workdir/repo"

git -C "$workdir/repo" init -q
git -C "$workdir/repo" config user.name "Fixture Author"
git -C "$workdir/repo" config user.email "fixture@example.invalid"
printf 'original\n' > "$workdir/repo/config.txt"
git -C "$workdir/repo" add config.txt
git -C "$workdir/repo" -c commit.gpgsign=false commit -q -m 'fixture base commit'
git -C "$workdir/repo" switch -q -c conflicting-change
printf 'change from branch\n' > "$workdir/repo/config.txt"
git -C "$workdir/repo" add config.txt
git -C "$workdir/repo" -c commit.gpgsign=false commit -q -m 'conflicting branch change'
git -C "$workdir/repo" switch -q master 2>/dev/null || git -C "$workdir/repo" switch -q main
printf 'change from base\n' > "$workdir/repo/config.txt"
git -C "$workdir/repo" add config.txt
git -C "$workdir/repo" -c commit.gpgsign=false commit -q -m 'base branch change'
git -C "$workdir/repo" merge conflicting-change >/dev/null 2>&1 || true
