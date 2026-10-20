#!/usr/bin/env bash
# Installs openrgb-python (GPL-3.0), the OpenRGB SDK client behind the Hub's
# Lighting page. Fedora doesn't package it, so the pinned, pure-Python wheel
# from PyPI is checked against its checksum and unpacked next to the Hub's
# own modules (runs after install-hub.sh).
set -euo pipefail

VERSION=0.3.7
SHA256=2188636e7a5831a8030abe34b234ede8d4a263ba02bc903d975eb55a80551833
URL=https://files.pythonhosted.org/packages/68/d7/43deea59bc9a7bf4fd8e7fdc6695542d7c5a3034cf6627cd6c2121069920/openrgb_python-$VERSION-py3-none-any.whl

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
curl -fsSL -o "$tmp/openrgb_python.whl" "$URL"
echo "$SHA256  $tmp/openrgb_python.whl" | sha256sum -c -
python3 -m zipfile -e "$tmp/openrgb_python.whl" /usr/share/softglowos-hub/
