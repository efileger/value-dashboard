#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
version=1.7.7
archive="actionlint_${version}_linux_amd64.tar.gz"
[[ "$(uname -s)/$(uname -m)" == Linux/x86_64 ]] || { echo 'Use the actionlint 1.7.7 release for your OS/architecture.' >&2; exit 1; }
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
base="https://github.com/rhysd/actionlint/releases/download/v${version}"
curl -fsSL "$base/$archive" -o "$tmp/$archive"
curl -fsSL "$base/actionlint_${version}_checksums.txt" -o "$tmp/checksums.txt"
(cd "$tmp" && grep " $archive$" checksums.txt | sha256sum -c -)
mkdir -p .venv/bin
tar -xzf "$tmp/$archive" -C .venv/bin actionlint
.venv/bin/actionlint --version
