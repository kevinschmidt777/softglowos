#!/usr/bin/env bash
# Calamares's branding images from our logo and wordmark, and the version
set -euo pipefail

SYSTEM=$SRC/files/system
BRANDING=$DEST/etc/calamares/branding/softglowos
rsvg-convert -w 128 -h 128 "$SYSTEM/usr/share/icons/hicolor/scalable/places/softglowos-logo.svg" \
  -o "$BRANDING/logo.png"
rsvg-convert -h 96 "$SYSTEM/usr/share/softglowos/branding/wordmark-dark.svg" -o "$BRANDING/welcome.png"
sed -i "s/@VERSION@/$(cat "$SRC/VERSION")/" "$BRANDING/branding.desc"
