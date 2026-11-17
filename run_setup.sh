#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$repo_dir"

if [[ ! -x venv/bin/python ]]; then
    echo "venv is missing. Run ./setup_venv.sh first."
    exit 1
fi

exec venv/bin/python setup_tournament.py "$@"
