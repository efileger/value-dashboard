#!/usr/bin/env bash
# Shared entry point: Dev and CI execute these exact commands.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.venv/bin:$PATH"
case "${1:-fast}" in
  fast)
    unset SMOKE_TEST
    actionlint -shellcheck= -pyflakes=
    python -m compileall -q stock_dashboard stock_dashboard.py
    python -m pip check
    python -m ruff check .
    python -m ruff format --check .
    python -m mypy .
    python -m bandit -r stock_dashboard -q
    python -m pytest --allow-hosts=127.0.0.1,::1 --timeout=30 \
      --cov=stock_dashboard --cov-report="xml:${COVERAGE_FILE_PATH:-/tmp/value-dashboard-coverage.xml}" --cov-fail-under=75
    ;;
  audit)
    # Advisory lookup needs network access; errors fail closed in CI.
    python -m pip_audit --cache-dir .venv/.cache/pip-audit --require-hashes --disable-pip --progress-spinner=off \
      -r requirements.txt -f cyclonedx-json -o "${SBOM_PATH:-/tmp/value-dashboard-sbom.json}"
    ;;
  smoke)
    python scripts/smoke.py
    ;;
  staged-secrets)
    gitleaks protect --staged --redact
    ;;
  secrets)
    gitleaks detect --source . --redact
    ;;
  *) echo 'Usage: bash scripts/check.sh [fast|audit|secrets|staged-secrets|smoke]' >&2; exit 2 ;;
esac
