#!/usr/bin/env bash
# Installs the RNNoise noise suppression plugin (LADSPA) for the Hub's mic
# chain. Fedora only packages the rnnoise library, not the plugin, so we take
# the official release of noise-suppression-for-voice (GPL-3.0) and check it
# against a pinned checksum.
set -euo pipefail

VERSION=1.10
SHA256=811390b6eb6e28dde023c70590c74d26e74ebb2e595bcf4b95af2341db160e99
URL=https://github.com/werman/noise-suppression-for-voice/releases/download/v$VERSION/linux-rnnoise.zip

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
curl -fsSL -o "$tmp/rnnoise.zip" "$URL"
echo "$SHA256  $tmp/rnnoise.zip" | sha256sum -c -

python3 -c '
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    open(sys.argv[2], "wb").write(z.read("linux-rnnoise/ladspa/librnnoise_ladspa.so"))
' "$tmp/rnnoise.zip" "$tmp/librnnoise_ladspa.so"
install -D -m 755 "$tmp/librnnoise_ladspa.so" /usr/lib64/ladspa/librnnoise_ladspa.so
