#!/usr/bin/env bash
set -euo pipefail

workdir=${1:?usage: setup.sh WORKDIR}
rm -rf -- "$workdir"
mkdir -p "$workdir"
cat > "$workdir/hang.py" <<'PY'
while True:
    pass
PY
