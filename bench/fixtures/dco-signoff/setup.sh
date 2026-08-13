#!/usr/bin/env bash
set -euo pipefail

workdir=${1:?usage: setup.sh WORKDIR}
rm -rf -- "$workdir"
mkdir -p "$workdir/repo"

git -C "$workdir/repo" init -q
git -C "$workdir/repo" config user.name "Fixture Author"
git -C "$workdir/repo" config user.email "fixture@example.invalid"
printf 'fixture\n' > "$workdir/repo/README.md"
git -C "$workdir/repo" add README.md
git -C "$workdir/repo" -c commit.gpgsign=false commit -q -m 'fixture commit without DCO sign-off'

git -C "$workdir/repo" log -1 --format='%B' > "$workdir/commit-message.txt"
