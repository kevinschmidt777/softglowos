#!/usr/bin/env bash
# Laptops with two graphics chips: the desktop stays on the power-saving one,
# games and OBS start on the strong one. GNOME does that for apps whose
# desktop file sets PrefersNonDefaultGPU (through cardwire, Bazzite's
# switcheroo-control). Steam already has it. On one GPU nothing changes.
set -euo pipefail

for app in com.heroicgameslauncher.hgl net.lutris.Lutris com.obsproject.Studio steam; do
  file="/usr/share/applications/$app.desktop"
  # Fail the build if a launcher renamed its desktop file
  [ -f "$file" ] || { echo "Missing $file" >&2; exit 1; }
  desktop-file-edit --set-key=PrefersNonDefaultGPU --set-value=true "$file"
  grep -H '^PrefersNonDefaultGPU=' "$file"
done
