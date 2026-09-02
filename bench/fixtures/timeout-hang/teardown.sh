#!/usr/bin/env bash
set -euo pipefail

workdir=${1:?usage: teardown.sh WORKDIR}
rm -rf -- "$workdir"
