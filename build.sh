#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
python3 -m venv .venv-build
.venv-build/bin/python -m pip install -r requirements-build.txt
.venv-build/bin/python scripts/build.py
