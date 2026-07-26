#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$HERE/src"
python -m unittest discover -s "$HERE/tests" -t "$HERE" "$@"

