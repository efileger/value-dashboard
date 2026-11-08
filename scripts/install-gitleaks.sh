#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
version=8.24.3
archive="gitleaks_${version}_linux_x64.tar.gz"
[[ "$(uname -s)/$(uname -m)" == Linux/x86_64 ]] || { echo 'Use the Gitleaks 8.24.3 release for your OS/architecture.' >&2; exit 1; }
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
base="https://github.com/gitleaks/gitleaks/releases/download/v${version}"
curl -fsSL "$base/$archive" -o "$tmp/$archive"
curl -fsSL "$base/gitleaks_${version}_checksums.txt" -o "$tmp/checksums.txt"
(cd "$tmp" && grep " $archive$" checksums.txt | sha256sum -c -)
mkdir -p .venv/bin
tar -xzf "$tmp/$archive" -C .venv/bin gitleaks
.venv/bin/gitleaks version
