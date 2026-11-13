#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.venv/.cache/uv}"
python -c 'import sys; assert (3, 11, 5) <= sys.version_info[:3] < (3, 12), "Use Python 3.11.5+ (3.11 series) to generate locks"'
uv pip compile --python-version 3.11.5 --generate-hashes --custom-compile-command 'bash scripts/lock-dependencies.sh' --output-file requirements.txt requirements.in
uv pip compile --python-version 3.11.5 --generate-hashes --custom-compile-command 'bash scripts/lock-dependencies.sh' --output-file requirements-dev.txt requirements-dev.in
