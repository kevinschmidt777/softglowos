#!/usr/bin/env bash
# Puts StreamController's official OBS plugin (GPL-3.0) next to our own mixer
# plugin in /usr/share/softglowos/streamcontroller; softglowos-streamcontroller
# copies them into StreamController on login. Pinned with a checksum; its
# Python backend sets itself up on first use (StreamController does that).
set -euo pipefail

COMMIT=242afda6bec75c568dfe71d2ce47a9a196d5a430
SHA256=e761bda8b0ab22afddebd840222f0ed23d9ed99627419fc5df1e11b3c2dfd90c
URL=https://github.com/StreamController/OBSPlugin/archive/$COMMIT.tar.gz
DEST=/usr/share/softglowos/streamcontroller/com_core447_OBSPlugin

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
curl -fsSL -o "$tmp/plugin.tar.gz" "$URL"
echo "$SHA256  $tmp/plugin.tar.gz" | sha256sum -c -
mkdir -p "$DEST"
tar -xzf "$tmp/plugin.tar.gz" -C "$DEST" --strip-components=1
# Fail the build if the layout StreamController expects changed
ls "$DEST/main.py" "$DEST/manifest.json" "$DEST/__install__.py"
