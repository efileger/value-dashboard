#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.venv/.cache/uv}"
python -c 'import sys; assert sys.version_info[:2] == (3, 11), "Use Python 3.11 to generate locks"'
uv pip compile --python-version 3.11 --generate-hashes --custom-compile-command 'bash scripts/lock-dependencies.sh' --output-file requirements.txt requirements.in
uv pip compile --python-version 3.11 --generate-hashes --custom-compile-command 'bash scripts/lock-dependencies.sh' --output-file requirements-dev.txt requirements-dev.in
