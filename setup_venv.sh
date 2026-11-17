#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$repo_dir"

if [[ -d .venv ]]; then
    echo "Refusing to use .venv. Remove it and use the repository's venv directory."
    exit 1
fi

if [[ ! -x venv/bin/python ]]; then
    python3 -m venv venv
fi

venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -r requirements.txt
echo "Environment ready: $repo_dir/venv"
