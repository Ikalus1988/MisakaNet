#!/usr/bin/env bash
set -euo pipefail

workdir=${1:?usage: setup.sh WORKDIR}
rm -rf -- "$workdir"
mkdir -p "$workdir"
cat > "$workdir/app.py" <<'PY'
import module_that_does_not_exist

print("unreachable")
PY
