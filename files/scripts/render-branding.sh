#!/usr/bin/env bash
# Renders the placeholder branding from SVG sources into the PNGs
# that Plymouth (boot splash) and GDM (login screen) expect.
set -euo pipefail

SRC=/usr/share/softglowos/branding

# Only pull in rsvg-convert temporarily if the base image doesn't ship it
if ! rpm -q librsvg2-tools &>/dev/null; then
  dnf5 -y install librsvg2-tools
  trap 'dnf5 -y remove librsvg2-tools' EXIT
fi

# Boot splash watermark of the spinner theme Bazzite uses
rsvg-convert -h 64 "$SRC/wordmark-white.svg" \
  -o /usr/share/plymouth/themes/spinner/watermark.png

# Login screen logo (GDM reads this path via Fedora's dconf defaults)
rsvg-convert -h 48 "$SRC/wordmark-white.svg" \
  -o /usr/share/pixmaps/fedora-gdm-logo.png
