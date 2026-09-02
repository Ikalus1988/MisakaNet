#!/usr/bin/env bash
# Run one benchmark fixture inside a clean, disposable directory.
set -euo pipefail

fixture=${1:?usage: sandbox.sh FIXTURE.py}
if [[ ! -f "$fixture" ]]; then
  echo "fixture not found: $fixture" >&2
  exit 2
fi

scratch=$(mktemp -d "${TMPDIR:-/tmp}/misakanet-bench.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
cp "$fixture" "$scratch/fixture.py"

env -i \
  HOME="$scratch" \
  PATH="${PATH:-/usr/bin:/bin}" \
  PYTHONNOUSERSITE=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  python3 "$scratch/fixture.py"
